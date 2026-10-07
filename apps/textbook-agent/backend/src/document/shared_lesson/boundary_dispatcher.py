"""Owner-scoped orchestration for continuity boundaries on a SharedDocument Run."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from core.database.models import PathLessonModel
from document.shared_lesson.approved_source import (
    ApprovedSourceVerificationError,
    load_current_approved_teaching_plan_source,
    make_approved_source_verifier,
)
from document.shared_lesson.boundary import (
    BoundaryRepairEngine,
    BoundarySemanticValidator,
    BoundaryValidationResult,
)
from document.shared_lesson.boundary_runtime import (
    BOUNDARY_STAGE,
    BoundaryRuntimeOutcome,
    BoundarySourceConflict,
    BOUNDARY_PENDING_REPLACEMENT_CODE,
    BoundaryWorkItemJob,
    admit_boundary_advisory_successor,
    admit_boundary_replacement_work_item,
    admit_boundary_work_item,
    execute_boundary_work_items,
)
from document.shared_lesson.models import SharedSection
from document.shared_lesson.runtime import TeachingPlanSource, _stable_hash
from document.shared_lesson.section_sources import SectionSourceError, build_section_sources
from document.shared_lesson.semantic_inputs import SemanticInputError, load_verified_semantic_inputs
from document.shared_lesson.work_item_inputs import (
    SharedLessonInputError,
    load_verified_shared_lesson_inputs,
)
from document.shared_lesson.writer import SectionSource, SectionWriterRequest
from document.shared_lesson.writer_admission import (
    WriterAdmissionError,
    admit_writer_work_items,
)
from document.shared_lesson.writer_repair_runtime import (
    WRITER_REPAIR_DEFINITION,
    WriterRepairRuntimeError,
    WriterRepairSourceConflict,
    WriterRepairWorkItemJob,
    admit_writer_repair_work_item,
    execute_writer_repair_work_item,
)
from infra.database.models import (
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)
from infra.generation_runtime import (
    InvalidRunTransition,
    InvalidWorkItemTransition,
    LeaseLostError,
    RuntimeCheckpoint,
    WorkItemConflict,
    WorkItemNotFound,
    WorkItemUnavailable,
    active_work_items,
    append_event,
    get_run_status,
)
from infra.generation_runtime.repository import RunNotFound

LOGGER = logging.getLogger(__name__)

MAX_BOUNDARY_DISPATCH_CONCURRENCY = 4

# A writer leaf that is a boundary-triggered targeted-repair replacement is
# *expected* to carry a different input_hash than the plan-derived admission
# recomputed on every dispatch call -- that input_hash durably encodes the
# specific repair identity (see ``writer_repair_runtime.WriterRepairWorkOrder``).
# Its composition identity never changes, so that is still verified below.
_WRITER_REPAIR_DEFINITION_HASH = _stable_hash(WRITER_REPAIR_DEFINITION)


class BoundaryDispatchError(ValueError):
    """A durable SharedDocument Run cannot be dispatched for boundary review."""


class _WriterReplacementPending(BoundaryDispatchError):
    def __init__(self, work_item_ids: tuple[str, ...]) -> None:
        super().__init__("an active writer replacement needs targeted repair")
        self.work_item_ids = work_item_ids


class BoundaryDispatchResult(BaseModel):
    """Closed status for boundary admission and dispatch without Run finalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    state: Literal["passed", "pending", "pending_repair", "blocked", "no_boundaries"]
    admitted_work_item_ids: tuple[str, ...] = ()
    pending_work_item_ids: tuple[str, ...] = ()
    pending_repair_work_item_ids: tuple[str, ...] = ()
    blocked_reason: str | None = None
    outcomes: tuple[BoundaryRuntimeOutcome, ...] = ()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _expired(item: GenerationWorkItemModel, now: datetime) -> bool:
    expiry = item.lease_expires_at
    if expiry is None:
        return False
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)
    return expiry <= now


