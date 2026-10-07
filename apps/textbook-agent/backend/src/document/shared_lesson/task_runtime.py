"""Durable execution of an admitted SharedDocument task WorkItem.

Shared tasks depend on two immutable semantic inputs: the accepted sourcebook
leaf and the approved item snapshot pinned by the Teaching Plan revision.  The
runtime owns only execution of an already-admitted generic WorkItem; admission
and final semantic reload remain in :mod:`semantic_inputs`.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select

from curriculum.shared_task_authoring import (
    ApprovedItemSnapshot,
    SharedTaskAuthoringError,
    approved_item_snapshot_hash,
    author_shared_tasks,
)
from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.revisions import read_approved_item_snapshot
from document.shared_lesson.runtime import (
    SectionRuntimeError,
    TeachingPlanSource,
    _stable_hash,
    verify_teaching_plan_source,
)
from document.shared_lesson.semantic_inputs import (
    TASK_DEFINITION,
    TASK_ITEM_KEY,
    TASK_STAGE,
    SemanticInputError,
    _task_input_hash,
    _validate_tasks,
    load_verified_sourcebook_input,
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
    append_event,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
)
from infra.generation_runtime.repository import SourceVerifier


class SharedTaskRuntimeError(ValueError):
    """The task execution request is invalid or stale."""


class SharedTaskSourceConflict(SharedTaskRuntimeError):
    """The approved source, snapshot, or sourcebook changed."""


class SharedTaskCheckpointError(SharedTaskRuntimeError):
    """A task checkpoint cannot safely be reused."""


class SharedTaskProviderOutputError(SharedTaskRuntimeError):
    """The task provider did not satisfy the closed semantic contract."""


_SAFE_VALIDATION_FIELDS = frozenset(
    {
        "tasks",
        "prompt",
        "response",
        "evaluation",
        "feedback",
        "expected_evidence",
        "difficulty",
        "type",
        "options",
        "id",
        "key",
        "text",
        "answer_lines",
        "items",
        "correct_order",
        "order",
        "values",
        "answers",
        "categories",
        "correct_placements",
        "pairs",
        "left",
        "right",
        "correct_option_id",
        "correct_option_ids",
        "correct_key",
        "correct_keys",
        "accepted_answers",
        "criteria",
        "rubric",
        "value",
        "tolerance",
        "unit",
        "review_guidance",
    }
)


def _safe_validation_path(path: str) -> str:
    """Keep only schema field names and numeric indices from validator paths."""
    parts = re.split(r"[.\[\]]+", path)
    safe_parts = [
        part if part.isdigit() or part in _SAFE_VALIDATION_FIELDS else "field"
        for part in parts[:12]
        if part
    ]
    return ".".join(safe_parts) or "payload"


def _safe_authoring_diagnostics(exc: AuthoringEngineError) -> dict[str, Any]:
    issue_codes = sorted({_safe_validation_issue_code(error) for error in exc.errors})
    failure_kinds = {code.partition("_")[0] for code in issue_codes}
    failure_kind = (
        next(iter(failure_kinds))
        if len(failure_kinds) == 1
        else "mixed" if failure_kinds else "unknown"
    )
    return {
        "error_code": exc.code,
        "exception_type": type(exc).__name__,
        "failure_kind": failure_kind,
        "validation_issue_codes": issue_codes,
        "validation_paths": sorted(
            {_safe_validation_path(error.path) for error in exc.errors}
        ),
    }


def _safe_validation_issue_code(error: Any) -> str:
    """Project validator text onto a closed diagnostic vocabulary.

    Messages can contain provider text, learner content, task IDs, or approved
    source text. Inspect them only to select a fixed code; never persist them.
    """
    message = str(getattr(error, "message", "")).strip()
    normalized = message.lower()

    if any(
        normalized.startswith(prefix)
        for prefix in (
            "expecting value",
            "expecting property name enclosed in double quotes",
            "unterminated string",
            "invalid \\escape",
            "invalid control character",
            "extra data",
        )
    ) or "could not be parsed" in normalized:
        return "parse_invalid_json"

    if message == "required":
        return "schema_required_field_missing"
    if message == "unexpected property":
        return "schema_unexpected_property"
    if normalized.startswith("expected "):
        return "schema_value_mismatch"
    if normalized.startswith(("minlength ", "minitems ", "maxitems ")):
        return "schema_constraint_violation"
    if message == "duplicate item":
        return "schema_duplicate_item"

    for feedback_code in (
        "feedback_unknown_option",
        "feedback_on_correct_option",
        "feedback_missing_wrong_option",
        "feedback_unknown_item",
        "feedback_blank",
    ):
        if feedback_code in normalized:
            return f"semantic_{feedback_code}"

    if "provider must return exactly" in normalized:
        return "semantic_task_count_mismatch"
    if "expected_evidence must match" in normalized:
        return "semantic_approved_evidence_mismatch"
    if "difficulty must match" in normalized:
        return "semantic_approved_difficulty_mismatch"
    if "failed canonical model validation" in normalized:
        return "semantic_task_model_invalid"
    if "failed the closed semantic contract" in normalized:
        return "semantic_contract_violation"

    semantic_markers = (
        ("uses an unsupported learner action", "semantic_action_unsupported"),
        ("requires response type", "semantic_response_type_mismatch"),
        ("response contains unsupported fields", "semantic_response_fields_unsupported"),
        ("choice response requires at least two options", "semantic_choice_options_missing"),
        ("choice options require unique ids", "semantic_choice_options_invalid"),
        ("choice option ids must be unique", "semantic_choice_option_ids_duplicate"),
        ("single-choice evaluation requires", "semantic_choice_answer_missing"),
        ("choice evaluation requires", "semantic_choice_answer_missing"),
        ("evaluation references unknown option ids", "semantic_choice_answer_unknown"),
        ("classification response requires", "semantic_classification_field_missing"),
        ("placements must cover every classified item", "semantic_classification_coverage_mismatch"),
        ("placements reference undeclared categories", "semantic_classification_category_unknown"),
        ("mapping evaluation must preserve correct_placements", "semantic_classification_evaluation_mismatch"),
        ("matching response requires", "semantic_matching_pairs_invalid"),
        ("ordered response requires", "semantic_ordered_items_invalid"),
        ("answer order must contain exactly", "semantic_ordered_answer_mismatch"),
        ("missing-values response requires", "semantic_missing_values_invalid"),
        ("evaluation must use a supported semantic type", "semantic_evaluation_type_unsupported"),
        ("evaluation contains unsupported fields", "semantic_evaluation_fields_unsupported"),
        ("evaluation type", "semantic_evaluation_type_mismatch"),
        ("evaluation requires meaningful criteria", "semantic_rubric_missing"),
        ("rubric criteria must be meaningful", "semantic_rubric_invalid"),
        ("evaluation requires an answer", "semantic_evaluation_answer_missing"),
        ("evaluation requires correct keys", "semantic_evaluation_keys_missing"),
        ("numeric evaluation requires", "semantic_numeric_answer_invalid"),
        ("numeric tolerance must be finite", "semantic_numeric_tolerance_invalid"),
        ("accepted-answers evaluation requires", "semantic_accepted_answers_missing"),
        ("evaluation must preserve missing-value answers", "semantic_missing_values_answer_mismatch"),
        ("teacher-review evaluation requires", "semantic_review_guidance_missing"),
        ("mapping evaluation requires", "semantic_mapping_answer_missing"),
        ("ordered-match evaluation requires", "semantic_ordered_answer_missing"),
    )
    for marker, issue_code in semantic_markers:
        if marker in normalized:
            return issue_code

    # A root-path, non-JSON error is a provider/schema-envelope failure (for
    # example a structured-output decoder diagnostic). Other unrecognized
    # messages from the task validator are semantic failures. Both are safely
    # categorized without retaining free text.
    if not getattr(error, "path", ""):
        return "schema_payload_invalid"
    return "semantic_contract_violation"


ApprovedItemSnapshotLoader = Callable[
    [Any, str, TeachingPlanSource, SourceIdentity],
    ApprovedItemSnapshot | Awaitable[ApprovedItemSnapshot],
]


class SharedTaskRuntimeOutcome(BaseModel):
    """Safe projection of one bounded shared-task attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: str
    tasks: tuple[SharedTaskSpec, ...] | None = None
    error_code: str | None = None
    error_summary: str | None = None
    preserved_ready: bool = False


