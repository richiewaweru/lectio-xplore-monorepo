"""Durable admission and commit for one boundary targeted writer repair.

The boundary runtime already owns the single targeted writer provider call.  If
that repair changes a section, this module turns the validated replacement into
the generic ``replace_work_item`` successor of the accepted writer item.  The
replacement is therefore durable and visible to the normal SharedDocument
loader, while the original ready row and every healthy sibling remain intact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.boundary import BoundaryValidationResult
from document.shared_lesson.boundary_runtime import accepted_section_output_hash
from document.shared_lesson.continuity import (
    ContinuityIssue,
    ExpectedNodeShape,
    validate_section_boundary,
    validate_section_continuity,
)
from document.shared_lesson.models import SharedSection
from document.shared_lesson.runtime import (
    TeachingPlanSource,
    _stable_hash,
    verify_teaching_plan_source,
)
from document.shared_lesson.writer import (
    SectionWriterDraft,
    SectionWriteResult,
    SectionWriterRequest,
    SectionWriteValidationError,
    validate_and_build_section,
)
from infra.database.models import GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    ErrorClass,
    LeaseLostError,
    RecoveryAction,
    RuntimeCheckpoint,
    RuntimeCheckpointCompatibility,
    SourceIdentity,
    WorkItemAdmission,
    WorkItemFailure,
    WorkItemReplacement,
    active_work_items,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
    replace_work_item,
)

WRITER_REPAIR_STAGE = "section_writing"
WRITER_REPAIR_DEFINITION = "shared-section-boundary-targeted-repair:v1"


class WriterRepairRuntimeError(ValueError):
    """A targeted repair cannot be admitted or committed safely."""


class WriterRepairSourceConflict(WriterRepairRuntimeError):
    """The approved source or accepted writer predecessor is stale."""


class WriterRepairCheckpointError(WriterRepairRuntimeError):
    """A repair checkpoint does not match its immutable work identity."""


class WriterRepairWorkOrder(BaseModel):
    """Closed identity and already validated output for one targeted repair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    source: SourceIdentity
    section_id: str = Field(min_length=1)
    composition_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    prior_writer_work_item_id: str = Field(min_length=1)
    prior_writer_output_hash: str = Field(min_length=1)
    boundary_work_item_id: str = Field(min_length=1)
    accepted_section_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    issue: ContinuityIssue
    previous_section: SharedSection
    next_section: SharedSection
    replacement: SectionWriteResult
    definition: Literal["shared-section-boundary-targeted-repair:v1"] = WRITER_REPAIR_DEFINITION

    @staticmethod
    def _hash_payload(value: Any) -> str:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @property
    def identity_hash(self) -> str:
        return self._hash_payload(self.model_dump(mode="json"))


@dataclass(frozen=True)
class WriterRepairWorkItemJob:
    session: Any
    work_item_id: str
    worker_id: str
    source: TeachingPlanSource | SourceIdentity
    work: WriterRepairWorkOrder
    writer_request: SectionWriterRequest
    worker_status: str = "queued"
    lease_seconds: int = 300


@dataclass(frozen=True)
class WriterRepairAdmission:
    """The admitted successor work item alongside its immutable work order.

    A caller that also needs to execute the admission (rather than leaving it
    for the normal worker loop to pick up as ``queued``) needs the exact
    ``WriterRepairWorkOrder`` this admission bound -- ``execute_writer_repair_work_item``
    treats it as the closed, already-validated source of truth and never
    reconstructs it from the database.
    """

    item: Any
    work: WriterRepairWorkOrder


@dataclass(frozen=True)
class WriterRepairOutcome:
    work_item_id: str
    result: SectionWriteResult | None = None
    error_code: str | None = None
    error_summary: str | None = None
    preserved_ready_siblings: bool = True


def _identity(source: TeachingPlanSource | SourceIdentity) -> SourceIdentity:
    if isinstance(source, TeachingPlanSource):
        return verify_teaching_plan_source(source)
    if isinstance(source, SourceIdentity):
        return source
    raise WriterRepairSourceConflict("targeted repair requires an approved Teaching Plan source")


