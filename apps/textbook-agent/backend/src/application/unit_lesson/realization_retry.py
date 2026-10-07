"""Bounded retry of a realization's generation Run (Option D, 4A).

The product retry route has two outcomes:

* a terminal shared-document boundary leaf that holds a valid repair proof
  (``boundary_checkpoint_integrity`` false positive) is requeued in place
  (``boundary_recovery``) instead of forcing a new revision;
* the realization's learn/print Run is ``failed_recoverable`` with retryable
  leaves -> ``retry_work_items`` reopens the same Run (bounded by the runtime
  attempt budget), and the realization projects back to ``queued``;
* otherwise (``failed_terminal`` / ``cancelled`` Run, no Run, document-level
  failure, or a legacy row) the caller bumps ``realization_revision`` with its
  existing compare-and-set, which yields a new output row and a new Run.

A realization that has no Run yet but whose *shared-document* Run is
``failed_recoverable`` on retryable leaves (typically failed figures) is also
retried in place: only those failed leaves are requeued, so the plan,
sourcebook and every finished section keep their outputs.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from application.unit_lesson.realization_projection import (
    is_legacy_realization,
    project_realization_status,
)
from core.database.models import NativeRealizationModel
from document.shared_lesson.boundary_recovery import recover_boundary_repair_leaves
from document.shared_lesson.realization_source import (
    PendingRealizationSource,
    RealizationAttemptsExhausted,
    RealizationSourceNotFound,
    RealizationSourceResult,
    ensure_shared_document_run,
)
from infra.database.models import GenerationRunModel
from infra.generation_runtime import (
    AttemptLimitExceeded,
    InvalidRunTransition,
    InvalidWorkItemTransition,
    RunNotFound,
    WorkItemConflict,
    WorkItemUnavailable,
    active_work_items,
    cancel_run,
    retry_work_items,
)

RETRYABLE_STATUSES = frozenset({"failed_recoverable", "failed_terminal", "failed"})


def retry_allowed(row: NativeRealizationModel) -> bool:
    return str(row.status or "") in RETRYABLE_STATUSES or is_legacy_realization(row)


async def retry_failed_run_in_place(
    session: AsyncSession,
    *,
    row: NativeRealizationModel,
    owner_user_id: str,
) -> bool:
    """Reopen a failed_recoverable Run's retryable leaves; False if a new revision is needed."""
    run_id = getattr(row, "generation_run_id", None)
    if not run_id:
        return await _retry_shared_document_leaves(session, row=row, owner_user_id=owner_user_id)
    run = await session.scalar(
        select(GenerationRunModel)
        .options(selectinload(GenerationRunModel.work_items))
        .where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
        .execution_options(populate_existing=True)
    )
    if run is None or run.status != "failed_recoverable":
        return False
    failed = [
        item
        for item in active_work_items(tuple(run.work_items))
        if item.status == "failed_recoverable"
    ]
    if not failed or any(item.recovery_action != "retry" for item in failed):
        return False
    try:
        async with session.begin_nested():
            await retry_work_items(
                session,
                run_id=run.id,
                work_item_ids=[item.id for item in failed],
                owner_user_id=owner_user_id,
            )
    except (InvalidWorkItemTransition, AttemptLimitExceeded, WorkItemConflict):
        return False
    refreshed = await session.scalar(
        select(GenerationRunModel)
        .options(selectinload(GenerationRunModel.work_items))
        .where(GenerationRunModel.id == run.id)
        .execution_options(populate_existing=True)
    )
    project_realization_status(row, run=refreshed)
    await session.flush()
    return True