def _root_key(item: GenerationWorkItemModel, by_id: Mapping[str, GenerationWorkItemModel]) -> str:
    current = item
    seen: set[str] = set()
    while current.replaces_work_item_id is not None:
        if current.id in seen:
            raise BoundaryDispatchError("work-item replacement chain contains a cycle")
        seen.add(current.id)
        predecessor = by_id.get(current.replaces_work_item_id)
        if predecessor is None:
            raise BoundaryDispatchError("work-item replacement predecessor is missing")
        current = predecessor
    return current.item_key


def _active_writer_leaves(
    run: GenerationRunModel,
) -> dict[str, GenerationWorkItemModel]:
    rows = tuple(item for item in run.work_items if item.stage == "section_writing")
    by_id = {item.id: item for item in rows}
    leaves: dict[str, GenerationWorkItemModel] = {}
    for item in active_work_items(rows):
        key = _root_key(item, by_id)
        if not key.startswith("write:"):
            continue
        if key in leaves:
            raise BoundaryDispatchError("duplicate active writer replacement leaf")
        leaves[key] = item
    return leaves


async def _verified_run_inputs(
    session: Any,
    *,
    run_id: str,
    owner_user_id: str,
) -> tuple[
    TeachingPlanSource,
    GenerationRunModel,
    tuple[SharedSection, ...],
    dict[str, SectionWriterRequest],
    dict[str, str],
]:
    run = await get_run_status(session, run_id=run_id, owner_user_id=owner_user_id)
    if run is None or run.run_type != "shared_document":
        raise RunNotFound("SharedDocument Run is unavailable to this owner")
    if run.status not in {"queued", "running", "failed_recoverable"}:
        raise BoundaryDispatchError("SharedDocument Run is not active for boundary dispatch")

    build = await session.scalar(
        select(GenerationBuildModel).where(
            GenerationBuildModel.id == run.build_id,
            GenerationBuildModel.owner_user_id == owner_user_id,
        )
    )
    if build is None:
        raise BoundaryDispatchError("SharedDocument Build is unavailable to this owner")
    lesson = await session.get(PathLessonModel, build.path_lesson_id)
    if lesson is None or not lesson.pack_id:
        raise BoundaryDispatchError("SharedDocument PathLesson preparation is unavailable")

    source = await load_current_approved_teaching_plan_source(
        session=session,
        owner_user_id=owner_user_id,
        path_lesson_id=lesson.id,
        preparation_generation_id=lesson.pack_id,
    )
    leaves = _active_writer_leaves(run)
    expected_keys = {f"write:{section.slot_id}" for section in source.plan.sections}
    if set(leaves) != expected_keys or any(item.status != "ready" for item in leaves.values()):
        raise BoundaryDispatchError("all current writer leaves must be ready")
    semantic = await load_verified_semantic_inputs(
        session,
        run_id=run.id,
        owner_user_id=owner_user_id,
        source=source,
    )
    all_sources: list[SectionSource] = []
    seen_sources: set[str] = set()
    try:
        for section in source.plan.sections:
            for section_source in build_section_sources(semantic, section):
                if section_source.id not in seen_sources:
                    seen_sources.add(section_source.id)
                    all_sources.append(section_source)
    except SectionSourceError as exc:
        raise BoundaryDispatchError("approved section sources are unavailable") from exc
    verified = await load_verified_shared_lesson_inputs(
        session,
        run_id=run.id,
        owner_user_id=owner_user_id,
        source=source,
        tasks=semantic.tasks,
        sources=tuple(all_sources),
    )
    try:
        admissions = await admit_writer_work_items(
            session,
            run_id=run.id,
            owner_user_id=owner_user_id,
            source=source,
            source_verifier=make_approved_source_verifier(
                owner_user_id=owner_user_id,
                path_lesson_id=lesson.id,
                preparation_generation_id=lesson.pack_id,
            ),
        )
    except (WriterAdmissionError, WorkItemConflict) as exc:
        replacements = tuple(
            item.id for item in leaves.values() if item.replaces_work_item_id is not None
        )
        if replacements:
            raise _WriterReplacementPending(replacements) from exc
        raise
    if {admission.section.slot_id for admission in admissions} != expected_keys_to_sections(source):
        raise BoundaryDispatchError("durable writer requests do not cover the approved sections")
    by_section = {admission.section.slot_id: admission for admission in admissions}
    for section_id, item in leaves.items():
        admission = by_section[section_id.removeprefix("write:")]
        if (
            item.replaces_work_item_id is not None
            and item.definition_hash == _WRITER_REPAIR_DEFINITION_HASH
        ):
            # A boundary-triggered targeted-repair replacement durably binds a
            # different, repair-specific input_hash and definition_hash by
            # design; only its composition identity must still match the plan.
            if item.composition_identity != admission.composition_identity:
                raise BoundaryDispatchError("current writer leaf identity is stale")
            continue
        if (
            item.input_hash != admission.input_hash
            or item.definition_hash != admission.definition_hash
            or item.composition_identity != admission.composition_identity
        ):
            raise BoundaryDispatchError("current writer leaf identity is stale")
    return (
        source,
        run,
        verified.sections,
        {key: admission.request for key, admission in by_section.items()},
        {key: admission.composition_identity for key, admission in by_section.items()},
    )