def _plan_sections(
    source: TeachingPlanSource, previous_id: str, next_id: str
) -> tuple[TeachingPlanSection, TeachingPlanSection]:
    by_id = {section.slot_id: section for section in source.plan.sections}
    previous_plan = by_id.get(previous_id)
    next_plan = by_id.get(next_id)
    if previous_plan is None or next_plan is None:
        raise WriterRepairSourceConflict("boundary sections are absent from the approved plan")
    positions = {section.slot_id: index for index, section in enumerate(source.plan.sections)}
    if positions[next_id] != positions[previous_id] + 1:
        raise WriterRepairSourceConflict("boundary sections are not adjacent in the approved plan")
    return previous_plan, next_plan


def _expected_shapes(request: SectionWriterRequest) -> tuple[ExpectedNodeShape, ...]:
    return tuple(
        ExpectedNodeShape(
            id=item.id,
            kind=item.kind,
            teaching_block_id=item.teaching_block_id,
            semantic_role=item.semantic_role,
            task_spec_id=item.task_spec_id,
        )
        for item in request.composition_plan.items
    )


def _as_section(result: SectionWriteResult, *, position: int) -> SharedSection:
    return result.as_shared_section(section_id=result.section_slot_id, position=position)


def _validated_result(
    *, request: SectionWriterRequest, section: SharedSection
) -> SectionWriteResult:
    if section.id != request.section.slot_id:
        raise WriterRepairRuntimeError("repair output belongs to a different section")
    ordinary_nodes = tuple(
        node.model_dump(mode="json") for node in section.nodes if node.kind != "task_anchor"
    )
    try:
        result = validate_and_build_section(
            request=request,
            draft=SectionWriterDraft.model_validate({"nodes": ordinary_nodes}),
        )
    except (TypeError, ValueError, SectionWriteValidationError) as exc:
        raise WriterRepairRuntimeError(
            "targeted repair output violates the closed writer contract"
        ) from exc
    if result.as_shared_section(section_id=section.id, position=section.position) != section:
        raise WriterRepairRuntimeError("targeted repair output changed after writer validation")
    return result


async def _load_predecessor(
    session: Any,
    *,
    predecessor_work_item_id: str,
    accepted_section: SharedSection,
    request: SectionWriterRequest,
) -> GenerationWorkItemModel:
    predecessor = await session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.id == predecessor_work_item_id
        )
    )
    if predecessor is None:
        raise WriterRepairSourceConflict("accepted writer predecessor does not exist")
    if predecessor.stage != WRITER_REPAIR_STAGE or predecessor.status != "ready":
        raise WriterRepairSourceConflict("targeted repair predecessor is no longer ready")
    successor = await session.scalar(
        select(GenerationWorkItemModel.id).where(
            GenerationWorkItemModel.replaces_work_item_id == predecessor_work_item_id
        )
    )
    if successor is not None:
        raise WriterRepairSourceConflict("targeted repair predecessor already has a successor")
    current = predecessor
    seen: set[str] = set()
    while current.replaces_work_item_id is not None:
        if current.id in seen:
            raise WriterRepairSourceConflict("writer replacement chain contains a cycle")
        seen.add(current.id)
        current = await session.scalar(
            select(GenerationWorkItemModel).where(
                GenerationWorkItemModel.id == current.replaces_work_item_id
            )
        )
        if current is None:
            raise WriterRepairSourceConflict("writer replacement chain has a missing predecessor")
    if current.item_key != f"write:{accepted_section.id}":
        raise WriterRepairSourceConflict(
            "targeted repair predecessor is not the logical writer root"
        )
    if predecessor.output_json is None or not predecessor.output_hash:
        raise WriterRepairSourceConflict("accepted writer predecessor has no complete output")
    if content_hash(predecessor.output_json) != predecessor.output_hash:
        raise WriterRepairSourceConflict("accepted writer predecessor output hash is invalid")
    try:
        previous_result = SectionWriteResult.model_validate(predecessor.output_json)
    except (TypeError, ValueError) as exc:
        raise WriterRepairSourceConflict("accepted writer predecessor output is invalid") from exc
    previous_section = _as_section(previous_result, position=accepted_section.position)
    if previous_section.id != accepted_section.id or previous_section != accepted_section:
        raise WriterRepairSourceConflict(
            "accepted writer predecessor differs from the boundary input"
        )
    expected_composition = _stable_hash(request.composition_plan.model_dump(mode="json"))
    if predecessor.composition_identity != expected_composition:
        raise WriterRepairSourceConflict("accepted writer predecessor uses a stale composition")
    return predecessor


