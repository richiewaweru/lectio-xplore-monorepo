"""Durable, section-early media execution for SharedLessonDocument runs.

The stateless :mod:`document.shared_lesson.media` module freezes and validates
one figure.  This module is the thin application boundary around that
contract: it admits a media work item, claims it through the generic runtime,
executes the existing visual provider, and commits a fenced result.  A figure
is therefore independently recoverable while unrelated sections continue
writing.

The work order itself is supplied by the section writer and is also persisted
in the first checkpoint after claim.  The checkpoint is intentionally tied to
the plan, accepted section output, and frozen figure semantic identity.  A
changed section creates a linked replacement work item through the generic
0046 replacement API; the healthy predecessor and all sibling outputs remain
history.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from document.shared_lesson.media import (
    ReadyFigureMediaResult,
    SharedFigureMediaError,
    SharedFigureMediaProviderFailed,
    SharedFigureWorkOrder,
    UnavailableFigureMediaResult,
    bind_generated_figure,
    rebuild_figure_work_order,
    unavailable_figure_result,
)
from curriculum.teaching_plan.models import VisualSpec
from media.generation.provider_errors import (
    is_non_retryable_provider_code,
    safe_summary_for_code,
)
from document.shared_lesson.models import FigureNode, SharedSection
from document.shared_lesson.runtime import (
    TeachingPlanSource,
    rollback_for_failure_record,
    verify_teaching_plan_source,
)
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.execution.leases import LeaseLostError
from infra.generation_runtime import (
    AdmissionResult,
    ErrorClass,
    RecoveryAction,
    RuntimeCheckpointCompatibility,
    SourceIdentity,
    WorkItemAdmission,
    WorkItemFailure,
    WorkItemUnavailable,
    WorkItemReplacement,
    active_work_items,
    add_work_item,
    append_event,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
    replace_work_item,
)
from media.generation.contracts import (
    GeneratedVisualBlock,
    VisualGeneratorWorkOrder,
)

MEDIA_STAGE = "media_generation"
MEDIA_DEFINITION = "shared-figure-media:v1"
MAX_CONCURRENT_MEDIA = 4


class MediaRuntimeError(ValueError):
    """The media runtime received an invalid or unsafe request."""


class MediaSourceConflict(MediaRuntimeError):
    """A work order does not belong to the admitted SharedDocument source."""


class MediaCheckpointError(MediaRuntimeError):
    """A media checkpoint is valid JSON but not the frozen work order."""


class FigureExecutor(Protocol):
    async def execute_figure(
        self, order: VisualGeneratorWorkOrder
    ) -> Sequence[GeneratedVisualBlock]:
        """Execute one work order through the existing media provider."""


class MediaRuntimeOutcome(BaseModel):
    """Serializable result projected by one independent media work item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: str
    media: ReadyFigureMediaResult | None = None
    #: Set when retries were exhausted and the figure was settled as unavailable.
    unavailable: UnavailableFigureMediaResult | None = None
    error_code: str | None = None
    error_summary: str | None = None
    preserved_ready: bool = False