async def _retry_shared_document_leaves(
    session: AsyncSession,
    *,
    row: NativeRealizationModel,
    owner_user_id: str,
) -> bool:
    """Requeue the failed leaves of a failed_recoverable shared-document Run."""
    shared_run_id = getattr(row, "shared_document_run_id", None)
    if not shared_run_id:
        return False
    if str(row.status or "") in {"failed_terminal", "failed_recoverable", "failed"} and (
        await recover_boundary_repair_leaves(
            session, run_id=shared_run_id, owner_user_id=owner_user_id
        )
    ):
        # A boundary leaf that terminally failed on a valid repair proof is a
        # false positive: it was requeued in place, so the plan, sourcebook
        # and every finished section keep their outputs.
        recovered = await session.scalar(
            select(GenerationRunModel)
            .where(GenerationRunModel.id == shared_run_id)
            .execution_options(populate_existing=True)
        )
        project_realization_status(
            row,
            doc_source=RealizationSourceResult(
                state="pending",
                pending=PendingRealizationSource(
                    run_id=shared_run_id,
                    status=str(recovered.status if recovered else "queued"),
                    stage=str(recovered.stage if recovered else "continuity_validation"),
                ),
            ),
        )
        await session.flush()
        return True
    if str(row.status or "") not in {"failed_recoverable", "failed"}:
        return False
    run = await session.scalar(
        select(GenerationRunModel)
        .options(selectinload(GenerationRunModel.work_items))
        .where(
            GenerationRunModel.id == shared_run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
            GenerationRunModel.run_type == "shared_document",
        )
        .execution_options(populate_existing=True)
    )
    if run is None or run.status != "failed_recoverable":
        return False
    failed = [
        item
        for item in active_work_items(tuple(run.work_items))
        if item.status == "failed_recoverable"
    ]
    if not failed or any(item.recovery_action != "retry" for item in failed):
        return False
    try:
        async with session.begin_nested():
            await retry_work_items(
                session,
                run_id=run.id,
                work_item_ids=[item.id for item in failed],
                owner_user_id=owner_user_id,
            )
    except (
        InvalidWorkItemTransition,
        InvalidRunTransition,
        AttemptLimitExceeded,
        WorkItemConflict,
        WorkItemUnavailable,
    ):
        return False
    refreshed = await session.scalar(
        select(GenerationRunModel)
        .where(GenerationRunModel.id == run.id)
        .execution_options(populate_existing=True)
    )
    project_realization_status(
        row,
        doc_source=RealizationSourceResult(
            state="pending",
            pending=PendingRealizationSource(
                run_id=run.id,
                status=str(refreshed.status if refreshed else "queued"),
                stage=str(refreshed.stage if refreshed else run.stage),
            ),
        ),
    )
    await session.flush()
    return True


async def admit_fresh_shared_document_run(
    session: AsyncSession,
    *,
    row: NativeRealizationModel,
    owner_user_id: str,
    label: str,
) -> GenerationRunModel:
    """Pin a retried realization to a usable (non-failed) shared-document Run.

    Called on the new-revision fallthrough, after in-place retry declined.  A
    pinned shared-document Run that is ``failed_recoverable`` but has no
    retryable leaves would be *reused* by ``ensure_shared_document_run`` (it is
    not terminal), leaving the realization re-projected as failed.  It is
    therefore cancelled first -- the same step as the shared-document
    regenerate endpoint -- so the deterministic bounded attempt keys admit a
    fresh Run.  ``failed_terminal``/``cancelled`` pinned Runs are advanced by
    ``ensure_shared_document_run`` itself; ready/active Runs are reused, so
    Learn and Print converge on one Run per lesson.  Does not commit; on a
    typed failure the session is rolled back before the 409 is raised so no
    partial cancel/admission survives.
    """
    try:
        pinned_id = getattr(row, "shared_document_run_id", None)
        if pinned_id:
            pinned = await session.scalar(
                select(GenerationRunModel)
                .where(
                    GenerationRunModel.id == pinned_id,
                    GenerationRunModel.owner_user_id == owner_user_id,
                    GenerationRunModel.run_type == "shared_document",
                )
                .execution_options(populate_existing=True)
            )
            if pinned is not None and pinned.status == "failed_recoverable":
                await cancel_run(session, run_id=pinned.id, owner_user_id=owner_user_id)
        shared_run = await ensure_shared_document_run(
            session, owner_user_id=owner_user_id, path_lesson_id=str(row.path_lesson_id)
        )
    except RealizationSourceNotFound as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SHARED_DOCUMENT_SOURCE_UNAVAILABLE",
                "message": str(exc),
                "recovery_action": "reprepare",
            },
        ) from exc
    except RealizationAttemptsExhausted as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SHARED_DOCUMENT_ATTEMPTS_EXHAUSTED",
                "message": f"This lesson's document attempts are used up, so {label} cannot "
                "be regenerated. Regenerate the lesson plan instead.",
                "recovery_action": "reprepare",
            },
        ) from exc
    except (InvalidRunTransition, RunNotFound) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SHARED_DOCUMENT_NOT_REGENERATABLE",
                "message": "The lesson document cannot be regenerated right now.",
            },
        ) from exc
    row.shared_document_run_id = shared_run.id
    row.shared_document_state = "ready" if shared_run.status == "ready" else "pending"
    await session.flush()
    return shared_run


__all__ = [
    "RETRYABLE_STATUSES",
    "admit_fresh_shared_document_run",
    "retry_allowed",
    "retry_failed_run_in_place",
]