@dataclass(frozen=True)
class SharedTaskWorkItemJob:
    """Inputs for one already-admitted shared-task WorkItem."""

    session: Any
    work_item_id: str
    worker_id: str
    source: TeachingPlanSource
    owner_user_id: str
    approved_item_snapshot_loader: ApprovedItemSnapshotLoader | None = None
    provider: AuthoringProvider | None = None
    engine: AuthoringEngine | None = None
    source_verifier: SourceVerifier | None = None
    status: str = "queued"
    lease_seconds: int = 300


def _identity(source: TeachingPlanSource) -> SourceIdentity:
    if not isinstance(source, TeachingPlanSource):
        raise SharedTaskSourceConflict(
            "shared-task execution requires an approved TeachingPlanSource"
        )
    try:
        return verify_teaching_plan_source(source)
    except SectionRuntimeError as exc:
        raise SharedTaskSourceConflict("approved Teaching Plan source is invalid") from exc


def _definition_hash() -> str:
    return _stable_hash(TASK_DEFINITION)


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
    source: TeachingPlanSource,
    item: GenerationWorkItemModel,
    *,
    sourcebook_output_hash: str,
    approved_item_snapshot_hash_value: str,
) -> dict[str, Any]:
    return {
        "kind": "shared_tasks",
        "source_artifact_type": "teaching_plan",
        "source_artifact_id": source.id,
        "source_revision": source.revision,
        "source_hash": source.content_hash,
        "sourcebook_output_hash": sourcebook_output_hash,
        "approved_item_snapshot_hash": approved_item_snapshot_hash_value,
        "input_hash": item.input_hash,
        "definition_hash": item.definition_hash,
        "composition_identity": item.composition_identity,
    }


