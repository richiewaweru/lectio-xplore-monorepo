"""Durable section composition and writing over the generic generation runtime.

This module owns orchestration only. Persistence, leases, fencing, retries, and
checkpoint integrity stay in ``infra.generation_runtime``; composition and
writing stay in the stateless shared-lesson modules.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import weakref
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson.composer import (
    CompositionPolicy,
    CompositionValidationError,
    SectionCompositionPlan,
    compose_section,
    validate_composition_plan,
)
from document.shared_lesson.writer import (
    SectionSource,
    SectionTaskSummary,
    SectionWriteResult,
    SectionWriterRequest,
    SectionWriteValidationError,
    write_section,
)
from infra.execution.checkpoints import content_hash
from infra.database.models import GenerationWorkItemModel
from infra.generation_runtime import (
    CheckpointCompatibilityError,
    CheckpointIntegrityError,
    ErrorClass,
    LeaseLostError,
    RecoveryAction,
    RunAdmission,
    RuntimeCheckpointCompatibility,
    RunType,
    SourceIdentity,
    SourceIdentityConflict,
    WorkItemAdmission,
    WorkItemFailure,
    add_work_item,
    admit_run,
    cancel_run,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
    retry_work_item,
)

MAX_CONCURRENT_SECTION_WRITERS = 4
SECTION_WRITER_LEASE_SECONDS = 360
# A writer can make up to three 90-second provider calls. Bound the full
# section operation below its lease so a stalled call fails while fenced.
SECTION_WRITER_TIMEOUT_SECONDS = 300
_COMPOSER_DEFINITION = "shared-section-composer:v1"
_WRITER_DEFINITION = "shared-section-writer:v1"
_SECTION_PROVIDER_SEMAPHORES: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, asyncio.Semaphore
] = weakref.WeakKeyDictionary()


class SectionRuntimeError(ValueError):
    """The requested section work does not match its approved source."""


class CheckpointPayloadError(SectionRuntimeError):
    """A persisted checkpoint payload is malformed or mismatches its identity."""


class TeachingPlanSource(BaseModel):
    """Exact approved Teaching Plan snapshot required by section work."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    plan: TeachingPlan
    revision_record: TeachingRevisionRecord
    id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SectionWriterJob:
    """Inputs for one already-admitted section writer work item."""

    session: Any
    work_item_id: str
    worker_id: str
    source: TeachingPlanSource
    request: SectionWriterRequest
    status: str
    provider: Callable[[dict[str, Any]], Awaitable[Any]] | None = None
    lease_seconds: int = SECTION_WRITER_LEASE_SECONDS


@dataclass(frozen=True)
class SectionWriterOutcome:
    """Independent result for one section; failures do not cancel ready siblings."""

    work_item_id: str
    result: SectionWriteResult | None = None
    error: Exception | None = None
    preserved_ready: bool = False


def verify_teaching_plan_source(source: TeachingPlanSource) -> SourceIdentity:
    """Verify approved revision provenance and recompute both source hashes."""
    record = source.revision_record
    if record.status != "approved":
        raise SectionRuntimeError(
            f"SharedDocument source revision must be approved, got {record.status!r}"
        )
    if source.plan.approval_status != "approved":
        raise SectionRuntimeError("SharedDocument source plan approval_status must be approved")
    if source.plan.contract_version < 2:
        raise SectionRuntimeError(
            "SharedDocument source requires Teaching Plan contract version 2 continuity"
        )
    if source.plan.teaching_plan_id != source.id:
        raise SectionRuntimeError("Teaching Plan source ID differs from its approved snapshot")
    if source.plan.revision != source.revision:
        raise SectionRuntimeError("Teaching Plan revision differs from its approved snapshot")
    if record.teaching_plan_id != source.id or record.revision != source.revision:
        raise SectionRuntimeError("Teaching Revision Record identity differs from its source")
    if not record.content_hash:
        raise SectionRuntimeError("approved Teaching Revision Record has no content hash")
    if not isinstance(record.plan, Mapping):
        raise SectionRuntimeError("approved Teaching Revision Record has an invalid plan snapshot")
    try:
        record_plan = TeachingPlan.model_validate(record.plan)
    except (TypeError, ValueError) as exc:
        raise SectionRuntimeError("approved Teaching Revision Record plan is invalid") from exc
    if record_plan.approval_status != "approved":
        raise SectionRuntimeError("Teaching Revision Record plan approval_status must be approved")
    if record_plan.teaching_plan_id != record.teaching_plan_id:
        raise SectionRuntimeError("Teaching Revision Record plan ID differs from its record")
    if record_plan.revision != record.revision:
        raise SectionRuntimeError("Teaching Revision Record plan revision differs from its record")

    record_hash = teaching_plan_content_hash(record_plan)
    actual_hash = teaching_plan_content_hash(source.plan)
    if record_hash != record.content_hash:
        raise SectionRuntimeError("Teaching Revision Record content hash does not match its plan")
    if actual_hash != record_hash:
        raise SectionRuntimeError("Teaching Plan source content differs from its approved revision")
    if source.content_hash != actual_hash:
        raise SectionRuntimeError("Teaching Plan content hash differs from its approved snapshot")
    return SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash=actual_hash,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _section_tasks(
    section: TeachingPlanSection, tasks: Sequence[SharedTaskSpec]
) -> tuple[SharedTaskSpec, ...]:
    block_ids = {block.id for block in section.blocks}
    return tuple(task for task in tasks if task.teaching_block_id in block_ids)