def expected_keys_to_sections(source: TeachingPlanSource) -> set[str]:
    return {section.slot_id for section in source.plan.sections}


def _current_boundary_leaves(
    items: tuple[GenerationWorkItemModel, ...],
) -> dict[str, GenerationWorkItemModel]:
    boundary_rows = tuple(item for item in items if item.stage == BOUNDARY_STAGE)
    by_id = {item.id: item for item in boundary_rows}
    leaves: dict[str, GenerationWorkItemModel] = {}
    for item in active_work_items(boundary_rows):
        key = _root_key(item, by_id)
        if not key.startswith("boundary:"):
            continue
        if key in leaves:
            raise BoundaryDispatchError("duplicate active boundary replacement leaf")
        leaves[key] = item
    return leaves


async def _load_boundary_leaves(
    session: Any,
    *,
    run_id: str,
) -> dict[str, GenerationWorkItemModel]:
    rows = tuple(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == BOUNDARY_STAGE,
                )
                .order_by(GenerationWorkItemModel.created_at, GenerationWorkItemModel.id)
            )
        ).all()
    )
    return _current_boundary_leaves(rows)


async def _load_writer_leaves(
    session: Any,
    *,
    run_id: str,
) -> dict[str, GenerationWorkItemModel]:
    """Reload the current active ``write:*`` leaves straight from the database.

    Used only by the writer-repair path below, after the Run's initial
    ``_verified_run_inputs`` snapshot may already be stale (a prior repair in
    this same dispatch call can have replaced a writer leaf).
    """
    rows = tuple(
        (
            await session.scalars(
                select(GenerationWorkItemModel).where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == "section_writing",
                )
            )
        ).all()
    )
    by_id = {item.id: item for item in rows}
    leaves: dict[str, GenerationWorkItemModel] = {}
    for item in active_work_items(rows):
        key = _root_key(item, by_id)
        if not key.startswith("write:"):
            continue
        leaves[key] = item
    return leaves


_RUNTIME_TRANSITION_ERRORS = (
    RunNotFound,
    InvalidRunTransition,
    InvalidWorkItemTransition,
    WorkItemNotFound,
    WorkItemUnavailable,
)


async def _record_boundary_repair_skipped(
    session_factory: Callable[[], Any],
    *,
    leaf: GenerationWorkItemModel,
    previous_id: str,
    next_id: str,
    reason: str,
) -> None:
    """Make a silent skip observable: one run event with a stable reason code."""
    LOGGER.info(
        "boundary repair skipped run=%s boundary=%s->%s reason=%s",
        leaf.run_id,
        previous_id,
        next_id,
        reason,
    )
    try:
        async with session_factory() as session:
            await append_event(
                session,
                run_id=leaf.run_id,
                work_item_id=leaf.id,
                event_type="boundary_repair_skipped",
                error_code=leaf.error_code,
                safe_payload={
                    "reason": reason,
                    "previous_section_id": previous_id,
                    "next_section_id": next_id,
                },
            )
            await session.commit()
    except Exception:  # noqa: BLE001 - diagnostics must never break dispatch
        LOGGER.warning("could not record boundary_repair_skipped event", exc_info=True)


