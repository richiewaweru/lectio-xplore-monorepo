"""Legacy retry-target classification for ``/v3/chunked/{id}/status``.

Preparation retry now runs on the shared generation runtime (Option D, 3A):
failed cards retry through ``/api/v1/generation/work-items/{id}/retry`` and
``POST /api/v1/v3/generations/{id}/retry-native`` delegates to the Run retry
(see ``application.unit_lesson.preparation_runs``).  The accept-only retry,
leased pre-worker execution and its worker were deleted.  Only the pure
classification the compatibility status projection still uses remains; it goes
away with ``native_status`` when the frontend reads lesson-status only (3B).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any


class NativeRetryTarget(str, Enum):
    ITEM_GENERATION = "item_generation"
    TEACHING_PLAN = "planning_teaching"
    POST_APPROVAL_WORKER = "post_approval_worker"
    VISUALS = "visuals"
    NOT_RETRYABLE = "not_retryable"


# A failed_recoverable row's last_error.stage names where the failure was
# raised (legacy rows only; new failures live on the preparation Run).
_POST_APPROVAL_ERROR_STAGES = frozenset(
    {
        "planning_forms",
        "writing_sections",
        "writing_blocks",
        "assembling",
        "queued",
    }
)

_VISUAL_ERROR_STAGES = frozenset({"awaiting_visuals", "visual_generation"})


def decide_native_retry_target(
    status: str,
    last_error: Mapping[str, Any] | None,
    *,
    has_failed_visuals: bool = False,
) -> NativeRetryTarget:
    """Persisted last_error.stage owns the checkpoint decision."""
    stage_status = str(status or "").strip()
    err_stage = ""
    if isinstance(last_error, Mapping):
        err_stage = str(last_error.get("stage") or "").strip()

    if stage_status == "awaiting_visuals":
        if has_failed_visuals or err_stage in _VISUAL_ERROR_STAGES:
            return NativeRetryTarget.VISUALS
        return NativeRetryTarget.NOT_RETRYABLE

    if stage_status == "failed_terminal":
        return NativeRetryTarget.NOT_RETRYABLE

    if stage_status != "failed_recoverable":
        return NativeRetryTarget.NOT_RETRYABLE

    if err_stage == "item_generation":
        return NativeRetryTarget.ITEM_GENERATION
    if err_stage == "planning_teaching":
        return NativeRetryTarget.TEACHING_PLAN
    if err_stage in _VISUAL_ERROR_STAGES:
        return NativeRetryTarget.VISUALS
    if err_stage in _POST_APPROVAL_ERROR_STAGES or not err_stage:
        return NativeRetryTarget.POST_APPROVAL_WORKER
    return NativeRetryTarget.NOT_RETRYABLE


def next_action_for_retry_target(target: NativeRetryTarget) -> str:
    if target == NativeRetryTarget.ITEM_GENERATION:
        return "retry_items"
    if target == NativeRetryTarget.TEACHING_PLAN:
        return "retry_teaching"
    if target == NativeRetryTarget.POST_APPROVAL_WORKER:
        return "retry_native"
    if target == NativeRetryTarget.VISUALS:
        return "retry_visuals"
    return "inspect_error"


__all__ = [
    "NativeRetryTarget",
    "decide_native_retry_target",
    "next_action_for_retry_target",
]