def _section_payload(
    *,
    section: TeachingPlanSection,
    tasks: Sequence[SharedTaskSpec],
    sources: Sequence[SectionSource],
) -> dict[str, Any]:
    return {
        "section": section.model_dump(mode="json"),
        "tasks": [task.model_dump(mode="json") for task in tasks],
        "sources": [source.model_dump(mode="json") for source in sources],
    }


def _checkpoint_compatibility(
    *,
    source: SourceIdentity,
    input_hash: str,
    definition_hash: str,
    composition_identity: str | None,
) -> RuntimeCheckpointCompatibility:
    return RuntimeCheckpointCompatibility(
        schema_version=1,
        source_revision=source.source_revision,
        source_hash=source.source_hash,
        input_hash=input_hash,
        definition_hash=definition_hash,
        composition_identity=composition_identity,
    )


async def _record_execution_failure(
    session: Any,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    error: Exception,
) -> None:
    if isinstance(error, LeaseLostError):
        raise error
    if isinstance(error, (CheckpointCompatibilityError, SourceIdentityConflict)):
        error_class = ErrorClass.SOURCE_CONFLICT
        recovery = RecoveryAction.NONE
        code = "checkpoint_compatibility_conflict"
        summary = "Persisted checkpoint no longer matches the approved source or work identity."
    elif isinstance(error, (CheckpointIntegrityError, CheckpointPayloadError)):
        error_class = ErrorClass.UNSUPPORTED_CONTRACT
        recovery = RecoveryAction.NONE
        code = "checkpoint_integrity_failure"
        summary = "Persisted checkpoint failed compatibility or integrity validation."
    elif isinstance(error, (TimeoutError, ConnectionError)):
        error_class = ErrorClass.PROVIDER_TRANSPORT
        recovery = RecoveryAction.RETRY
        code = "provider_transport"
        summary = "Section provider transport failed."
    elif isinstance(
        error, (CompositionValidationError, SectionWriteValidationError, ValidationError)
    ):
        error_class = ErrorClass.PROVIDER_OUTPUT
        recovery = RecoveryAction.RETRY
        code = "invalid_section_output"
        summary = "Section output failed deterministic validation."
    else:
        error_class = ErrorClass.INTERNAL_PROGRAMMING
        recovery = RecoveryAction.NONE
        code = "section_runtime_error"
        summary = "Section runtime failed unexpectedly."
    await fail_work_item(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        lease_token=lease_token,
        failure=WorkItemFailure(
            error_code=code,
            error_class=error_class,
            safe_summary=summary,
            recovery_action=recovery,
        ),
    )


