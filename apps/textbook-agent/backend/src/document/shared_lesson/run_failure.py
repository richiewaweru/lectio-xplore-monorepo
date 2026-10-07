"""Truthful, teacher-safe description of why a SharedDocument Run is stuck.

Pure projection over work-item rows (ORM models or any object with the same
attributes). Only the persisted *safe* error code/summary of a failed leaf is
used; raw provider messages never reach this layer.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from document.shared_lesson.auto_retry import is_leaf_auto_retryable
from document.shared_lesson.boundary_recovery import looks_like_recoverable_boundary_leaf
from infra.config import settings as _settings

_FAILED_STATUSES = frozenset({"failed_recoverable", "failed_terminal"})
_MEDIA_STAGE = "media_generation"


@dataclass(frozen=True)
class RunFailureSummary:
    error_code: str
    safe_summary: str
    stage: str
    error_class: str | None
    work_item_id: str
    attempt: int
    max_attempts: int
    recovery_action: str | None
    retryable: bool
    auto_retrying: bool
    failed_count: int
    #: True when the lead failure is a falsely terminal boundary repair leaf that
    #: a Retry recovers in place (see ``boundary_recovery``).
    boundary_recoverable: bool = False


def summarize_failed_leaves(
    leaves: Iterable[Any],
    *,
    auto_retry_enabled: bool | None = None,
) -> RunFailureSummary | None:
    """Summarize the active failed leaves of a Run (``None`` when none failed).

    ``auto_retrying`` is true only when the worker will really requeue the Run
    on its own: auto-retry is enabled and *every* failed leaf is eligible with
    attempts remaining (mirrors ``scan_and_auto_retry``).
    """
    failed = [item for item in leaves if item.status in _FAILED_STATUSES]
    if not failed:
        return None
    if auto_retry_enabled is None:
        auto_retry_enabled = bool(_settings.shared_document_auto_retry_enabled)
    # Media failures are the common, most actionable case: report them first.
    failed.sort(key=lambda item: 0 if item.stage == _MEDIA_STAGE else 1)
    lead = failed[0]
    # A boundary leaf terminally failed as ``boundary_checkpoint_integrity``
    # while holding a valid repair proof is recovered by Retry, not by
    # regenerating the whole lesson.
    recoverable = [looks_like_recoverable_boundary_leaf(item) for item in failed]
    boundary_recoverable = all(recoverable)
    return RunFailureSummary(
        error_code=str(lead.error_code or "RUN_FAILED"),
        safe_summary=str(lead.error_summary or "A step of this lesson failed."),
        stage=str(lead.stage),
        error_class=str(lead.error_class) if lead.error_class else None,
        work_item_id=str(lead.id),
        attempt=int(lead.attempt),
        max_attempts=int(lead.max_attempts),
        recovery_action=(
            "retry"
            if boundary_recoverable
            else str(lead.recovery_action)
            if lead.recovery_action
            else None
        ),
        retryable=all(
            (item.status == "failed_recoverable" and item.recovery_action == "retry")
            or looks_like_recoverable_boundary_leaf(item)
            for item in failed
        ),
        auto_retrying=bool(auto_retry_enabled)
        and all(is_leaf_auto_retryable(item) for item in failed),
        failed_count=len(failed),
        boundary_recoverable=boundary_recoverable,
    )


__all__ = ["RunFailureSummary", "summarize_failed_leaves"]