def _validate_checkpoint_payload(
    payload: Any,
    *,
    source: TeachingPlanSource,
    item: GenerationWorkItemModel,
    sourcebook_output_hash: str,
    approved_item_snapshot_hash_value: str,
) -> None:
    expected = _checkpoint_payload(
        source,
        item,
        sourcebook_output_hash=sourcebook_output_hash,
        approved_item_snapshot_hash_value=approved_item_snapshot_hash_value,
    )
    if payload != expected:
        raise SharedTaskCheckpointError("shared-task checkpoint is stale or conflicting")


def _validate_item_binding(
    item: GenerationWorkItemModel,
    source: TeachingPlanSource,
    *,
    sourcebook_output_hash: str,
    approved_item_snapshot_hash_value: str,
) -> None:
    expected_input = _task_input_hash(
        source,
        sourcebook_output_hash,
        approved_item_snapshot_hash_value,
    )
    if (
        item.item_key != TASK_ITEM_KEY
        or item.stage != TASK_STAGE
        or item.input_hash != expected_input
        or item.definition_hash != _definition_hash()
        or item.composition_identity != sourcebook_output_hash
    ):
        raise SharedTaskSourceConflict(
            "shared-task WorkItem is bound to a different source, snapshot, or sourcebook"
        )


async def _verify_persisted_source(
    session: Any,
    *,
    verifier: SourceVerifier | None,
    requested: SourceIdentity,
) -> SourceIdentity:
    if verifier is None:
        raise SourceVerificationError("shared-task execution requires an injected SourceVerifier")
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
        raise SharedTaskSourceConflict("persisted approved source differs from the admitted source")
    return identity


