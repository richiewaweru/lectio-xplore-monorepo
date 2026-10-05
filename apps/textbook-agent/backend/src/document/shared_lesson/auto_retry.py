"""Bounded automatic retry for recoverable SharedDocument Run failures.

Today, every ``failed_recoverable`` SharedDocument Run requires a human or
operator to call the existing ``retry_work_items`` API before the next
attempt starts. In live use, nearly every recoverable failure (writer
``UnexpectedModelBehavior``/invalid output, task semantic validation after
repair, boundary ambiguous repair, media provider failures) succeeds on one
manual retry -- so requiring that manual step is pure added latency.

This module scans ``failed_recoverable`` SharedDocument Runs and, only when
every active failed leaf is a durably bounded, retryable provider hiccup,
calls the existing ``retry_work_items`` transactional API on the Run's
behalf. It never widens ``max_attempts``, never retries a leaf whose
recovery requires human review (``recovery_action == review``) or that
carries a non-provider error class (validation, internal programming,
unsupported contract, auth, config), and never raises a concurrency race
out of the scan loop.

A boundary leaf that failed with ``boundary_repair_pending_writer_replacement``
is also never auto-retried even though its error class is
``provider_output``: it durably proves a validated targeted repair that is
waiting on a linked writer replacement, and re-running the boundary leaf as-is
only fails it again with ``boundary_checkpoint_integrity`` (a fresh claim's
checkpoint compatibility no longer matches the stale binding). Admitting that
writer replacement is the boundary dispatcher's job
(``document.shared_lesson.boundary_dispatcher``), not this scan's.
"""

from __future__ import annotations

import logging
from collections.abc import Container
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from media.generation.provider_errors import is_auth_provider_code
from infra.generation_runtime import (
    AttemptLimitExceeded,
    ErrorClass,
    InvalidRunTransition,
    RecoveryAction,
    RunNotFound,
    WorkItemUnavailable,
    active_work_items,
    append_event,
    retry_work_items,
)

LOGGER = logging.getLogger(__name__)

# A "failed leaf" covers both terminal statuses so a Run with even one
# failed_terminal leaf is recognized (and therefore excluded below): only a
# Run whose *every* active failed leaf is failed_recoverable is eligible.
_FAILED_STATUSES = frozenset({"failed_recoverable", "failed_terminal"})

_AUTO_RETRY_ERROR_CLASSES = frozenset(
    {str(ErrorClass.PROVIDER_OUTPUT), str(ErrorClass.PROVIDER_TRANSPORT)}
)

# A boundary leaf carrying this code has a durably checkpointed targeted
# repair waiting on a linked writer replacement (see
# ``document.shared_lesson.boundary_dispatcher``); it is retried by admitting
# that replacement, never by blindly re-running the boundary leaf. Auto-retry
# must treat it as ineligible so it never races the dispatcher's own repair
# admission and never re-executes a boundary whose checkpoint no longer
# matches a fresh claim (which fails as ``boundary_checkpoint_integrity``).
_INELIGIBLE_ERROR_CODES = frozenset({"boundary_repair_pending_writer_replacement"})


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _leaf_failure_time(item: GenerationWorkItemModel) -> datetime:
    reference = item.completed_at or item.updated_at
    return _as_naive_utc(reference)


def is_leaf_auto_retryable(item: GenerationWorkItemModel) -> bool:
    """Whether one failed leaf is safe for the scan to requeue automatically."""
    if item.status != "failed_recoverable":
        return False
    if item.recovery_action != RecoveryAction.RETRY.value:
        return False
    if item.error_class not in _AUTO_RETRY_ERROR_CLASSES:
        return False
    if item.error_code in _INELIGIBLE_ERROR_CODES:
        return False
    # A rejected key / missing model only recovers after an operator fix; a
    # manual Retry (or the key fix) is the right path, not a timer.
    if is_auth_provider_code(item.error_code):
        return False
    return item.attempt < item.max_attempts


def _eligible_failed_leaves(
    active: tuple[GenerationWorkItemModel, ...],
) -> tuple[GenerationWorkItemModel, ...] | None:
    """Return the Run's failed leaves when every one is safely auto-retryable.

    Returns ``None`` when the Run has no active failed leaves, or when any
    failed leaf is not eligible for automatic retry -- it needs human review
    (or ``recovery_action == none``), is not a provider_output/
    provider_transport error, has already exhausted its attempt budget, or
    is failed_terminal. In every such case the whole Run is left untouched
    for manual handling; auto-retry never fires on part of a Run.
    """
    failed = tuple(item for item in active if item.status in _FAILED_STATUSES)
    if not failed:
        return None
    if not all(is_leaf_auto_retryable(item) for item in failed):
        return None
    return failed


async def scan_and_auto_retry(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    delay_seconds: int,
    max_runs: int = 5,
    skip_run_ids: Container[str] | None = None,
) -> int:
    """Auto-retry bounded-eligible ``failed_recoverable`` SharedDocument Runs.

    Scans oldest-first (by Run ``updated_at``), retries at most ``max_runs``
    Runs, and commits each Run's retry in its own transaction using the
    Run's own ``owner_user_id`` and exactly its failed leaf ids. A race with
    a concurrent manual retry or Run transition (``InvalidRunTransition``,
    ``AttemptLimitExceeded``, ``WorkItemUnavailable``, ``RunNotFound``) is
    logged and skipped; it never propagates out of this scan.

    Returns the number of Runs it successfully auto-retried.
    """
    current_time = _as_naive_utc(now or datetime.now(UTC))
    skip = skip_run_ids or ()

    runs = list(
        (
            await session.scalars(
                select(GenerationRunModel)
                .where(
                    GenerationRunModel.run_type == "shared_document",
                    GenerationRunModel.status == "failed_recoverable",
                )
                .order_by(GenerationRunModel.updated_at, GenerationRunModel.id)
            )
        ).all()
    )

    retried = 0
    for run in runs:
        if retried >= max_runs:
            break
        if run.id in skip:
            continue

        items = list(
            (
                await session.scalars(
                    select(GenerationWorkItemModel).where(
                        GenerationWorkItemModel.run_id == run.id
                    )
                )
            ).all()
        )
        active = active_work_items(items)
        failed = _eligible_failed_leaves(active)
        if not failed:
            continue

        latest_failure = max(_leaf_failure_time(item) for item in failed)
        if (current_time - latest_failure).total_seconds() < delay_seconds:
            continue

        work_item_ids = tuple(item.id for item in failed)
        attempts = tuple(item.attempt for item in failed)
        error_codes = tuple(item.error_code for item in failed)

        try:
            await retry_work_items(
                session,
                run_id=run.id,
                work_item_ids=work_item_ids,
                owner_user_id=run.owner_user_id,
                now=current_time,
            )
            await append_event(
                session,
                run_id=run.id,
                event_type="auto_retry_scheduled",
                safe_payload={
                    "work_item_ids": list(work_item_ids),
                    "attempts": list(attempts),
                    "error_codes": list(error_codes),
                },
            )
            await session.commit()
        except (
            InvalidRunTransition,
            AttemptLimitExceeded,
            WorkItemUnavailable,
            RunNotFound,
        ) as exc:
            LOGGER.warning(
                "SharedDocument auto-retry skipped Run %s: %s: %s",
                run.id,
                type(exc).__name__,
                exc,
            )
            await session.rollback()
            continue

        retried += 1

    return retried


__all__ = ["is_leaf_auto_retryable", "scan_and_auto_retry"]