async def _admit_boundary_advisory(
    session_factory: Callable[[], Any],
    *,
    owner_user_id: str,
    source: TeachingPlanSource,
    leaf: GenerationWorkItemModel,
    previous_id: str,
    next_id: str,
    accepted_sections: Mapping[str, SharedSection],
    writer_identities: Mapping[str, str],
) -> bool:
    """Deterministic advisory fallback; never calls a provider.

    A source/identity mismatch raises ``BoundarySourceConflict`` inside the
    admission, which keeps the boundary blocked (reported via a skip event).
    """
    async with session_factory() as session:
        try:
            await admit_boundary_advisory_successor(
                session,
                predecessor_work_item_id=leaf.id,
                owner_user_id=owner_user_id,
                source=source,
                previous_section=accepted_sections[previous_id],
                next_section=accepted_sections[next_id],
                previous_composition_identity=writer_identities[previous_id],
                next_composition_identity=writer_identities[next_id],
            )
            await session.commit()
            return True
        except (BoundarySourceConflict, WorkItemConflict, *_RUNTIME_TRANSITION_ERRORS) as exc:
            await session.rollback()
            reason = f"advisory_admission_rejected:{type(exc).__name__}"
    await _record_boundary_repair_skipped(
        session_factory, leaf=leaf, previous_id=previous_id, next_id=next_id, reason=reason
    )
    return False