class MediaReadiness(BaseModel):
    """Truthful readiness projection over current media work-item leaves."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ready: bool
    required_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    failed_required_work_item_ids: tuple[str, ...] = ()
    pending_required_work_item_ids: tuple[str, ...] = ()
    pending_required_figure_identities: tuple[str, ...] = ()


@dataclass(frozen=True)
class MediaWorkItemJob:
    """Execution inputs for one already-admitted media work item.

    Each job should own its session.  That keeps SQLite test sessions and
    PostgreSQL worker claims independent while the outer batch still caps
    provider concurrency at four.
    """

    session: Any
    work_item_id: str
    worker_id: str
    source: TeachingPlanSource | SourceIdentity
    work: SharedFigureWorkOrder
    accepted_section: SharedSection
    executor: FigureExecutor
    status: str = "queued"
    lease_seconds: int = 300


def _identity(source: TeachingPlanSource | SourceIdentity) -> SourceIdentity:
    if isinstance(source, TeachingPlanSource):
        return verify_teaching_plan_source(source)
    if isinstance(source, SourceIdentity):
        return source
    raise MediaSourceConflict(
        "media source must be an approved TeachingPlanSource or SourceIdentity"
    )


def _work_identity(work: SharedFigureWorkOrder) -> tuple[str, str, str, str]:
    return (
        work.source_plan_id,
        str(work.source_plan_revision),
        work.source_plan_hash,
        work.section_output_hash,
    )


def _input_hash(work: SharedFigureWorkOrder) -> str:
    return content_hash(work.model_dump(mode="json"))


def _definition_hash() -> str:
    return hashlib.sha256(MEDIA_DEFINITION.encode("utf-8")).hexdigest()


def _composition_identity(work: SharedFigureWorkOrder) -> str:
    # Keep the frozen semantic/spec durable on the generic WorkItem row.  The
    # digest in ``input_hash`` remains the compact equality check; this
    # canonical JSON lets a restarted worker reconstruct and verify the exact
    # accepted media input without consulting an in-memory section writer.
    payload: dict[str, Any] = {
        "source_plan_id": work.source_plan_id,
        "source_plan_revision": work.source_plan_revision,
        "source_plan_hash": work.source_plan_hash,
        "section_id": work.section_id,
        "section_output_hash": work.section_output_hash,
        "figure_node_id": work.figure_node_id,
        "figure_semantic_hash": work.figure_semantic_hash,
        "required": work.required,
        "work_order": work.work_order.model_dump(mode="json"),
    }
    if work.warnings:
        # Warnings are part of ``input_hash``; persisting them (only when
        # present, so existing identities stay byte-identical) lets a
        # reconstructed work order reproduce that hash and lets progress
        # surface them.
        payload["warnings"] = list(work.warnings)
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def accepted_section_output_hash(section: SharedSection) -> str:
    """Reproduce the media adapter's exact UTF-8 section hash canonicalization."""
    payload = json.dumps(
        section.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def frozen_figure_semantic_hash(work: SharedFigureWorkOrder, section: SharedSection) -> str:
    """Recompute the semantic identity without trusting caller-supplied hashes."""
    try:
        return rebuild_figure_work_order(work, section).figure_semantic_hash
    except SharedFigureMediaError as exc:
        raise MediaSourceConflict(str(exc)) from exc


def _item_request(
    run_id: str, work: SharedFigureWorkOrder, *, max_attempts: int
) -> WorkItemAdmission:
    # The semantic hash makes an accepted repaired section a distinct item key
    # while duplicate admission of the same frozen figure remains idempotent.
    return WorkItemAdmission(
        run_id=run_id,
        item_key=f"media:{work.work_order.work_order_id}",
        stage=MEDIA_STAGE,
        input_hash=_input_hash(work),
        definition_hash=_definition_hash(),
        composition_identity=_composition_identity(work),
        max_attempts=max_attempts,
    )


async def _verify_run_source(
    session: Any,
    *,
    run_id: str,
    owner_user_id: str,
    source: SourceIdentity,
    lock: bool = False,
) -> GenerationRunModel:
    statement = select(GenerationRunModel).where(GenerationRunModel.id == run_id)
    if lock:
        statement = statement.with_for_update()
    run = await session.scalar(statement)
    if run is None or run.owner_user_id != owner_user_id:
        raise MediaSourceConflict("SharedDocument Run is unavailable to this owner")
    persisted = (
        run.source_artifact_type,
        run.source_artifact_id,
        run.source_revision,
        run.source_hash,
    )
    observed = (
        source.source_artifact_type,
        source.source_artifact_id,
        source.source_revision,
        source.source_hash,
    )
    if persisted != observed:
        raise MediaSourceConflict("media source differs from the admitted SharedDocument Run")
    return run


def _verify_work_source(work: SharedFigureWorkOrder, source: SourceIdentity) -> None:
    if source.source_artifact_type != "teaching_plan":
        raise MediaSourceConflict("figure media requires a Teaching Plan source")
    if _work_identity(work)[:3] != (
        source.source_artifact_id,
        str(source.source_revision),
        source.source_hash,
    ):
        raise MediaSourceConflict("figure work order is bound to a different Teaching Plan source")


def _plan_visual_spec(
    source: TeachingPlanSource | SourceIdentity | None, work: SharedFigureWorkOrder, node: FigureNode
) -> VisualSpec | None:
    """The approved plan block's authoritative spec, when the plan is available."""
    if not isinstance(source, TeachingPlanSource):
        return None
    planned = next(
        (item for item in source.plan.sections if item.slot_id == work.section_id), None
    )
    block = (
        next((item for item in planned.blocks if item.id == node.teaching_block_id), None)
        if planned is not None
        else None
    )
    if block is None or block.visual is None:
        raise MediaSourceConflict("figure node has no visual spec in the approved Teaching Plan")
    return block.visual


def _predates_numbered_labels(work: SharedFigureWorkOrder, expected: SharedFigureWorkOrder) -> bool:
    return (
        work.work_order.visual.visual_style is None
        and expected.work_order.visual.visual_style == "diagram_numbered"
    )


def _verify_accepted_section(
    work: SharedFigureWorkOrder,
    section: SharedSection,
    source: TeachingPlanSource | SourceIdentity | None = None,
) -> None:
    if section.id != work.section_id:
        raise MediaSourceConflict("figure work order section differs from the accepted section")
    if accepted_section_output_hash(section) != work.section_output_hash:
        raise MediaSourceConflict("figure work order is not bound to the accepted section output")
    node = next(
        (candidate for candidate in section.nodes if candidate.id == work.figure_node_id), None
    )
    if not isinstance(node, FigureNode):
        raise MediaSourceConflict("accepted section does not contain the frozen FigureNode")
    # One builder derives the expected order: re-run it from the accepted section
    # (and the plan's authoritative spec when available) and require equality.
    try:
        expected = rebuild_figure_work_order(
            work, section, spec=_plan_visual_spec(source, work, node)
        )
    except SharedFigureMediaError as exc:
        raise MediaSourceConflict(f"figure work order cannot be re-derived: {exc}") from exc
    if work.figure_semantic_hash != expected.figure_semantic_hash:
        raise MediaSourceConflict("figure work order semantic hash is stale or forged")
    if work != expected and _predates_numbered_labels(work, expected):
        # Orders admitted before numbered diagram labels carry no visual_style;
        # the style is presentation-only (outside the semantic hash), so they
        # stay valid and resume with their original unlabelled behaviour.
        expected = expected.model_copy(
            update={
                "work_order": expected.work_order.model_copy(
                    update={
                        "visual": expected.work_order.visual.model_copy(
                            update={"visual_style": None}
                        )
                    }
                )
            }
        )
    if work != expected:
        raise MediaSourceConflict(
            "figure work order differs from the work order derived from the plan spec "
            "and accepted section"
        )


def find_active_figure_media_work_item(
    items: Sequence[GenerationWorkItemModel],
    *,
    section_id: str,
    figure_node_id: str,
) -> GenerationWorkItemModel | None:
    """Return the one active media WorkItem currently bound to a figure identity.

    ``items`` need not be pre-filtered to the media stage or to active leaves;
    both admission and repair callers use this to find the current leaf for
    one ``(section_id, figure_node_id)`` pair without trusting positional
    order or an in-memory section writer.
    """
    matches: list[GenerationWorkItemModel] = []
    for item in active_work_items(tuple(item for item in items if item.stage == MEDIA_STAGE)):
        if item.composition_identity is None:
            continue
        try:
            persisted_identity = json.loads(item.composition_identity)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MediaRuntimeError("active media work item has invalid frozen identity") from exc
        if (
            persisted_identity.get("section_id") == section_id
            and persisted_identity.get("figure_node_id") == figure_node_id
        ):
            matches.append(item)
    if len(matches) > 1:
        raise MediaRuntimeError(
            f"multiple active media work items are bound to figure {figure_node_id!r}"
        )
    return matches[0] if matches else None


def work_order_from_composition_identity(composition_identity: str | None) -> SharedFigureWorkOrder:
    """Reconstruct a durable figure work order from its frozen WorkItem identity.

    ``admit_figure_media_work_item``/``admit_repaired_figure_media_work_item``
    both persist the exact frozen ``SharedFigureWorkOrder`` as the WorkItem's
    own ``composition_identity`` (see ``_composition_identity``). A caller
    that must re-verify or re-execute an already-admitted media WorkItem --
    without trusting an in-memory section writer -- reconstructs the work
    order from this single durable source instead of recomputing it.
    """
    if not isinstance(composition_identity, str) or not composition_identity.strip():
        raise MediaRuntimeError("media work item has no frozen composition identity")
    try:
        payload = json.loads(composition_identity)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MediaRuntimeError("media work item composition identity is not valid JSON") from exc
    try:
        return SharedFigureWorkOrder.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise MediaRuntimeError(
            "media work item composition identity is not a valid frozen work order"
        ) from exc


async def admit_figure_media_work_item(
    session: Any,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource | SourceIdentity,
    work: SharedFigureWorkOrder,
    accepted_section: SharedSection,
    max_attempts: int = 3,
) -> AdmissionResult:
    """Durably admit one validated figure as soon as its section is accepted."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    identity = _identity(source)
    _verify_work_source(work, identity)
    _verify_accepted_section(work, accepted_section, source)
    run = await _verify_run_source(
        session, run_id=run_id, owner_user_id=owner_user_id, source=identity, lock=True
    )
    media_items = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel).where(
                    GenerationWorkItemModel.run_id == run.id,
                    GenerationWorkItemModel.stage == MEDIA_STAGE,
                )
            )
        ).all()
    )
    requested_identity = _composition_identity(work)
    existing = find_active_figure_media_work_item(
        media_items, section_id=work.section_id, figure_node_id=work.figure_node_id
    )
    if existing is not None and existing.composition_identity != requested_identity:
        raise MediaRuntimeError(
            "a changed section figure requires admit_repaired_figure_media_work_item"
        )
    return await add_work_item(session, _item_request(run_id, work, max_attempts=max_attempts))


async def admit_repaired_figure_media_work_item(
    session: Any,
    *,
    predecessor_work_item_id: str,
    owner_user_id: str,
    source: TeachingPlanSource | SourceIdentity,
    work: SharedFigureWorkOrder,
    accepted_section: SharedSection,
    max_attempts: int = 3,
) -> GenerationWorkItemModel:
    """Admit one changed figure as a linked 0046 replacement.

    The generic replacement repository enforces same-Run lineage, changed
    identity, predecessor state, and idempotency.  This boundary additionally
    ensures the replacement remains a media work item for the same approved
    source.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    identity = _identity(source)
    _verify_work_source(work, identity)
    _verify_accepted_section(work, accepted_section, source)
    predecessor = await session.get(GenerationWorkItemModel, predecessor_work_item_id)
    if predecessor is None:
        raise MediaRuntimeError("media replacement predecessor does not exist")
    if predecessor.stage != MEDIA_STAGE:
        raise MediaRuntimeError("media replacement predecessor has the wrong stage")
    run = await _verify_run_source(
        session,
        run_id=predecessor.run_id,
        owner_user_id=owner_user_id,
        source=identity,
    )
    if run.status not in {"queued", "running", "failed_recoverable"}:
        raise MediaRuntimeError("media replacement Run is no longer active")
    return await replace_work_item(
        session,
        WorkItemReplacement(
            predecessor_work_item_id=predecessor_work_item_id,
            owner_user_id=owner_user_id,
            source=identity,
            replacement=_item_request(run.id, work, max_attempts=max_attempts),
        ),
    )


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


def _checkpoint_payload(work: SharedFigureWorkOrder) -> dict[str, Any]:
    return {
        "kind": "shared_figure_media",
        "work_order": work.model_dump(mode="json"),
        "source_plan_id": work.source_plan_id,
        "source_plan_revision": work.source_plan_revision,
        "source_plan_hash": work.source_plan_hash,
        "section_output_hash": work.section_output_hash,
        "figure_semantic_hash": work.figure_semantic_hash,
    }


def _validate_checkpoint_payload(payload: Any, work: SharedFigureWorkOrder) -> None:
    if not isinstance(payload, Mapping) or payload.get("kind") != "shared_figure_media":
        raise MediaCheckpointError("media checkpoint has an unsupported shape")
    if payload.get("work_order") != work.model_dump(mode="json"):
        raise MediaCheckpointError("media checkpoint work order is stale or conflicting")


def _validate_item_binding(item: GenerationWorkItemModel, work: SharedFigureWorkOrder) -> None:
    if item.stage != MEDIA_STAGE:
        raise MediaCheckpointError("media work item has an unexpected stage")
    if item.input_hash != _input_hash(work) or item.composition_identity != _composition_identity(
        work
    ):
        raise MediaCheckpointError("media work item identity is stale or conflicting")


def _failure_for_exception(exc: Exception) -> WorkItemFailure:
    """Keep retries bounded and fail closed for programming/config errors."""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return WorkItemFailure(
            error_code="media_provider_transport",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="Figure media provider transport failed.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, DBAPIError):
        # Raw database faults are transient infrastructure errors; retryable.
        return WorkItemFailure(
            error_code="database_transient",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="A transient database error interrupted figure media work.",
            recovery_action=RecoveryAction.RETRY,
        )
    name = type(exc).__name__.casefold()
    if any(token in name for token in ("auth", "permission", "config", "program")):
        return WorkItemFailure(
            error_code="media_executor_configuration",
            error_class=ErrorClass.INTERNAL_PROGRAMMING,
            safe_summary="Figure media executor configuration or authorization failed.",
            recovery_action=RecoveryAction.NONE,
        )
    return WorkItemFailure(
        error_code="media_executor_failure",
        error_class=ErrorClass.INTERNAL_PROGRAMMING,
        safe_summary="Figure media executor failed unexpectedly.",
        recovery_action=RecoveryAction.NONE,
    )


async def _fail_after_rollback(
    job: MediaWorkItemJob,
    *,
    identity: SourceIdentity,
    lease_token: int,
    lease_committed: bool,
    failure: WorkItemFailure,
    now: Any,
) -> GenerationWorkItemModel | None:
    """Roll the session back, then persist ``failure`` under a valid fence.

    Returns ``None`` when the uncommitted claim could not be re-claimed; the
    caller then re-raises and lease expiry reconciles the item.
    """
    failure_lease_token = await rollback_for_failure_record(
        job.session,
        lease_token=lease_token,
        lease_committed=lease_committed,
        reclaim=lambda: claim_work_item(
            job.session,
            work_item_id=job.work_item_id,
            worker_id=job.worker_id,
            source=identity,
            lease_seconds=job.lease_seconds,
            now=now,
        ),
    )
    if failure_lease_token is None:
        return None
    return await fail_work_item(
        job.session,
        work_item_id=job.work_item_id,
        worker_id=job.worker_id,
        lease_token=failure_lease_token,
        failure=failure,
        now=now,
    )


def _is_terminal_figure_failure(
    failure: WorkItemFailure, *, attempt: int, max_attempts: int
) -> bool:
    """True when a retryable-class media failure can no longer be retried.

    Terminal means the lesson should ship with a durable "unavailable" figure:
    the failure is a non-retryable provider code (auth / 4xx), or the work
    item has used its whole attempt budget.  Failures that carry
    ``RecoveryAction.NONE`` (integrity, programming, configuration) are never
    terminal in this sense; they stay hard failures.
    """
    if failure.recovery_action != RecoveryAction.RETRY.value:
        return False
    if is_non_retryable_provider_code(failure.error_code):
        return True
    return attempt >= max_attempts


async def _settle_unavailable_after_rollback(
    job: MediaWorkItemJob,
    *,
    identity: SourceIdentity,
    lease_token: int,
    failure: WorkItemFailure,
    attempt: int,
    now: Any,
) -> UnavailableFigureMediaResult | None:
    """Complete the work item with a durable unavailable output (lease committed)."""
    token = await rollback_for_failure_record(
        job.session,
        lease_token=lease_token,
        lease_committed=True,
        reclaim=lambda: claim_work_item(
            job.session,
            work_item_id=job.work_item_id,
            worker_id=job.worker_id,
            source=identity,
            lease_seconds=job.lease_seconds,
            now=now,
        ),
    )
    if token is None:
        return None
    unavailable = unavailable_figure_result(
        job.work,
        error_code=failure.error_code,
        reason=safe_summary_for_code(failure.error_code)
        if failure.error_code.startswith(("provider_", "render_"))
        else failure.safe_summary,
        attempts=max(attempt, 1),
    )
    output = unavailable.model_dump(mode="json")
    await complete_work_item(
        job.session,
        work_item_id=job.work_item_id,
        worker_id=job.worker_id,
        lease_token=token,
        output_json=output,
        output_hash=content_hash(output),
        now=now,
    )
    return unavailable


async def _record_media_failure(
    job: MediaWorkItemJob,
    *,
    identity: SourceIdentity,
    lease_token: int,
    failure: WorkItemFailure,
    attempt: int,
    max_attempts: int,
    now: Any,
) -> tuple[GenerationWorkItemModel | None, UnavailableFigureMediaResult | None]:
    """Settle a post-claim failure as unavailable when terminal, else record it."""
    if _is_terminal_figure_failure(failure, attempt=attempt, max_attempts=max_attempts):
        unavailable = await _settle_unavailable_after_rollback(
            job,
            identity=identity,
            lease_token=lease_token,
            failure=failure,
            attempt=attempt,
            now=now,
        )
        if unavailable is not None:
            return None, unavailable
        return None, None
    failed = await _fail_after_rollback(
        job,
        identity=identity,
        lease_token=lease_token,
        lease_committed=True,
        failure=failure,
        now=now,
    )
    return failed, None


async def execute_figure_media_work_item(
    job: MediaWorkItemJob,
    *,
    now: Any = None,
) -> MediaRuntimeOutcome:
    """Claim, execute, and fenced-commit one figure work item."""
    identity = _identity(job.source)
    _verify_work_source(job.work, identity)
    _verify_accepted_section(job.work, job.accepted_section, job.source)
    item = await claim_work_item(
        job.session,
        work_item_id=job.work_item_id,
        worker_id=job.worker_id,
        source=identity,
        lease_seconds=job.lease_seconds,
        now=now,
    )
    # Capture ORM attributes now: rollback expires ``item`` and a lazy reload
    # outside the greenlet raises MissingGreenlet.
    item_id = item.id
    lease_token = item.lease_token or 0
    run_id = item.run_id
    attempt = item.attempt
    max_attempts = item.max_attempts
    compatibility = _checkpoint_compatibility(source=identity, item=item)
    try:
        _validate_item_binding(item, job.work)
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
                payload=_checkpoint_payload(job.work),
                now=now,
            )
        else:
            _validate_checkpoint_payload(checkpoint.payload, job.work)
    except LeaseLostError:
        raise
    except MediaCheckpointError:
        failure = WorkItemFailure(
            error_code="media_checkpoint_integrity",
            error_class=ErrorClass.UNSUPPORTED_CONTRACT,
            safe_summary="Figure media checkpoint failed compatibility or integrity validation.",
            recovery_action=RecoveryAction.NONE,
        )
        if (
            await _fail_after_rollback(
                job,
                identity=identity,
                lease_token=lease_token,
                lease_committed=False,
                failure=failure,
                now=now,
            )
            is None
        ):
            raise
        return MediaRuntimeOutcome(
            work_item_id=item_id,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
        )
    except Exception as exc:  # noqa: BLE001 - persist unknown checkpoint failures as terminal.
        # Checkpoint integrity/source mismatches are terminal contract errors;
        # they must not enter semantic provider retry. A raw database fault is
        # transient and stays retryable.
        if isinstance(exc, DBAPIError):
            failure = _failure_for_exception(exc)
        else:
            failure = WorkItemFailure(
                error_code="media_checkpoint_integrity",
                error_class=ErrorClass.UNSUPPORTED_CONTRACT,
                safe_summary="Figure media checkpoint failed compatibility or integrity validation.",
                recovery_action=RecoveryAction.NONE,
            )
        if (
            await _fail_after_rollback(
                job,
                identity=identity,
                lease_token=lease_token,
                lease_committed=False,
                failure=failure,
                now=now,
            )
            is None
        ):
            raise
        return MediaRuntimeOutcome(
            work_item_id=item_id,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
        )

    # The provider call must observe a durable claim and checkpoint.  Keeping
    # this commit outside the checkpoint transaction lets cancellation or a
    # lease takeover fence any late provider result before it can become ready.
    await job.session.commit()

    try:
        blocks = await job.executor.execute_figure(job.work.work_order)
        media = bind_generated_figure(job.work, blocks)
    except LeaseLostError:
        raise
    except SharedFigureMediaProviderFailed as provider_exc:
        # The executor itself reported a failed provider/transport call (for
        # example an unreachable image API). This is not a violation of the
        # shared media contract, so it must not be classified as invalid
        # hosted output. Only a safe, structured diagnostic is recorded -
        # never the provider's error_message, prompts, URLs, or keys.
        provider_code = provider_exc.error_code
        failure = WorkItemFailure(
            error_code=provider_code,
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary=safe_summary_for_code(provider_code),
            recovery_action=RecoveryAction.RETRY,
        )
        failed_item, unavailable = await _record_media_failure(
            job,
            identity=identity,
            lease_token=lease_token,
            failure=failure,
            attempt=attempt,
            max_attempts=max_attempts,
            now=now,
        )
        # lease_committed=True never skips the record.
        assert failed_item is not None or unavailable is not None
        await append_event(
            job.session,
            run_id=run_id,
            work_item_id=item_id,
            event_type="media_provider_failure_diagnostic",
            error_code=failure.error_code,
            safe_payload={"media_block_status": "failed"},
        )
        return MediaRuntimeOutcome(
            work_item_id=item_id,
            unavailable=unavailable,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
        )
    except SharedFigureMediaError:
        failure = WorkItemFailure(
            error_code="media_invalid_output",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary="Figure media output failed the shared semantic contract.",
            recovery_action=RecoveryAction.RETRY,
        )
        failed_item, unavailable = await _record_media_failure(
            job,
            identity=identity,
            lease_token=lease_token,
            failure=failure,
            attempt=attempt,
            max_attempts=max_attempts,
            now=now,
        )
        if failed_item is None and unavailable is None:
            raise
        return MediaRuntimeOutcome(
            work_item_id=item_id,
            unavailable=unavailable,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed for unknown provider errors.
        failure = _failure_for_exception(exc)
        failed_item, unavailable = await _record_media_failure(
            job,
            identity=identity,
            lease_token=lease_token,
            failure=failure,
            attempt=attempt,
            max_attempts=max_attempts,
            now=now,
        )
        if failed_item is None and unavailable is None:
            raise
        return MediaRuntimeOutcome(
            work_item_id=item_id,
            unavailable=unavailable,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
        )

    output = media.model_dump(mode="json")
    await complete_work_item(
        job.session,
        work_item_id=item.id,
        worker_id=job.worker_id,
        lease_token=lease_token,
        output_json=output,
        output_hash=content_hash(output),
        now=now,
    )
    return MediaRuntimeOutcome(work_item_id=item.id, media=media)


async def execute_figure_media_work_items(
    jobs: Sequence[MediaWorkItemJob],
    *,
    concurrency: int = MAX_CONCURRENT_MEDIA,
) -> tuple[MediaRuntimeOutcome, ...]:
    """Execute independent figures concurrently while preserving siblings."""
    if not jobs:
        return ()
    if concurrency < 1 or concurrency > MAX_CONCURRENT_MEDIA:
        raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENT_MEDIA}")
    identifiers = [job.work_item_id for job in jobs]
    if len(identifiers) != len(set(identifiers)):
        raise MediaRuntimeError("media batch contains duplicate work item IDs")
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(job: MediaWorkItemJob) -> MediaRuntimeOutcome:
        if job.status == "ready":
            return MediaRuntimeOutcome(work_item_id=job.work_item_id, preserved_ready=True)
        if job.status != "queued":
            return MediaRuntimeOutcome(
                work_item_id=job.work_item_id,
                error_code="media_item_not_queued",
                error_summary="Media batch accepts queued items only; retry failed items explicitly.",
            )
        async with semaphore:
            try:
                outcome = await execute_figure_media_work_item(job)
            except LeaseLostError:
                await job.session.rollback()
                return MediaRuntimeOutcome(
                    work_item_id=job.work_item_id,
                    error_code="media_lease_lost",
                    error_summary="Figure worker lease was lost before commit.",
                )
            except WorkItemUnavailable:
                await job.session.rollback()
                # A competing claimant may have the row lock, or the item may
                # have changed state after this batch was assembled. Keep this
                # item pending for the normal next worker pass; this is not a
                # provider failure and must not consume a semantic retry.
                return MediaRuntimeOutcome(
                    work_item_id=job.work_item_id,
                    error_code="media_claim_unavailable",
                    error_summary="Figure media work was not available to claim.",
                )
            except MediaRuntimeError as exc:
                await job.session.rollback()
                return MediaRuntimeOutcome(
                    work_item_id=job.work_item_id,
                    error_code="media_contract_failure",
                    error_summary=str(exc),
                )
            # Each job owns its session. Commit successful output and expected
            # failure transitions independently so an unrelated sibling
            # exception cannot roll them back when the batch stack closes.
            await job.session.commit()
            return outcome

    # gather's default behavior propagates the first exception immediately,
    # while sibling jobs may still be using their sessions. Collect exceptions
    # only after every task has settled, then re-raise the first one so the
    # caller keeps its normal failure path and READY remains blocked.
    results = await asyncio.gather(
        *(run_one(job) for job in jobs),
        return_exceptions=True,
    )
    outcomes: list[MediaRuntimeOutcome] = []
    first_error: BaseException | None = None
    for result in results:
        if isinstance(result, BaseException):
            if first_error is None:
                first_error = result
        else:
            outcomes.append(result)
    if first_error is not None:
        raise first_error
    return tuple(outcomes)


def project_media_readiness(
    items: Sequence[GenerationWorkItemModel],
    works: Mapping[str, SharedFigureWorkOrder],
    *,
    expected_required_work_item_ids: Sequence[str] = (),
    expected_figure_identities: Sequence[tuple[str, str]] = (),
) -> MediaReadiness:
    """Block readiness on required leaves or validated figures not yet admitted.

    ``expected_figure_identities`` is derived from validated sections before a
    generic WorkItem row exists.  It therefore closes the zero-admission gap
    without inventing a WorkItem ID or changing the generic runtime schema.
    """
    leaves = active_work_items(tuple(item for item in items if item.stage == MEDIA_STAGE))
    missing = tuple(item.id for item in leaves if item.id not in works)
    if missing:
        raise MediaRuntimeError(
            "media readiness cannot be projected without frozen work-order metadata: "
            + ", ".join(missing)
        )
    expected = tuple(dict.fromkeys(expected_required_work_item_ids))
    if any(item_id not in works for item_id in expected):
        missing_metadata = tuple(item_id for item_id in expected if item_id not in works)
        raise MediaRuntimeError(
            "media readiness cannot be projected without expected figure metadata: "
            + ", ".join(missing_metadata)
        )
    leaf_ids = {item.id for item in leaves}
    missing_required = tuple(item_id for item_id in expected if item_id not in leaf_ids)
    expected_figures = tuple(dict.fromkeys(expected_figure_identities))
    if any(
        len(identity) != 2 or not all(isinstance(part, str) and part.strip() for part in identity)
        for identity in expected_figures
    ):
        raise MediaRuntimeError("expected figure identities must be non-empty section/figure pairs")
    active_figures: set[tuple[str, str]] = set()
    for item in leaves:
        identity_payload = works[item.id].model_dump(mode="json") if item.id in works else None
        if identity_payload is None:
            continue
        active_figures.add((identity_payload["section_id"], identity_payload["figure_node_id"]))
    missing_figures = tuple(
        f"{section_id}:{figure_id}"
        for section_id, figure_id in expected_figures
        if (section_id, figure_id) not in active_figures
    )
    expected_figure_set = set(expected_figures)
    required = [
        item
        for item in leaves
        if works.get(item.id) is not None
        and (
            works[item.id].required
            or (
                works[item.id].section_id,
                works[item.id].figure_node_id,
            )
            in expected_figure_set
        )
    ]
    ready_count = sum(item.status == "ready" for item in required)
    failed = tuple(
        item.id
        for item in required
        if item.status in {"failed_recoverable", "failed_terminal", "cancelled"}
    )
    pending = tuple(
        item.id
        for item in required
        if item.status not in {"ready", "failed_recoverable", "failed_terminal", "cancelled"}
    )
    pending = missing_required + pending
    return MediaReadiness(
        ready=not failed and not pending and not missing_figures,
        required_count=len(required) + len(missing_required) + len(missing_figures),
        ready_count=ready_count,
        failed_required_work_item_ids=failed,
        pending_required_work_item_ids=pending,
        pending_required_figure_identities=missing_figures,
    )


__all__ = [
    "MAX_CONCURRENT_MEDIA",
    "MEDIA_DEFINITION",
    "MEDIA_STAGE",
    "FigureExecutor",
    "MediaCheckpointError",
    "MediaReadiness",
    "MediaRuntimeError",
    "MediaRuntimeOutcome",
    "MediaSourceConflict",
    "MediaWorkItemJob",
    "accepted_section_output_hash",
    "admit_figure_media_work_item",
    "admit_repaired_figure_media_work_item",
    "execute_figure_media_work_item",
    "execute_figure_media_work_items",
    "find_active_figure_media_work_item",
    "frozen_figure_semantic_hash",
    "project_media_readiness",
    "work_order_from_composition_identity",
]