async def admit_section_run(
    session: Any,
    *,
    build_id: str,
    owner_user_id: str,
    request_key: str,
    source: TeachingPlanSource,
    sections: Sequence[TeachingPlanSection] | None = None,
    tasks: Sequence[SharedTaskSpec] = (),
    sources: Sequence[SectionSource] = (),
    max_attempts: int = 3,
) -> tuple[Any, tuple[Any, ...]]:
    """Admit/reuse a SharedDocument run and stable composition work per section."""
    identity = verify_teaching_plan_source(source)
    selected_sections = tuple(sections if sections is not None else source.plan.sections)
    if not selected_sections:
        raise SectionRuntimeError("Teaching Plan must contain at least one section")
    if len({section.slot_id for section in selected_sections}) != len(selected_sections):
        raise SectionRuntimeError("section slot IDs must be unique")
    if any(section not in source.plan.sections for section in selected_sections):
        raise SectionRuntimeError("requested section is not part of the approved Teaching Plan")

    run_result = await admit_run(
        session,
        RunAdmission(
            build_id=build_id,
            owner_user_id=owner_user_id,
            run_type=RunType.SHARED_DOCUMENT,
            request_key=request_key,
            stage="section_composition",
            source_artifact_type=identity.source_artifact_type,
            source_artifact_id=identity.source_artifact_id,
            source_revision=identity.source_revision,
            source_hash=identity.source_hash,
        ),
    )
    run_record = run_result.record
    items: list[Any] = []
    for section in selected_sections:
        task_slice = _section_tasks(section, tasks)
        payload = _section_payload(section=section, tasks=task_slice, sources=sources)
        items.append(
            (
                await add_work_item(
                    session,
                    WorkItemAdmission(
                        run_id=run_record.id,
                        item_key=f"compose:{section.slot_id}",
                        stage="section_composition",
                        input_hash=_stable_hash(payload),
                        definition_hash=_stable_hash(_COMPOSER_DEFINITION),
                        max_attempts=max_attempts,
                    ),
                )
            ).record
        )
    return run_record, tuple(items)


async def compose_section_work_item(
    session: Any,
    *,
    work_item_id: str,
    worker_id: str,
    source: TeachingPlanSource,
    section: TeachingPlanSection,
    tasks: Sequence[SharedTaskSpec],
    sources: Sequence[SectionSource] = (),
    provider: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
    policy: CompositionPolicy | None = None,
    lease_seconds: int = 300,
) -> SectionCompositionPlan:
    """Claim, checkpoint and fence one section composition output."""
    identity = verify_teaching_plan_source(source)
    selected_policy = policy or CompositionPolicy()
    task_slice = _section_tasks(section, tasks)
    payload = _section_payload(section=section, tasks=task_slice, sources=sources)
    input_hash = _stable_hash(payload)
    definition_hash = _stable_hash(_COMPOSER_DEFINITION)
    compatibility = _checkpoint_compatibility(
        source=identity,
        input_hash=input_hash,
        definition_hash=definition_hash,
        composition_identity=None,
    )
    item = await claim_work_item(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        source=identity,
        lease_seconds=lease_seconds,
    )
    try:
        checkpoint = await load_compatible_checkpoint(
            session,
            work_item_id=work_item_id,
            worker_id=worker_id,
            lease_token=item.lease_token,
            compatibility=compatibility,
        )
        if checkpoint is None:
            # The provider call can be slow. Persist the claim first so no
            # database transaction or lock remains open while composing.
            await session.commit()
            plan = await compose_section(
                section=section,
                tasks=task_slice,
                provider=provider,
                policy=selected_policy,
            )
            await persist_checkpoint(
                session,
                work_item_id=work_item_id,
                worker_id=worker_id,
                lease_token=item.lease_token,
                compatibility=compatibility,
                payload=plan.model_dump(mode="json"),
            )
        else:
            try:
                plan = SectionCompositionPlan.model_validate(checkpoint.payload)
            except (ValidationError, TypeError, ValueError) as exc:
                raise CheckpointPayloadError("persisted composition checkpoint is invalid") from exc
        # Revalidate the immutable composition against the exact current section/tasks.
        try:
            validate_composition_plan(
                plan=plan, section=section, tasks=task_slice, policy=selected_policy
            )
        except CompositionValidationError as exc:
            if checkpoint is not None:
                raise CheckpointPayloadError(
                    "persisted composition checkpoint no longer matches its source"
                ) from exc
            raise
    except LeaseLostError:
        raise
    except Exception as exc:
        await _record_execution_failure(
            session,
            work_item_id=work_item_id,
            worker_id=worker_id,
            lease_token=item.lease_token,
            error=exc,
        )
        raise
    await complete_work_item(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        lease_token=item.lease_token,
        output_json=plan.model_dump(mode="json"),
        output_hash=content_hash(plan.model_dump(mode="json")),
    )
    return plan