async def _repair_pending_boundary_writers(
    session_factory: Callable[[], Any],
    *,
    owner_user_id: str,
    worker_id: str,
    source: TeachingPlanSource,
    accepted_sections: Mapping[str, SharedSection],
    writer_requests: Mapping[str, SectionWriterRequest],
    writer_identities: Mapping[str, str],
    section_order: tuple[str, ...],
    boundary_leaves: Mapping[str, GenerationWorkItemModel],
) -> None:
    """Turn each stalled ``boundary_repair_pending_writer_replacement`` leaf
    into an admitted, executed writer replacement plus its linked boundary
    replacement -- so the next normal dispatch round validates the repair.

    Bounded to at most one writer repair per boundary identity: a boundary
    leaf that is *itself* already a repair-replacement (``replaces_work_item_id
    is not None``) completes in place with advisories in
    ``execute_boundary_work_item`` instead of ever asking for a second repair.

    When a targeted writer repair cannot be applied (issues in both sections,
    admission rejected, repair changed both sections, repaired boundary did
    not pass) the boundary falls back deterministically to an *advisory*
    successor: the original sections are kept and the findings surface as
    teacher-visible quality flags.  Every skip is recorded as a
    ``boundary_repair_skipped`` event with a reason code.

    Every step is best-effort per boundary pair: a stale or conflicting repair
    is left exactly as ``pending_repair`` for the next dispatch call (or human
    review) rather than raised out of this scan.
    """

    async def skip(leaf: GenerationWorkItemModel, previous_id: str, next_id: str, reason: str):
        await _record_boundary_repair_skipped(
            session_factory, leaf=leaf, previous_id=previous_id, next_id=next_id, reason=reason
        )

    async def advisory(leaf: GenerationWorkItemModel, previous_id: str, next_id: str) -> None:
        await _admit_boundary_advisory(
            session_factory,
            owner_user_id=owner_user_id,
            source=source,
            leaf=leaf,
            previous_id=previous_id,
            next_id=next_id,
            accepted_sections=accepted_sections,
            writer_identities=writer_identities,
        )

    for previous_id, next_id in pairwise(section_order):
        key = f"boundary:{previous_id}->{next_id}"
        leaf = boundary_leaves.get(key)
        if (
            leaf is None
            or leaf.status != "failed_recoverable"
            or leaf.error_code != BOUNDARY_PENDING_REPLACEMENT_CODE
        ):
            continue
        if leaf.checkpoint_json is None:
            await skip(leaf, previous_id, next_id, "checkpoint_missing")
            continue
        try:
            checkpoint = RuntimeCheckpoint.model_validate(leaf.checkpoint_json)
            payload = checkpoint.payload
            if not isinstance(payload, Mapping) or (
                payload.get("kind") != "shared_lesson_boundary_repair_result"
            ):
                await skip(leaf, previous_id, next_id, "checkpoint_not_repair_result")
                continue
            boundary_result = BoundaryValidationResult.model_validate(payload["result"])
        except (KeyError, TypeError, ValueError):
            await skip(leaf, previous_id, next_id, "checkpoint_unreadable")
            continue
        issues = tuple(boundary_result.initial_issues)
        if not issues:
            await skip(leaf, previous_id, next_id, "no_initial_issues")
            continue
        affected_sections = {issue.affected_section_id for issue in issues}
        if not affected_sections <= {previous_id, next_id}:
            await skip(leaf, previous_id, next_id, "issue_section_outside_boundary")
            continue
        if len(affected_sections) != 1 or leaf.replaces_work_item_id is not None:
            # Findings on both sections cannot be fixed by one targeted writer
            # repair, and a boundary that is already a repair replacement never
            # gets a second one; keep both accepted sections and surface the
            # findings as advisories.
            await advisory(leaf, previous_id, next_id)
            continue
        affected_section_id = next(iter(affected_sections))
        accepted_section = accepted_sections.get(affected_section_id)
        writer_request = writer_requests.get(affected_section_id)
        if accepted_section is None or writer_request is None:
            await skip(leaf, previous_id, next_id, "affected_section_unavailable")
            continue

        admission = None
        admission_rejected = False
        predecessor_missing = False
        async with session_factory() as session:
            writer_leaves = await _load_writer_leaves(session, run_id=leaf.run_id)
            predecessor = writer_leaves.get(f"write:{affected_section_id}")
            if predecessor is None:
                predecessor_missing = True
            else:
                try:
                    admission = await admit_writer_repair_work_item(
                        session,
                        owner_user_id=owner_user_id,
                        source=source,
                        predecessor_work_item_id=predecessor.id,
                        accepted_section=accepted_section,
                        writer_request=writer_request,
                        boundary_result=boundary_result,
                        boundary_work_item_id=leaf.id,
                        issues=issues,
                        previous_section=accepted_sections[previous_id],
                        next_section=accepted_sections[next_id],
                    )
                    await session.commit()
                except (
                    WriterRepairRuntimeError,
                    WriterRepairSourceConflict,
                    WorkItemConflict,
                    *_RUNTIME_TRANSITION_ERRORS,
                ) as exc:
                    await session.rollback()
                    admission_rejected = True
                    LOGGER.info(
                        "writer repair admission rejected for %s: %s", key, type(exc).__name__
                    )
        if predecessor_missing:
            await skip(leaf, previous_id, next_id, "writer_predecessor_missing")
            continue
        if admission_rejected:
            await skip(leaf, previous_id, next_id, "writer_repair_admission_rejected")
            await advisory(leaf, previous_id, next_id)
            continue
        if admission is None:
            await skip(leaf, previous_id, next_id, "writer_repair_not_admitted")
            continue

        outcome = None
        async with session_factory() as session:
            try:
                outcome = await execute_writer_repair_work_item(
                    WriterRepairWorkItemJob(
                        session=session,
                        work_item_id=admission.item.id,
                        worker_id=worker_id,
                        source=source,
                        work=admission.work,
                        writer_request=writer_request,
                    )
                )
            except LeaseLostError:
                await session.rollback()
                outcome = None
                lease_lost = True
            else:
                lease_lost = False
                await session.commit()
        if lease_lost:
            await skip(leaf, previous_id, next_id, "writer_repair_lease_lost")
            continue
        if outcome is None or outcome.result is None:
            # The repair failed its own closed-contract or source
            # revalidation; the writer replacement is now failed_recoverable
            # (or terminal) in its own right and the original section can no
            # longer be restored here, so the boundary stays pending_repair
            # for the next dispatch call or human review.
            await skip(leaf, previous_id, next_id, "writer_repair_execution_failed")
            continue

        repaired_section = outcome.result.as_shared_section(
            section_id=affected_section_id,
            position=accepted_section.position,
        )
        if affected_section_id == previous_id:
            new_previous, new_next = repaired_section, accepted_sections[next_id]
        else:
            new_previous, new_next = accepted_sections[previous_id], repaired_section

        replacement_rejected = False
        async with session_factory() as session:
            try:
                await admit_boundary_replacement_work_item(
                    session,
                    predecessor_work_item_id=leaf.id,
                    owner_user_id=owner_user_id,
                    source=source,
                    previous_section=new_previous,
                    next_section=new_next,
                    previous_composition_identity=writer_identities[previous_id],
                    next_composition_identity=writer_identities[next_id],
                )
                await session.commit()
            except (BoundarySourceConflict, WorkItemConflict, *_RUNTIME_TRANSITION_ERRORS):
                await session.rollback()
                replacement_rejected = True
        if replacement_rejected:
            await skip(leaf, previous_id, next_id, "boundary_replacement_admission_rejected")