async def _verify_boundary_proof(
    session: Any,
    *,
    boundary_work_item_id: str,
    run_id: str,
    source: SourceIdentity,
    boundary_result: BoundaryValidationResult,
) -> None:
    """Require the failed boundary item to durably prove this exact repair."""
    boundary = await session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.id == boundary_work_item_id,
            GenerationWorkItemModel.run_id == run_id,
            GenerationWorkItemModel.stage == "continuity_validation",
        )
    )
    if boundary is None or boundary.status != "failed_recoverable":
        raise WriterRepairSourceConflict(
            "boundary repair proof is unavailable or no longer recoverable"
        )
    if boundary.checkpoint_json is None:
        raise WriterRepairSourceConflict("boundary repair result was not durably checkpointed")
    try:
        checkpoint = RuntimeCheckpoint.model_validate(boundary.checkpoint_json)
    except (TypeError, ValueError) as exc:
        raise WriterRepairSourceConflict(
            "boundary repair checkpoint violates its runtime contract"
        ) from exc
    if content_hash(checkpoint.payload) != checkpoint.payload_hash:
        raise WriterRepairSourceConflict("boundary repair checkpoint hash is invalid")
    if (
        checkpoint.compatibility.source_revision != source.source_revision
        or checkpoint.compatibility.source_hash != source.source_hash
        or checkpoint.compatibility.input_hash != boundary.input_hash
        or checkpoint.compatibility.definition_hash != boundary.definition_hash
        or checkpoint.compatibility.composition_identity != boundary.composition_identity
    ):
        raise WriterRepairSourceConflict("boundary repair checkpoint identity is stale")
    payload = checkpoint.payload
    if (
        not isinstance(payload, Mapping)
        or payload.get("kind") != "shared_lesson_boundary_repair_result"
    ):
        raise WriterRepairSourceConflict(
            "boundary work item does not contain a targeted repair proof"
        )
    work = payload.get("work")
    if not isinstance(work, Mapping) or (
        work.get("source_plan_id"),
        work.get("source_plan_revision"),
        work.get("source_plan_hash"),
    ) != (source.source_artifact_id, source.source_revision, source.source_hash):
        raise WriterRepairSourceConflict(
            "boundary repair proof source differs from the approved source"
        )
    if payload.get("result") != boundary_result.model_dump(mode="json"):
        raise WriterRepairSourceConflict(
            "boundary repair proof differs from the supplied validation result"
        )


def _repair_input_hash(work: WriterRepairWorkOrder) -> str:
    return work.identity_hash