def make_section_writer_request(
    *,
    section: TeachingPlanSection,
    composition: SectionCompositionPlan,
    tasks: Sequence[SharedTaskSpec],
    sources: Sequence[SectionSource] = (),
) -> SectionWriterRequest:
    """Build the writer request from the exact approved composition and task anchors."""
    task_slice = _section_tasks(section, tasks)
    validate_composition_plan(plan=composition, section=section, tasks=task_slice)
    summaries = tuple(
        SectionTaskSummary(
            task_spec_id=task.id,
            teaching_block_id=task.teaching_block_id,
            action=task.action,
            purpose=task.purpose,
            prompt=task.prompt,
            expected_evidence=task.expected_evidence,
        )
        for task in task_slice
    )
    return SectionWriterRequest(
        section=section,
        composition_plan=composition,
        sources=tuple(sources),
        task_summaries=summaries,
    )


async def admit_writer_work_item(
    session: Any,
    *,
    run_id: str,
    section: TeachingPlanSection,
    request: SectionWriterRequest,
    max_attempts: int = 3,
) -> Any:
    """Admit writer work whose identity is bound to this exact composition."""
    composition_identity = _stable_hash(request.composition_plan.model_dump(mode="json"))
    input_payload = request.model_dump(mode="json")
    result = await add_work_item(
        session,
        WorkItemAdmission(
            run_id=run_id,
            item_key=f"write:{section.slot_id}",
            stage="section_writing",
            input_hash=_stable_hash(input_payload),
            definition_hash=_stable_hash(_WRITER_DEFINITION),
            composition_identity=composition_identity,
            max_attempts=max_attempts,
        ),
    )
    return result.record


async def _write_section_work_item(
    session: Any,
    *,
    work_item_id: str,
    worker_id: str,
    source: TeachingPlanSource,
    request: SectionWriterRequest,
    provider: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
    provider_semaphore: asyncio.Semaphore,
    lease_seconds: int = SECTION_WRITER_LEASE_SECONDS,
) -> SectionWriteResult:
    """Write one section under a provider-call cap and a durable lease fence."""
    identity = verify_teaching_plan_source(source)
    composition_identity = _stable_hash(request.composition_plan.model_dump(mode="json"))
    input_hash = _stable_hash(request.model_dump(mode="json"))
    definition_hash = _stable_hash(_WRITER_DEFINITION)
    compatibility = _checkpoint_compatibility(
        source=identity,
        input_hash=input_hash,
        definition_hash=definition_hash,
        composition_identity=composition_identity,
    )
    item = await claim_work_item(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        source=identity,
        lease_seconds=lease_seconds,
    )
    try:
        checkpoint = await load_compatible_checkpoint(
            session,
            work_item_id=work_item_id,
            worker_id=worker_id,
            lease_token=item.lease_token,
            compatibility=compatibility,
        )
        expected_composition = request.composition_plan.model_dump(mode="json")
        if checkpoint is None:
            await persist_checkpoint(
                session,
                work_item_id=work_item_id,
                worker_id=worker_id,
                lease_token=item.lease_token,
                compatibility=compatibility,
                payload={
                    "composition_identity": composition_identity,
                    "plan": expected_composition,
                },
            )
        else:
            try:
                verify_writer_checkpoint_payload(
                    checkpoint.payload, composition=request.composition_plan
                )
            except SectionRuntimeError as exc:
                raise CheckpointPayloadError(str(exc)) from exc

        # Publish both the claim and its compatible composition checkpoint
        # before the writer makes any provider call.
        await session.commit()
        if provider is None:
            from document.shared_lesson.writer import _default_provider

            provider_dispatch = _default_provider
        else:
            provider_dispatch = provider
        deadline = asyncio.get_running_loop().time() + SECTION_WRITER_TIMEOUT_SECONDS
        bounded_provider = _bounded_section_provider(
            provider_dispatch,
            provider_semaphore,
            deadline=deadline,
        )
        # Keep provider/validation work separate from this session-owning task.
        # asyncio.wait_for waits for cancellation to finish, so a provider that
        # suppresses cancellation can otherwise keep the lease running forever.
        writer_task = asyncio.create_task(
            write_section(request=request, provider=bounded_provider),
            name=f"shared-section-writer:{work_item_id}",
        )
        try:
            done, _pending = await asyncio.wait(
                {writer_task}, timeout=max(0.0, deadline - asyncio.get_running_loop().time())
            )
        except BaseException:
            _cancel_detached_writer_task(writer_task)
            raise
        if not done:
            _cancel_detached_writer_task(writer_task)
            raise TimeoutError("SharedDocument section writer exceeded its aggregate deadline")
        result = writer_task.result()
    except LeaseLostError:
        raise
    except Exception as exc:
        await _record_execution_failure(
            session,
            work_item_id=work_item_id,
            worker_id=worker_id,
            lease_token=item.lease_token,
            error=exc,
        )
        raise
    output = result.model_dump(mode="json")
    # A cancelled run, expired lease, or newer fence rejects this completion.
    await complete_work_item(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        lease_token=item.lease_token,
        output_json=output,
        output_hash=content_hash(output),
    )
    return result


