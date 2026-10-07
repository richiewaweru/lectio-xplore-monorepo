"""Durable execution of an admitted SharedDocument sourcebook WorkItem.

Sourcebook admission is owned by :mod:`semantic_inputs`.  This module only
executes that already admitted item through the generic runtime.  The exact
approved Teaching Plan identity is checked against the persisted source by an
injected ``SourceVerifier`` before dispatch and again before completion.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select

from curriculum.lesson_sourcebook import LessonSourcebook, validate_sourcebook
from curriculum.shared_sourcebook_authoring import (
    SharedSourcebookAuthoringError,
    author_shared_sourcebook,
)
from document.shared_lesson.runtime import (
    SectionRuntimeError,
    TeachingPlanSource,
    _stable_hash,
    verify_teaching_plan_source,
)
from document.shared_lesson.semantic_inputs import (
    SOURCEBOOK_DEFINITION,
    SOURCEBOOK_ITEM_KEY,
    SOURCEBOOK_STAGE,
    SemanticInputError,
    _sourcebook_input_hash,
    _validate_sourcebook,
)
from infra.authoring import AuthoringEngine, AuthoringEngineError, AuthoringProvider
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.execution.leases import LeaseLostError
from infra.llm.runner import is_provider_request_rejected, is_retryable_provider_error
from infra.generation_runtime import (
    ErrorClass,
    RecoveryAction,
    RuntimeCheckpointCompatibility,
    SourceIdentity,
    SourceVerificationError,
    WorkItemFailure,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
)
from infra.generation_runtime.repository import SourceVerifier


class SourcebookRuntimeError(ValueError):
    """The sourcebook execution request is invalid or stale."""


class SourcebookSourceConflict(SourcebookRuntimeError):
    """The persisted approved source no longer matches this WorkItem."""


class SourcebookCheckpointError(SourcebookRuntimeError):
    """A sourcebook checkpoint cannot safely be reused."""


class SourcebookProviderOutputError(SourcebookRuntimeError):
    """The provider did not satisfy the sourcebook semantic contract."""


class SourcebookRuntimeOutcome(BaseModel):
    """Safe projection of one bounded sourcebook attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: str
    sourcebook: LessonSourcebook | None = None
    error_code: str | None = None
    error_summary: str | None = None
    preserved_ready: bool = False


@dataclass(frozen=True)
class SourcebookWorkItemJob:
    """Inputs for one already-admitted sourcebook WorkItem."""

    session: Any
    work_item_id: str
    worker_id: str
    source: TeachingPlanSource
    provider: AuthoringProvider | None = None
    engine: AuthoringEngine | None = None
    source_verifier: SourceVerifier | None = None
    owner_user_id: str | None = None
    status: str = "queued"
    lease_seconds: int = 300


def _identity(source: TeachingPlanSource) -> SourceIdentity:
    if not isinstance(source, TeachingPlanSource):
        raise SourcebookSourceConflict(
            "sourcebook execution requires an approved TeachingPlanSource"
        )
    try:
        return verify_teaching_plan_source(source)
    except SectionRuntimeError as exc:
        raise SourcebookSourceConflict("approved Teaching Plan source is invalid") from exc


def _definition_hash() -> str:
    return _stable_hash(SOURCEBOOK_DEFINITION)


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


def _checkpoint_payload(
    source: TeachingPlanSource, item: GenerationWorkItemModel
) -> dict[str, Any]:
    return {
        "kind": "shared_sourcebook",
        "source_artifact_type": "teaching_plan",
        "source_artifact_id": source.id,
        "source_revision": source.revision,
        "source_hash": source.content_hash,
        "input_hash": item.input_hash,
        "definition_hash": item.definition_hash,
    }


def _validate_checkpoint_payload(
    payload: Any, *, source: TeachingPlanSource, item: GenerationWorkItemModel
) -> None:
    expected = _checkpoint_payload(source, item)
    if payload != expected:
        raise SourcebookCheckpointError("sourcebook checkpoint is stale or conflicting")


def _validate_item_binding(item: GenerationWorkItemModel, source: TeachingPlanSource) -> None:
    expected_input = _sourcebook_input_hash(source)
    if (
        item.item_key != SOURCEBOOK_ITEM_KEY
        or item.stage != SOURCEBOOK_STAGE
        or item.input_hash != expected_input
        or item.definition_hash != _definition_hash()
        or item.composition_identity is not None
    ):
        raise SourcebookSourceConflict(
            "sourcebook WorkItem is bound to a different source or definition"
        )


async def _verify_persisted_source(
    session: Any,
    *,
    verifier: SourceVerifier | None,
    requested: SourceIdentity,
) -> SourceIdentity:
    if verifier is None:
        raise SourceVerificationError("sourcebook execution requires an injected SourceVerifier")
    observed = verifier(session, requested)
    if inspect.isawaitable(observed):
        observed = await observed
    try:
        identity = (
            observed
            if isinstance(observed, SourceIdentity)
            else SourceIdentity.model_validate(observed)
        )
    except (TypeError, ValueError) as exc:
        raise SourceVerificationError(
            "approved source verifier returned an invalid identity"
        ) from exc
    if identity != requested:
        raise SourcebookSourceConflict("persisted approved source differs from the admitted source")
    return identity