async def _load_snapshot(
    job: SharedTaskWorkItemJob,
    *,
    identity: SourceIdentity,
) -> tuple[ApprovedItemSnapshot, str]:
    loader = job.approved_item_snapshot_loader
    if loader is None:
        raise SourceVerificationError(
            "shared-task execution requires an injected approved-item snapshot loader"
        )
    value = loader(job.session, job.owner_user_id, job.source, identity)
    if inspect.isawaitable(value):
        value = await value
    try:
        snapshot = (
            value
            if isinstance(value, ApprovedItemSnapshot)
            else ApprovedItemSnapshot.model_validate(value)
        )
        expected = ApprovedItemSnapshot.model_validate(
            read_approved_item_snapshot(job.source.revision_record)
        )
        expected_hash = approved_item_snapshot_hash(expected)
        observed_hash = approved_item_snapshot_hash(snapshot)
    except (TypeError, ValueError) as exc:
        raise SharedTaskSourceConflict(
            "persisted approved item snapshot is unavailable or invalid"
        ) from exc
    if observed_hash != expected_hash:
        raise SharedTaskSourceConflict(
            "persisted approved item snapshot differs from the approved revision"
        )
    if job.source.revision_record.approved_item_snapshot_hash != expected_hash:
        raise SharedTaskSourceConflict(
            "approved item snapshot hash differs from its revision record"
        )
    if (
        snapshot.teaching_plan_id,
        snapshot.teaching_plan_revision,
        snapshot.teaching_plan_hash,
    ) != (
        identity.source_artifact_id,
        identity.source_revision,
        identity.source_hash,
    ):
        raise SharedTaskSourceConflict(
            "approved item snapshot is bound to a different Teaching Plan revision"
        )
    return snapshot, observed_hash


async def _load_sourcebook(
    job: SharedTaskWorkItemJob,
    *,
    run_id: str,
) -> tuple[Any, str]:
    try:
        verified = await load_verified_sourcebook_input(
            job.session,
            run_id=run_id,
            owner_user_id=job.owner_user_id,
            source=job.source,
        )
    except (SemanticInputError, SharedTaskRuntimeError) as exc:
        raise SharedTaskSourceConflict(
            "active READY sourcebook could not be verified for shared tasks"
        ) from exc
    return verified.sourcebook, verified.sourcebook_output_hash


async def _load_item_run_id(session: Any, work_item_id: str) -> str:
    item = await session.scalar(
        select(GenerationWorkItemModel).where(GenerationWorkItemModel.id == work_item_id)
    )
    if item is None:
        raise SharedTaskRuntimeError("shared-task WorkItem does not exist")
    return str(item.run_id)