async def write_section_work_items(
    jobs: Sequence[SectionWriterJob],
) -> tuple[SectionWriterOutcome, ...]:
    """Run selected queued writer items with one internal four-provider cap.

    Each job owns its AsyncSession. Already-ready siblings are returned as
    preserved outcomes without claiming or changing them. Failed/recoverable
    work is not implicitly reset: callers retry one item first, then submit that
    queued item here. Per-item errors are collected so a failing section does
    not cancel healthy siblings in the same batch.
    """
    selected = tuple(jobs)
    ids = [job.work_item_id for job in selected]
    if len(ids) != len(set(ids)):
        raise SectionRuntimeError("writer batch contains duplicate work item IDs")
    semaphore = _section_provider_semaphore()

    async def run_one(job: SectionWriterJob) -> SectionWriterOutcome:
        if job.status == "ready":
            return SectionWriterOutcome(work_item_id=job.work_item_id, preserved_ready=True)
        if job.status != "queued":
            return SectionWriterOutcome(
                work_item_id=job.work_item_id,
                error=SectionRuntimeError(
                    "writer batch accepts queued items only; retry a failed section explicitly"
                ),
            )
        try:
            result = await _write_section_work_item(
                job.session,
                work_item_id=job.work_item_id,
                worker_id=job.worker_id,
                source=job.source,
                request=job.request,
                provider=job.provider,
                provider_semaphore=semaphore,
                lease_seconds=job.lease_seconds,
            )
        except LeaseLostError as exc:
            await _settle_writer_job_session(job.session, commit=False)
            return SectionWriterOutcome(work_item_id=job.work_item_id, error=exc)
        except asyncio.CancelledError:
            await _settle_writer_job_session(job.session, commit=False)
            raise
        except Exception as exc:  # noqa: BLE001 - isolate section failures and finish siblings.
            # _write_section_work_item records typed failures before raising.
            # Commit only when a fresh read proves that failure was recorded.
            fresh = await job.session.get(GenerationWorkItemModel, job.work_item_id)
            if fresh is None or fresh.status not in {"failed_recoverable", "failed_terminal"}:
                await _settle_writer_job_session(job.session, commit=False)
                raise
            try:
                await _settle_writer_job_session(job.session, commit=True)
            except BaseException:
                await _settle_writer_job_session(job.session, commit=False)
                raise
            return SectionWriterOutcome(work_item_id=job.work_item_id, error=exc)
        try:
            await _settle_writer_job_session(job.session, commit=True)
        except BaseException:
            await _settle_writer_job_session(job.session, commit=False)
            raise
        return SectionWriterOutcome(work_item_id=job.work_item_id, result=result)

    tasks = [asyncio.create_task(run_one(job)) for job in selected]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return tuple(results)


async def _settle_writer_job_session(session: Any, *, commit: bool) -> None:
    method = getattr(session, "commit" if commit else "rollback", None)
    if callable(method):
        await method()


def _section_provider_semaphore() -> asyncio.Semaphore:
    """Share the provider cap across batches for this worker event loop."""
    loop = asyncio.get_running_loop()
    semaphore = _SECTION_PROVIDER_SEMAPHORES.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SECTION_WRITERS)
        _SECTION_PROVIDER_SEMAPHORES[loop] = semaphore
    return semaphore


