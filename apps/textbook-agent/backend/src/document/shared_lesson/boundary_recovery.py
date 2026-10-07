"""Recover SharedDocument Runs falsely terminalized at a boundary repair proof.

Before the boundary runtime accepted its own ``shared_lesson_boundary_repair_result``
checkpoint on a re-run, a manual Retry of a pending-writer-replacement boundary
leaf failed it as ``boundary_checkpoint_integrity`` (terminal, no recovery).
Such a leaf still holds a perfectly valid, hash-verified repair proof, so the
failure is a false positive.  This module requeues exactly those leaves (no
attempt consumed, checkpoint kept); the normal boundary dispatcher then
resolves them through the writer-replacement or advisory-fallback path.

Anything that is not provably that case -- a tampered checkpoint, a source or
identity mismatch, a leaf that never reached repair -- is left terminal.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from document.shared_lesson.boundary_runtime import (
    BOUNDARY_STAGE,
    BoundarySourceConflict,
    _verified_repair_proof,
)
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.generation_runtime import (
    InvalidRunTransition,
    InvalidWorkItemTransition,
    SourceIdentity,
    WorkItemUnavailable,
    active_work_items,
    requeue_failed_terminal_work_item,
)

LOGGER = logging.getLogger(__name__)

RECOVERABLE_BOUNDARY_ERROR_CODE = "boundary_checkpoint_integrity"
_FAILED_STATUSES = frozenset({"failed_recoverable", "failed_terminal"})


def _run_identity(run: GenerationRunModel) -> SourceIdentity:
    return SourceIdentity(
        source_artifact_type=run.source_artifact_type,
        source_artifact_id=run.source_artifact_id,
        source_revision=run.source_revision,
        source_hash=run.source_hash,
    )


def is_recoverable_boundary_repair_leaf(
    item: GenerationWorkItemModel, identity: SourceIdentity
) -> bool:
    """Whether ``item`` is a terminal boundary leaf holding a valid repair proof."""
    if (
        item.stage != BOUNDARY_STAGE
        or item.status != "failed_terminal"
        or item.error_code != RECOVERABLE_BOUNDARY_ERROR_CODE
        or item.checkpoint_json is None
    ):
        return False
    try:
        _verified_repair_proof(item, identity)
    except BoundarySourceConflict:
        return False
    return True


def looks_like_recoverable_boundary_leaf(item: Any) -> bool:
    """Cheap, pure shape check for failure summaries (no hash verification).

    ``recover_boundary_repair_leaves`` re-verifies the proof before changing
    anything; this only decides whether the UI may offer a Retry.
    """
    checkpoint = getattr(item, "checkpoint_json", None)
    payload = checkpoint.get("payload") if isinstance(checkpoint, dict) else None
    return (
        getattr(item, "stage", None) == BOUNDARY_STAGE
        and getattr(item, "status", None) == "failed_terminal"
        and getattr(item, "error_code", None) == RECOVERABLE_BOUNDARY_ERROR_CODE
        and isinstance(payload, dict)
        and payload.get("kind") == "shared_lesson_boundary_repair_result"
    )


async def recover_boundary_repair_leaves(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
) -> bool:
    """Requeue the Run's falsely terminal boundary-repair leaves.

    Returns ``True`` only when every active failed leaf of the Run was such a
    leaf and all were requeued; otherwise nothing is changed.
    """
    run = await session.scalar(
        select(GenerationRunModel)
        .options(selectinload(GenerationRunModel.work_items))
        .where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
            GenerationRunModel.run_type == "shared_document",
        )
        .execution_options(populate_existing=True)
    )
    if run is None or run.status not in {"failed_terminal", "failed_recoverable"}:
        return False
    identity = _run_identity(run)
    failed = [
        item for item in active_work_items(tuple(run.work_items)) if item.status in _FAILED_STATUSES
    ]
    if not failed or not all(is_recoverable_boundary_repair_leaf(item, identity) for item in failed):
        return False
    try:
        async with session.begin_nested():
            for item in failed:
                await requeue_failed_terminal_work_item(
                    session,
                    work_item_id=item.id,
                    owner_user_id=owner_user_id,
                    expected_error_code=RECOVERABLE_BOUNDARY_ERROR_CODE,
                )
    except (InvalidRunTransition, InvalidWorkItemTransition, WorkItemUnavailable):
        LOGGER.info("boundary repair recovery skipped for run %s", run_id, exc_info=True)
        return False
    return True


__all__ = [
    "RECOVERABLE_BOUNDARY_ERROR_CODE",
    "is_recoverable_boundary_repair_leaf",
    "recover_boundary_repair_leaves",
    "looks_like_recoverable_boundary_leaf",
]