async def admit_writer_repair_work_item(
    session: Any,
    *,
    owner_user_id: str,
    source: TeachingPlanSource | SourceIdentity,
    predecessor_work_item_id: str,
    accepted_section: SharedSection,
    writer_request: SectionWriterRequest,
    boundary_result: BoundaryValidationResult,
    boundary_work_item_id: str,
    issue: ContinuityIssue,
    previous_section: SharedSection,
    next_section: SharedSection,
    max_attempts: int = 3,
) -> WriterRepairAdmission:
    """Admit a validated changed boundary repair as one linked writer successor.

    The boundary validator has already spent its one targeted provider call.
    This operation persists that closed result as durable work; it never invokes
    a provider and therefore cannot create an unbounded second repair loop.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if not isinstance(source, TeachingPlanSource):
        raise WriterRepairSourceConflict(
            "targeted repair admission requires the approved source snapshot"
        )
    identity = _identity(source)
    if writer_request.section.slot_id != accepted_section.id:
        raise WriterRepairSourceConflict("writer request and accepted section differ")
    if boundary_result.status != "pass" or not boundary_result.passed:
        raise WriterRepairRuntimeError("only a passing repaired boundary can be admitted")
    if not boundary_result.repair_attempted:
        raise WriterRepairRuntimeError("boundary result does not prove a targeted repair")
    if len(boundary_result.initial_issues) != 1 or boundary_result.initial_issues[0] != issue:
        raise WriterRepairRuntimeError(
            "boundary issue is not the exact typed issue that triggered repair"
        )
    if issue.affected_section_id != accepted_section.id:
        raise WriterRepairRuntimeError("boundary issue does not target the accepted writer section")
    target_original = (
        previous_section if issue.affected_section_id == previous_section.id else next_section
    )
    if accepted_section != target_original:
        raise WriterRepairSourceConflict(
            "accepted section is not the exact original boundary input"
        )
    if (
        previous_section.id != boundary_result.previous_section.id
        or next_section.id != boundary_result.next_section.id
    ):
        raise WriterRepairRuntimeError(
            "boundary result sections do not match the supplied boundary"
        )
    repaired_section = (
        boundary_result.previous_section
        if issue.affected_section_id == boundary_result.previous_section.id
        else boundary_result.next_section
    )
    if repaired_section == accepted_section:
        raise WriterRepairRuntimeError("targeted repair did not change the accepted section")
    previous_plan, next_plan = _plan_sections(source, previous_section.id, next_section.id)
    predecessor = await _load_predecessor(
        session,
        predecessor_work_item_id=predecessor_work_item_id,
        accepted_section=accepted_section,
        request=writer_request,
    )
    await _verify_boundary_proof(
        session,
        boundary_work_item_id=boundary_work_item_id,
        run_id=predecessor.run_id,
        source=identity,
        boundary_result=boundary_result,
    )
    replacement = _validated_result(request=writer_request, section=repaired_section)
    if replacement.section_slot_id != issue.affected_section_id:
        raise WriterRepairRuntimeError("targeted repair result is bound to the wrong section")
    if issue.affected_section_id == previous_section.id:
        if next_section != boundary_result.next_section:
            raise WriterRepairRuntimeError("healthy boundary sibling changed during repair")
        boundary_previous, boundary_next = repaired_section, next_section
    else:
        if previous_section != boundary_result.previous_section:
            raise WriterRepairRuntimeError("healthy boundary sibling changed during repair")
        boundary_previous, boundary_next = previous_section, repaired_section
    # Admission repeats deterministic checks against the exact changed output.
    if validate_section_boundary(
        previous_section=boundary_previous,
        previous_plan=previous_plan,
        next_section=boundary_next,
        next_plan=next_plan,
    ):
        raise WriterRepairRuntimeError("targeted repair does not pass boundary revalidation")
    target_plan = previous_plan if issue.affected_section_id == previous_section.id else next_plan
    if validate_section_continuity(
        section=repaired_section,
        teaching_plan_section=target_plan,
        expected_nodes=_expected_shapes(writer_request),
    ):
        raise WriterRepairRuntimeError("targeted repair does not pass section revalidation")
    work = WriterRepairWorkOrder(
        source=identity,
        section_id=issue.affected_section_id,
        composition_identity=_stable_hash(writer_request.composition_plan.model_dump(mode="json")),
        prior_writer_work_item_id=predecessor.id,
        prior_writer_output_hash=predecessor.output_hash,
        boundary_work_item_id=boundary_work_item_id,
        accepted_section_output_hash=accepted_section_output_hash(accepted_section),
        issue=issue,
        previous_section=previous_section,
        next_section=next_section,
        replacement=replacement,
    )
    request = WorkItemReplacement(
        predecessor_work_item_id=predecessor.id,
        owner_user_id=owner_user_id,
        source=identity,
        replacement=WorkItemAdmission(
            run_id=predecessor.run_id,
            item_key=f"write:{work.section_id}:boundary-repair:{work.identity_hash[:24]}",
            stage=WRITER_REPAIR_STAGE,
            input_hash=_repair_input_hash(work),
            definition_hash=_stable_hash(WRITER_REPAIR_DEFINITION),
            composition_identity=work.composition_identity,
            max_attempts=max_attempts,
        ),
    )
    item = await replace_work_item(session, request)
    return WriterRepairAdmission(item=item, work=work)


def _checkpoint_compatibility(
    *, source: SourceIdentity, item: GenerationWorkItemModel
) -> RuntimeCheckpointCompatibility:
    return RuntimeCheckpointCompatibility(
        schema_version=1,
        source_revision=source.source_revision,
        source_hash=source.source_hash,
        input_hash=item.input_hash,
        definition_hash=item.definition_hash,
        composition_identity=item.composition_identity,
    )


def _validate_checkpoint(payload: Any, work: WriterRepairWorkOrder) -> SectionWriteResult:
    if not isinstance(payload, Mapping) or payload.get("kind") != "shared_lesson_writer_repair":
        raise WriterRepairCheckpointError("targeted repair checkpoint has an unsupported shape")
    if payload.get("work") != work.model_dump(mode="json"):
        raise WriterRepairCheckpointError("targeted repair checkpoint is stale or conflicting")
    try:
        return SectionWriteResult.model_validate(payload["work"]["replacement"])
    except (TypeError, ValueError) as exc:
        raise WriterRepairCheckpointError("targeted repair checkpoint output is invalid") from exc


def _logical_key(item: Any, by_id: Mapping[str, Any]) -> str:
    current = item
    seen: set[str] = set()
    while current.replaces_work_item_id is not None:
        if current.id in seen:
            raise WriterRepairSourceConflict("writer replacement chain contains a cycle")
        seen.add(current.id)
        current = by_id.get(current.replaces_work_item_id)
        if current is None:
            raise WriterRepairSourceConflict("writer replacement chain has a missing predecessor")
    return current.item_key


async def _active_boundary_sections(
    session: Any,
    *,
    run_id: str,
    item: GenerationWorkItemModel,
    work: WriterRepairWorkOrder,
) -> tuple[SharedSection, SharedSection]:
    """Reload the live sibling before commit so a concurrent repair is stale."""
    rows = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel).where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == WRITER_REPAIR_STAGE,
                )
            )
        ).all()
    )
    by_id = {row.id: row for row in rows}
    leaves = active_work_items(rows)
    if item.id not in {row.id for row in leaves}:
        raise WriterRepairSourceConflict("targeted repair is no longer the active writer leaf")
    by_key = {_logical_key(row, by_id): row for row in leaves}

    def load(section: SharedSection) -> SharedSection:
        row = by_key.get(f"write:{section.id}")
        if row is None or row.id == item.id or row.status != "ready":
            raise WriterRepairSourceConflict(
                f"active writer sibling for {section.id!r} is unavailable"
            )
        if row.output_json is None or not row.output_hash:
            raise WriterRepairSourceConflict(
                f"active writer sibling for {section.id!r} has no output"
            )
        if content_hash(row.output_json) != row.output_hash:
            raise WriterRepairSourceConflict(
                f"active writer sibling for {section.id!r} has an invalid hash"
            )
        try:
            result = SectionWriteResult.model_validate(row.output_json)
        except (TypeError, ValueError) as exc:
            raise WriterRepairSourceConflict(
                f"active writer sibling for {section.id!r} is invalid"
            ) from exc
        accepted = result.as_shared_section(section_id=section.id, position=section.position)
        if accepted_section_output_hash(accepted) != accepted_section_output_hash(section):
            raise WriterRepairSourceConflict(f"active writer sibling for {section.id!r} changed")
        return accepted

    target = _as_section(
        work.replacement,
        position=(
            work.previous_section.position
            if work.section_id == work.previous_section.id
            else work.next_section.position
        ),
    )
    if work.section_id == work.previous_section.id:
        previous, next_section = target, load(work.next_section)
    else:
        previous, next_section = load(work.previous_section), target
    return previous, next_section


async def execute_writer_repair_work_item(
    job: WriterRepairWorkItemJob,
    *,
    now: Any = None,
) -> WriterRepairOutcome:
    """Claim, revalidate, checkpoint and fenced-commit one repair output."""
    identity = _identity(job.source)
    if identity != job.work.source:
        raise WriterRepairSourceConflict("repair source differs from its immutable work order")
    item = await claim_work_item(
        job.session,
        work_item_id=job.work_item_id,
        worker_id=job.worker_id,
        source=identity,
        lease_seconds=job.lease_seconds,
        now=now,
    )
    try:
        if item.stage != WRITER_REPAIR_STAGE or item.input_hash != _repair_input_hash(job.work):
            raise WriterRepairCheckpointError("repair work item identity is stale")
        if item.composition_identity != job.work.composition_identity:
            raise WriterRepairCheckpointError("repair work item composition identity is stale")
        compatibility = _checkpoint_compatibility(source=identity, item=item)
        checkpoint = await load_compatible_checkpoint(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            compatibility=compatibility,
            now=now,
        )
        result = (
            _validate_checkpoint(checkpoint.payload, job.work)
            if checkpoint is not None
            else job.work.replacement
        )
        if result != job.work.replacement:
            raise WriterRepairCheckpointError("repair output differs from its immutable work order")
        # Re-run the closed writer validator before durable commit.
        repaired = _as_section(
            result,
            position=(
                job.work.previous_section.position
                if job.work.previous_section.id == job.work.section_id
                else job.work.next_section.position
            ),
        )
        _validated_result(request=job.writer_request, section=repaired)
        if not isinstance(job.source, TeachingPlanSource):
            raise WriterRepairSourceConflict(
                "boundary revalidation requires the approved source snapshot"
            )
        previous_plan, next_plan = _plan_sections(
            job.source, job.work.previous_section.id, job.work.next_section.id
        )
        previous_active, next_active = await _active_boundary_sections(
            job.session,
            run_id=item.run_id,
            item=item,
            work=job.work,
        )
        if validate_section_boundary(
            previous_section=previous_active,
            previous_plan=previous_plan,
            next_section=next_active,
            next_plan=next_plan,
        ):
            raise WriterRepairSourceConflict("active writer output failed boundary revalidation")
        target_plan = (
            previous_plan if job.work.section_id == job.work.previous_section.id else next_plan
        )
        if validate_section_continuity(
            section=repaired,
            teaching_plan_section=target_plan,
            expected_nodes=_expected_shapes(job.writer_request),
        ):
            raise WriterRepairSourceConflict("active writer output failed section revalidation")
        if checkpoint is None:
            await persist_checkpoint(
                job.session,
                work_item_id=item.id,
                worker_id=job.worker_id,
                lease_token=item.lease_token or 0,
                compatibility=compatibility,
                payload={
                    "kind": "shared_lesson_writer_repair",
                    "work": job.work.model_dump(mode="json"),
                },
                now=now,
            )
    except LeaseLostError:
        raise
    except Exception as exc:  # noqa: BLE001 - convert only bounded runtime failures.
        failure = WorkItemFailure(
            error_code=(
                "writer_repair_checkpoint_integrity"
                if isinstance(exc, WriterRepairCheckpointError)
                else "writer_repair_source_conflict"
                if isinstance(exc, WriterRepairSourceConflict)
                else "writer_repair_validation_failed"
            ),
            error_class=(
                ErrorClass.UNSUPPORTED_CONTRACT
                if isinstance(exc, WriterRepairCheckpointError)
                else ErrorClass.SOURCE_CONFLICT
                if isinstance(exc, WriterRepairSourceConflict)
                else ErrorClass.PROVIDER_OUTPUT
            ),
            safe_summary="Targeted writer repair failed its closed contract or source revalidation.",
            recovery_action=RecoveryAction.NONE,
        )
        await fail_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            failure=failure,
            now=now,
        )
        return WriterRepairOutcome(
            work_item_id=item.id,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
        )
    await complete_work_item(
        job.session,
        work_item_id=item.id,
        worker_id=job.worker_id,
        lease_token=item.lease_token or 0,
        output_json=result.model_dump(mode="json"),
        output_hash=content_hash(result.model_dump(mode="json")),
        now=now,
    )
    return WriterRepairOutcome(work_item_id=item.id, result=result)


__all__ = [
    "WRITER_REPAIR_DEFINITION",
    "WRITER_REPAIR_STAGE",
    "WriterRepairAdmission",
    "WriterRepairCheckpointError",
    "WriterRepairOutcome",
    "WriterRepairRuntimeError",
    "WriterRepairSourceConflict",
    "WriterRepairWorkItemJob",
    "WriterRepairWorkOrder",
    "admit_writer_repair_work_item",
    "execute_writer_repair_work_item",
]