def _bounded_section_provider(
    provider: Callable[[dict[str, Any]], Awaitable[Any]],
    semaphore: asyncio.Semaphore,
    *,
    deadline: float,
) -> Callable[[dict[str, Any]], Awaitable[Any]]:
    """Cap provider concurrency and forbid further calls after the writer deadline."""

    async def dispatch(payload: dict[str, Any]) -> Any:
        loop = asyncio.get_running_loop()
        if loop.time() >= deadline:
            raise TimeoutError("SharedDocument section writer deadline expired")
        async with semaphore:
            if loop.time() >= deadline:
                raise TimeoutError("SharedDocument section writer deadline expired")
            result = await provider(payload)
            if loop.time() >= deadline:
                raise TimeoutError("SharedDocument section writer deadline expired")
            return result

    return dispatch


def _consume_detached_writer_task(task: asyncio.Task[Any]) -> None:
    """Retrieve a late detached provider-task exception without touching DB state."""
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


def _cancel_detached_writer_task(task: asyncio.Task[Any]) -> None:
    """Request cancellation without waiting on a cancellation-resistant provider."""
    if not task.done():
        task.cancel()
        task.add_done_callback(_consume_detached_writer_task)


def verify_writer_checkpoint_payload(payload: Any, *, composition: SectionCompositionPlan) -> None:
    """Reject a checkpoint that is stale or belongs to another composition."""
    expected_plan = composition.model_dump(mode="json")
    expected_identity = _stable_hash(expected_plan)
    if payload != {"composition_identity": expected_identity, "plan": expected_plan}:
        raise SectionRuntimeError("writer checkpoint belongs to a different composition plan")


async def retry_failed_section(session: Any, *, work_item_id: str, owner_user_id: str) -> Any:
    """Retry exactly one failed section; sibling rows and outputs are untouched."""
    return await retry_work_item(
        session,
        work_item_id=work_item_id,
        owner_user_id=owner_user_id,
    )


async def cancel_section_run(session: Any, *, run_id: str, owner_user_id: str) -> Any:
    """Cancel a section run and invalidate all outstanding worker fences."""
    return await cancel_run(session, run_id=run_id, owner_user_id=owner_user_id)


async def restart_section_run(
    session: Any,
    *,
    previous_run_id: str,
    build_id: str,
    owner_user_id: str,
    request_key: str,
    source: TeachingPlanSource,
    sections: Sequence[TeachingPlanSection] | None = None,
    tasks: Sequence[SharedTaskSpec] = (),
    sources: Sequence[SectionSource] = (),
    max_attempts: int = 3,
) -> tuple[Any, tuple[Any, ...]]:
    """Start a new run/revision; the request key must not reuse the prior run."""
    run, items = await admit_section_run(
        session,
        build_id=build_id,
        owner_user_id=owner_user_id,
        request_key=request_key,
        source=source,
        sections=sections,
        tasks=tasks,
        sources=sources,
        max_attempts=max_attempts,
    )
    if run.id == previous_run_id:
        raise SectionRuntimeError("restart requires a fresh idempotency request key")
    return run, items


async def fail_section_work_item(
    session: Any,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    error_code: str,
    error_class: ErrorClass,
    safe_summary: str,
    recovery_action: RecoveryAction,
) -> Any:
    """Persist typed failures through the generic retry/failure state machine."""
    return await fail_work_item(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        lease_token=lease_token,
        failure=WorkItemFailure(
            error_code=error_code,
            error_class=error_class,
            safe_summary=safe_summary,
            recovery_action=recovery_action,
        ),
    )


__all__ = [
    "MAX_CONCURRENT_SECTION_WRITERS",
    "SectionRuntimeError",
    "SectionWriterJob",
    "SectionWriterOutcome",
    "TeachingPlanSource",
    "admit_section_run",
    "admit_writer_work_item",
    "cancel_section_run",
    "compose_section_work_item",
    "fail_section_work_item",
    "make_section_writer_request",
    "restart_section_run",
    "retry_failed_section",
    "verify_teaching_plan_source",
    "verify_writer_checkpoint_payload",
    "write_section_work_items",
]
