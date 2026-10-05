"""Bounded retry of a realization's generation Run (Option D, 4A).

The product retry route has two outcomes:

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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from application.unit_lesson.realization_projection import (
    is_legacy_realization,
    project_realization_status,
)
from core.database.models import NativeRealizationModel
from document.shared_lesson.realization_source import (
    PendingRealizationSource,
    RealizationSourceResult,
)
from infra.database.models import GenerationRunModel
from infra.generation_runtime import (
    AttemptLimitExceeded,
    InvalidRunTransition,
    InvalidWorkItemTransition,
    WorkItemConflict,
    WorkItemUnavailable,
    active_work_items,
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
    if not shared_run_id or str(row.status or "") not in {"failed_recoverable", "failed"}:
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


__all__ = ["RETRYABLE_STATUSES", "retry_allowed", "retry_failed_run_in_place"]