def _failure_for_exception(exc: Exception) -> WorkItemFailure:
    if isinstance(exc, (SharedTaskProviderOutputError, SharedTaskAuthoringError, ValidationError)):
        return WorkItemFailure(
            error_code="shared_task_invalid_output",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary="Shared-task provider output failed the closed semantic contract.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, AuthoringEngineError):
        if exc.code in {"REPAIR_EXHAUSTED", "INVALID_PAYLOAD"}:
            return WorkItemFailure(
                error_code="shared_task_invalid_output",
                error_class=ErrorClass.PROVIDER_OUTPUT,
                safe_summary="Shared-task provider output failed the closed semantic contract.",
                recovery_action=RecoveryAction.RETRY,
            )
        if exc.code == "PROVIDER_TRANSPORT_EXHAUSTED":
            return WorkItemFailure(
                error_code="shared_task_provider_transport",
                error_class=ErrorClass.PROVIDER_TRANSPORT,
                safe_summary="Shared-task provider transport failed.",
                recovery_action=RecoveryAction.RETRY,
            )
        return WorkItemFailure(
            error_code="shared_task_provider_terminal",
            error_class=ErrorClass.INTERNAL_PROGRAMMING,
            safe_summary="Shared-task provider configuration or authorization failed.",
            recovery_action=RecoveryAction.NONE,
        )
    if isinstance(exc, (TimeoutError, ConnectionError)) or is_retryable_provider_error(exc):
        return WorkItemFailure(
            error_code="shared_task_provider_transport",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="Shared-task provider transport failed.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, (SharedTaskSourceConflict, SourceVerificationError)):
        return WorkItemFailure(
            error_code="shared_task_source_conflict",
            error_class=ErrorClass.SOURCE_CONFLICT,
            safe_summary="The persisted approved task inputs changed or could not be verified.",
            recovery_action=RecoveryAction.NONE,
        )
    if isinstance(exc, SharedTaskCheckpointError):
        return WorkItemFailure(
            error_code="shared_task_checkpoint_integrity",
            error_class=ErrorClass.UNSUPPORTED_CONTRACT,
            safe_summary="Shared-task checkpoint failed compatibility or integrity validation.",
            recovery_action=RecoveryAction.NONE,
        )
    if is_provider_request_rejected(exc):
        return WorkItemFailure(
            error_code="shared_task_provider_request_rejected",
            error_class=ErrorClass.UNSUPPORTED_CONTRACT,
            safe_summary="Shared-task provider rejected the request.",
            recovery_action=RecoveryAction.NONE,
        )
    return WorkItemFailure(
        error_code="shared_task_runtime_error",
        error_class=ErrorClass.INTERNAL_PROGRAMMING,
        safe_summary="Shared-task execution failed unexpectedly.",
        recovery_action=RecoveryAction.NONE,
    )


async def _fail_after_claim(
    job: SharedTaskWorkItemJob,
    item: GenerationWorkItemModel,
    exc: Exception,
    *,
    now: Any = None,
) -> SharedTaskRuntimeOutcome:
    failure = _failure_for_exception(exc)
    if isinstance(exc, AuthoringEngineError) and exc.code in {
        "INVALID_PAYLOAD",
        "REPAIR_EXHAUSTED",
    }:
        await append_event(
            job.session,
            run_id=item.run_id,
            work_item_id=item.id,
            event_type="shared_task_validation_failed",
            error_code=exc.code,
            safe_payload=_safe_authoring_diagnostics(exc),
        )
    await fail_work_item(
        job.session,
        work_item_id=item.id,
        worker_id=job.worker_id,
        lease_token=item.lease_token or 0,
        failure=failure,
        now=now,
    )
    return SharedTaskRuntimeOutcome(
        work_item_id=item.id,
        error_code=failure.error_code,
        error_summary=failure.safe_summary,
    )


def _validated_tasks(
    source: TeachingPlanSource,
    sourcebook: Any,
    tasks: Sequence[SharedTaskSpec],
) -> tuple[SharedTaskSpec, ...]:
    raw = [task.model_dump(mode="json") for task in tasks]
    try:
        return _validate_tasks(source, sourcebook, raw)
    except (SemanticInputError, TypeError, ValueError) as exc:
        raise SharedTaskProviderOutputError(
            "shared-task output failed final semantic validation"
        ) from exc


async def execute_shared_task_work_item(
    job: SharedTaskWorkItemJob,
    *,
    source_verifier: SourceVerifier | None = None,
    now: Any = None,
) -> SharedTaskRuntimeOutcome:
    """Claim, author, validate, and fenced-commit one shared-task item."""
    identity = _identity(job.source)
    verifier = source_verifier or job.source_verifier
    await _verify_persisted_source(job.session, verifier=verifier, requested=identity)
    snapshot, snapshot_hash = await _load_snapshot(job, identity=identity)
    run_id = await _load_item_run_id(job.session, job.work_item_id)
    sourcebook, sourcebook_hash = await _load_sourcebook(job, run_id=run_id)

    if job.status == "ready":
        persisted = await job.session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.id == job.work_item_id)
        )
        if persisted is None or persisted.status != "ready":
            raise SharedTaskRuntimeError("shared-task item is not durably ready")
        run = await job.session.scalar(
            select(GenerationRunModel).where(GenerationRunModel.id == persisted.run_id)
        )
        if run is None or run.run_type != "shared_document":
            raise SharedTaskRuntimeError("ready shared-task item belongs to an unavailable Run")
        if run.owner_user_id != job.owner_user_id:
            raise SharedTaskRuntimeError("ready shared-task item belongs to a different owner")
        _validate_item_binding(
            persisted,
            job.source,
            sourcebook_output_hash=sourcebook_hash,
            approved_item_snapshot_hash_value=snapshot_hash,
        )
        if persisted.output_json is None or not persisted.output_hash:
            raise SharedTaskRuntimeError("ready shared-task item has no complete output")
        if content_hash(persisted.output_json) != persisted.output_hash:
            raise SharedTaskRuntimeError("ready shared-task output hash is invalid")
        try:
            tasks = _validated_tasks(
                job.source,
                sourcebook,
                tuple(SharedTaskSpec.model_validate(value) for value in persisted.output_json),
            )
        except (TypeError, ValueError) as exc:
            raise SharedTaskRuntimeError("ready shared-task output violates its contract") from exc
        return SharedTaskRuntimeOutcome(
            work_item_id=job.work_item_id,
            tasks=tasks,
            preserved_ready=True,
        )

    if job.status != "queued":
        raise SharedTaskRuntimeError("shared-task execution accepts queued items only")

    item = await claim_work_item(
        job.session,
        work_item_id=job.work_item_id,
        worker_id=job.worker_id,
        source=identity,
        lease_seconds=job.lease_seconds,
        now=now,
    )
    try:
        _validate_item_binding(
            item,
            job.source,
            sourcebook_output_hash=sourcebook_hash,
            approved_item_snapshot_hash_value=snapshot_hash,
        )
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
                payload=_checkpoint_payload(
                    job.source,
                    item,
                    sourcebook_output_hash=sourcebook_hash,
                    approved_item_snapshot_hash_value=snapshot_hash,
                ),
                now=now,
            )
        else:
            _validate_checkpoint_payload(
                checkpoint.payload,
                source=job.source,
                item=item,
                sourcebook_output_hash=sourcebook_hash,
                approved_item_snapshot_hash_value=snapshot_hash,
            )
        await _verify_persisted_source(job.session, verifier=verifier, requested=identity)
        refreshed_snapshot, refreshed_hash = await _load_snapshot(job, identity=identity)
        if refreshed_hash != snapshot_hash or refreshed_snapshot != snapshot:
            raise SharedTaskSourceConflict(
                "approved item snapshot changed before provider dispatch"
            )
        refreshed_sourcebook, refreshed_sourcebook_hash = await _load_sourcebook(job, run_id=run_id)
        if refreshed_sourcebook_hash != sourcebook_hash or refreshed_sourcebook != sourcebook:
            raise SharedTaskSourceConflict("active sourcebook changed before provider dispatch")
        commit = getattr(job.session, "commit", None)
        if commit is None:
            raise SharedTaskRuntimeError("shared-task execution requires a session commit boundary")
        result = commit()
        if inspect.isawaitable(result):
            await result
    except LeaseLostError:
        raise
    except Exception as exc:  # noqa: BLE001 - persist a typed failure after claim.
        return await _fail_after_claim(job, item, exc, now=now)

    try:
        raw_tasks = await author_shared_tasks(
            job.source.plan,
            sourcebook,
            approved_item_snapshot=snapshot,
            expected_teaching_plan_hash=job.source.content_hash,
            expected_sourcebook_hash=sourcebook_hash,
            provider=job.provider,
            engine=job.engine,
            work_order_id=f"shared-tasks:{item.id}",
            trace_id=item.run_id,
        )
        tasks = _validated_tasks(job.source, sourcebook, raw_tasks)
    except LeaseLostError:
        raise
    except Exception as exc:  # noqa: BLE001 - classify bounded provider failures.
        return await _fail_after_claim(job, item, exc, now=now)

    try:
        await _verify_persisted_source(job.session, verifier=verifier, requested=identity)
        final_snapshot, final_snapshot_hash = await _load_snapshot(job, identity=identity)
        final_sourcebook, final_sourcebook_hash = await _load_sourcebook(job, run_id=run_id)
        if (
            final_snapshot_hash != snapshot_hash
            or final_snapshot != snapshot
            or final_sourcebook_hash != sourcebook_hash
            or final_sourcebook != sourcebook
        ):
            raise SharedTaskSourceConflict("shared-task inputs changed before fenced completion")
        output = [task.model_dump(mode="json") for task in tasks]
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
    return SharedTaskRuntimeOutcome(work_item_id=item.id, tasks=tasks)


__all__ = [
    "ApprovedItemSnapshotLoader",
    "SharedTaskCheckpointError",
    "SharedTaskProviderOutputError",
    "SharedTaskRuntimeError",
    "SharedTaskRuntimeOutcome",
    "SharedTaskSourceConflict",
    "SharedTaskWorkItemJob",
    "execute_shared_task_work_item",
]