async def dispatch_shared_document_boundaries(
    session_factory: Callable[[], Any],
    *,
    run_id: str,
    owner_user_id: str,
    worker_id: str | None = None,
    semantic_validator: BoundarySemanticValidator | None = None,
    repair_engine: BoundaryRepairEngine | None = None,
    lease_seconds: int = 300,
    concurrency: int = MAX_BOUNDARY_DISPATCH_CONCURRENCY,
) -> BoundaryDispatchResult:
    """Verify accepted writer leaves, admit adjacent boundaries, and dispatch ready work."""
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    if concurrency < 1 or concurrency > MAX_BOUNDARY_DISPATCH_CONCURRENCY:
        raise ValueError(f"concurrency must be between 1 and {MAX_BOUNDARY_DISPATCH_CONCURRENCY}")
    selected_worker_id = worker_id or f"shared-boundary-{uuid.uuid4()}"

    try:
        async with session_factory() as session:
            (
                source,
                run,
                accepted_sections_raw,
                writer_requests,
                writer_identities,
            ) = await _verified_run_inputs(
                session,
                run_id=run_id,
                owner_user_id=owner_user_id,
            )
            accepted_sections = {section.id: section for section in accepted_sections_raw}
            section_order = tuple(section.slot_id for section in source.plan.sections)
            if len(section_order) == 1:
                await session.commit()
                return BoundaryDispatchResult(run_id=run_id, state="no_boundaries")

            admitted_ids: list[str] = []
            for previous_id, next_id in pairwise(section_order):
                try:
                    admitted = await admit_boundary_work_item(
                        session,
                        run_id=run.id,
                        owner_user_id=owner_user_id,
                        source=source,
                        previous_section=accepted_sections[previous_id],
                        next_section=accepted_sections[next_id],
                        previous_composition_identity=writer_identities[previous_id],
                        next_composition_identity=writer_identities[next_id],
                    )
                except WorkItemConflict:
                    # A prior writer repair already replaced this pair's root
                    # boundary identity (its accepted writer output changed).
                    # The active replacement leaf is loaded and validated
                    # below; re-admitting under the original stable key would
                    # only re-raise this same conflict against the historical
                    # failed row it is now bound to.
                    continue
                admitted_ids.append(admitted.record.id)
            await session.commit()
    except _WriterReplacementPending as exc:
        return BoundaryDispatchResult(
            run_id=run_id,
            state="pending_repair",
            pending_repair_work_item_ids=exc.work_item_ids,
        )
    except (
        ApprovedSourceVerificationError,
        BoundaryDispatchError,
        BoundarySourceConflict,
        RunNotFound,
        SemanticInputError,
        SharedLessonInputError,
        WriterAdmissionError,
        WorkItemConflict,
    ):
        return BoundaryDispatchResult(
            run_id=run_id,
            state="blocked",
            blocked_reason="approved_writer_inputs_unavailable_or_stale",
        )

    async with session_factory() as session:
        boundary_leaves = await _load_boundary_leaves(session, run_id=run_id)

    expected_keys = tuple(
        f"boundary:{previous}->{next_}" for previous, next_ in pairwise(section_order)
    )
    if any(key not in boundary_leaves for key in expected_keys):
        return BoundaryDispatchResult(
            run_id=run_id,
            state="blocked",
            admitted_work_item_ids=tuple(admitted_ids),
            blocked_reason="boundary_work_items_incomplete",
        )

    now = _now()
    pending_repair_ids = tuple(
        boundary_leaves[key].id
        for key in expected_keys
        if boundary_leaves[key].status in {"failed_recoverable", "failed_terminal", "cancelled"}
    )
    pending_ids = tuple(
        boundary_leaves[key].id
        for key in expected_keys
        if boundary_leaves[key].status == "running" and not _expired(boundary_leaves[key], now)
    )
    work = [
        (previous_id, next_id, boundary_leaves[f"boundary:{previous_id}->{next_id}"])
        for previous_id, next_id in pairwise(section_order)
        if (
            boundary_leaves[f"boundary:{previous_id}->{next_id}"].status == "queued"
            or (
                boundary_leaves[f"boundary:{previous_id}->{next_id}"].status == "running"
                and _expired(boundary_leaves[f"boundary:{previous_id}->{next_id}"], now)
            )
        )
    ]

    outcomes: tuple[BoundaryRuntimeOutcome, ...] = ()
    if work:
        async with AsyncExitStack() as stack:
            jobs: list[BoundaryWorkItemJob] = []
            for previous_id, next_id, item in work:
                job_session = await stack.enter_async_context(session_factory())
                jobs.append(
                    BoundaryWorkItemJob(
                        session=job_session,
                        work_item_id=item.id,
                        worker_id=selected_worker_id,
                        source=source,
                        previous_section=accepted_sections[previous_id],
                        next_section=accepted_sections[next_id],
                        writer_requests={
                            previous_id: writer_requests[previous_id],
                            next_id: writer_requests[next_id],
                        },
                        semantic_validator=semantic_validator,
                        repair_engine=repair_engine,
                        # execute_boundary_work_item claims an expired running
                        # row; the batch only accepts queued jobs as dispatchable.
                        status="queued",
                        lease_seconds=lease_seconds,
                    )
                )
            outcomes = await execute_boundary_work_items(jobs, concurrency=concurrency)

    async with session_factory() as session:
        boundary_leaves = await _load_boundary_leaves(session, run_id=run_id)

    await _repair_pending_boundary_writers(
        session_factory,
        owner_user_id=owner_user_id,
        worker_id=selected_worker_id,
        source=source,
        accepted_sections=accepted_sections,
        writer_requests=writer_requests,
        writer_identities=writer_identities,
        section_order=section_order,
        boundary_leaves=boundary_leaves,
    )

    async with session_factory() as session:
        boundary_leaves = await _load_boundary_leaves(session, run_id=run_id)
    pending_repair_ids = tuple(
        boundary_leaves[key].id
        for key in expected_keys
        if boundary_leaves[key].status in {"failed_recoverable", "failed_terminal", "cancelled"}
    )
    pending_ids = tuple(
        boundary_leaves[key].id
        for key in expected_keys
        if boundary_leaves[key].status in {"queued", "running"}
    )
    if pending_repair_ids or any(outcome.error_code for outcome in outcomes):
        state: Literal["passed", "pending", "pending_repair", "blocked", "no_boundaries"] = (
            "pending_repair"
        )
    elif pending_ids:
        state = "pending"
    else:
        state = "passed"
    return BoundaryDispatchResult(
        run_id=run_id,
        state=state,
        admitted_work_item_ids=tuple(admitted_ids),
        pending_work_item_ids=pending_ids,
        pending_repair_work_item_ids=pending_repair_ids,
        outcomes=outcomes,
    )


__all__ = [
    "MAX_BOUNDARY_DISPATCH_CONCURRENCY",
    "BoundaryDispatchError",
    "BoundaryDispatchResult",
    "dispatch_shared_document_boundaries",
]