def _failure_for_exception(exc: Exception) -> WorkItemFailure:
    """Classify provider failures without semantic fallback."""
    if isinstance(exc, (SourcebookProviderOutputError, ValidationError)):
        return WorkItemFailure(
            error_code="sourcebook_invalid_output",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary="Sourcebook provider output failed the shared semantic contract.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, AuthoringEngineError):
        if exc.code in {"REPAIR_EXHAUSTED", "INVALID_PAYLOAD"}:
            return WorkItemFailure(
                error_code="sourcebook_invalid_output",
                error_class=ErrorClass.PROVIDER_OUTPUT,
                safe_summary="Sourcebook provider output failed the shared semantic contract.",
                recovery_action=RecoveryAction.RETRY,
            )
        if exc.code == "PROVIDER_TRANSPORT_EXHAUSTED":
            return WorkItemFailure(
                error_code="sourcebook_provider_transport",
                error_class=ErrorClass.PROVIDER_TRANSPORT,
                safe_summary="Sourcebook provider transport failed.",
                recovery_action=RecoveryAction.RETRY,
            )
        # Authentication, configuration, missing capability, and exhausted
        # budget are terminal.  They never get semantic fallback.
        return WorkItemFailure(
            error_code="sourcebook_provider_terminal",
            error_class=ErrorClass.INTERNAL_PROGRAMMING,
            safe_summary="Sourcebook provider configuration or authorization failed.",
            recovery_action=RecoveryAction.NONE,
        )
    if isinstance(exc, (TimeoutError, ConnectionError)) or is_retryable_provider_error(exc):
        return WorkItemFailure(
            error_code="sourcebook_provider_transport",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="Sourcebook provider transport failed.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, (SourcebookSourceConflict, SourceVerificationError)):
        return WorkItemFailure(
            error_code="sourcebook_source_conflict",
            error_class=ErrorClass.SOURCE_CONFLICT,
            safe_summary="The persisted approved source changed or could not be verified.",
            recovery_action=RecoveryAction.NONE,
        )
    if isinstance(exc, SourcebookCheckpointError):
        return WorkItemFailure(
            error_code="sourcebook_checkpoint_integrity",
            error_class=ErrorClass.UNSUPPORTED_CONTRACT,
            safe_summary="Sourcebook checkpoint failed compatibility or integrity validation.",
            recovery_action=RecoveryAction.NONE,
        )
    if isinstance(exc, SharedSourcebookAuthoringError):
        return WorkItemFailure(
            error_code="sourcebook_plan_contract",
            error_class=ErrorClass.UNSUPPORTED_CONTRACT,
            safe_summary=(
                "The approved Teaching Plan has sourcebook needs without approved references."
            ),
            recovery_action=RecoveryAction.NONE,
        )
    if is_provider_request_rejected(exc):
        return WorkItemFailure(
            error_code="sourcebook_provider_request_rejected",
            error_class=ErrorClass.UNSUPPORTED_CONTRACT,
            safe_summary="Sourcebook provider rejected the request.",
            recovery_action=RecoveryAction.NONE,
        )
    return WorkItemFailure(
        error_code="sourcebook_runtime_error",
        error_class=ErrorClass.INTERNAL_PROGRAMMING,
        safe_summary="Sourcebook execution failed unexpectedly.",
        recovery_action=RecoveryAction.NONE,
    )


async def _fail_after_claim(
    job: SourcebookWorkItemJob,
    item: GenerationWorkItemModel,
    exc: Exception,
    *,
    now: Any = None,
) -> SourcebookRuntimeOutcome:
    failure = _failure_for_exception(exc)
    await fail_work_item(
        job.session,
        work_item_id=item.id,
        worker_id=job.worker_id,
        lease_token=item.lease_token or 0,
        failure=failure,
        now=now,
    )
    return SourcebookRuntimeOutcome(
        work_item_id=item.id,
        error_code=failure.error_code,
        error_summary=failure.safe_summary,
    )


async def execute_sourcebook_work_item(
    job: SourcebookWorkItemJob,
    *,
    source_verifier: SourceVerifier | None = None,
    now: Any = None,
) -> SourcebookRuntimeOutcome:
    """Claim, author, validate, and fenced-commit one sourcebook item."""
    if job.status == "ready":
        identity = _identity(job.source)
        verifier = source_verifier or job.source_verifier
        await _verify_persisted_source(job.session, verifier=verifier, requested=identity)
        persisted = await job.session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.id == job.work_item_id)
        )
        if persisted is None or persisted.status != "ready":
            raise SourcebookRuntimeError("sourcebook item is not durably ready")
        run = await job.session.scalar(
            select(GenerationRunModel).where(GenerationRunModel.id == persisted.run_id)
        )
        if run is None or run.run_type != "shared_document":
            raise SourcebookRuntimeError("ready sourcebook item belongs to an unavailable Run")
        if job.owner_user_id is not None and run.owner_user_id != job.owner_user_id:
            raise SourcebookRuntimeError("ready sourcebook item belongs to a different owner")
        if (
            run.source_artifact_type,
            run.source_artifact_id,
            run.source_revision,
            run.source_hash,
        ) != (
            identity.source_artifact_type,
            identity.source_artifact_id,
            identity.source_revision,
            identity.source_hash,
        ):
            raise SourcebookSourceConflict(
                "ready sourcebook item source differs from the admitted source"
            )
        _validate_item_binding(persisted, job.source)
        if persisted.output_json is None or not persisted.output_hash:
            raise SourcebookRuntimeError("ready sourcebook item has no complete output")
        if content_hash(persisted.output_json) != persisted.output_hash:
            raise SourcebookRuntimeError("ready sourcebook output hash is invalid")
        try:
            ready_sourcebook = LessonSourcebook.model_validate(persisted.output_json)
            _validate_sourcebook(job.source, ready_sourcebook)
        except (TypeError, ValueError, SemanticInputError) as exc:
            raise SourcebookRuntimeError(
                "ready sourcebook output violates its approved contract"
            ) from exc
        return SourcebookRuntimeOutcome(work_item_id=job.work_item_id, preserved_ready=True)
    if job.status != "queued":
        raise SourcebookRuntimeError("sourcebook execution accepts queued items only")

    identity = _identity(job.source)
    verifier = source_verifier or job.source_verifier
    # Verify the durable approved source before acquiring a provider lease.
    await _verify_persisted_source(job.session, verifier=verifier, requested=identity)
    item = await claim_work_item(
        job.session,
        work_item_id=job.work_item_id,
        worker_id=job.worker_id,
        source=identity,
        lease_seconds=job.lease_seconds,
        now=now,
    )
    try:
        _validate_item_binding(item, job.source)
        compatibility = _checkpoint_compatibility(source=identity, item=item)
        checkpoint = await load_compatible_checkpoint(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            compatibility=compatibility,
            now=now,
        )
        if checkpoint is None:
            await persist_checkpoint(
                job.session,
                work_item_id=item.id,
                worker_id=job.worker_id,
                lease_token=item.lease_token or 0,
                compatibility=compatibility,
                payload=_checkpoint_payload(job.source, item),
                now=now,
            )
        else:
            _validate_checkpoint_payload(checkpoint.payload, source=job.source, item=item)
        await _verify_persisted_source(job.session, verifier=verifier, requested=identity)
        # The provider call may block on a network round trip.  Commit the
        # durable claim/checkpoint first so a process crash cannot lose the
        # recoverability record while that call is in flight.
        commit = getattr(job.session, "commit", None)
        if commit is None:
            raise SourcebookRuntimeError("sourcebook execution requires a session commit boundary")
        result = commit()
        if inspect.isawaitable(result):
            await result
    except LeaseLostError:
        raise
    except Exception as exc:  # noqa: BLE001 - persist a typed failure after claim.
        return await _fail_after_claim(job, item, exc, now=now)

    try:
        sourcebook = await author_shared_sourcebook(
            job.source.plan,
            expected_teaching_plan_hash=job.source.content_hash,
            provider=job.provider,
            engine=job.engine,
            work_order_id=f"sourcebook:{item.id}",
            trace_id=item.run_id,
        )
        if (
            sourcebook.teaching_plan_id,
            sourcebook.teaching_plan_revision,
            sourcebook.teaching_plan_hash,
        ) != (job.source.id, job.source.revision, job.source.content_hash):
            raise SourcebookProviderOutputError(
                "sourcebook output is bound to a stale Teaching Plan"
            )
        validation_errors = validate_sourcebook(sourcebook)
        if validation_errors:
            raise SourcebookProviderOutputError("; ".join(validation_errors))
    except LeaseLostError:
        raise
    except Exception as exc:  # noqa: BLE001 - classify bounded provider failures.
        return await _fail_after_claim(job, item, exc, now=now)

    # A source can be replaced while the provider is running.  Rechecking the
    # trusted source immediately before completion prevents stale output from
    # crossing the generic runtime fence.
    try:
        await _verify_persisted_source(job.session, verifier=verifier, requested=identity)
        output = sourcebook.model_dump(mode="json")
        await complete_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            output_json=output,
            output_hash=content_hash(output),
            now=now,
        )
    except LeaseLostError:
        raise
    except Exception as exc:  # noqa: BLE001 - preserve failure under the live fence.
        return await _fail_after_claim(job, item, exc, now=now)
    return SourcebookRuntimeOutcome(work_item_id=item.id, sourcebook=sourcebook)


__all__ = [
    "SOURCEBOOK_DEFINITION",
    "SOURCEBOOK_ITEM_KEY",
    "SOURCEBOOK_STAGE",
    "SourcebookCheckpointError",
    "SourcebookProviderOutputError",
    "SourcebookRuntimeError",
    "SourcebookRuntimeOutcome",
    "SourcebookSourceConflict",
    "SourcebookWorkItemJob",
    "execute_sourcebook_work_item",
]
