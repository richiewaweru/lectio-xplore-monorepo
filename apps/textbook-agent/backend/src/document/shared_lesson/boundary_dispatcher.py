"""Owner-scoped orchestration for continuity boundaries on a SharedDocument Run."""

from __future__ import annotations

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
from document.shared_lesson.boundary import BoundaryRepairEngine, BoundarySemanticValidator
from document.shared_lesson.boundary_runtime import (
    BOUNDARY_STAGE,
    BoundaryRuntimeOutcome,
    BoundarySourceConflict,
    BoundaryWorkItemJob,
    admit_boundary_work_item,
    execute_boundary_work_items,
)
from document.shared_lesson.models import SharedSection
from document.shared_lesson.runtime import TeachingPlanSource
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
from infra.database.models import (
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)
from infra.generation_runtime import WorkItemConflict, active_work_items, get_run_status
from infra.generation_runtime.repository import RunNotFound

MAX_BOUNDARY_DISPATCH_CONCURRENCY = 4


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
