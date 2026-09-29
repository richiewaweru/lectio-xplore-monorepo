"""Pure retry-target classification kept for the compatibility chunked status.

The accept-only retry and its leased pre-worker execution were deleted in
Option D 3A (preparation retry is a Run retry; see
``tests/application/test_3a_preparation_runs.py``).
"""

from __future__ import annotations

from print.generation.whole_lesson.native_retry import (
    NativeRetryTarget,
    decide_native_retry_target,
    next_action_for_retry_target,
)


def test_decide_targets() -> None:
    assert (
        decide_native_retry_target(
            "failed_recoverable", {"stage": "item_generation", "retryable": True}
        )
        == NativeRetryTarget.ITEM_GENERATION
    )
    assert (
        decide_native_retry_target(
            "failed_recoverable", {"stage": "planning_teaching", "retryable": True}
        )
        == NativeRetryTarget.TEACHING_PLAN
    )
    assert (
        decide_native_retry_target(
            "failed_recoverable", {"stage": "planning_forms", "retryable": True}
        )
        == NativeRetryTarget.POST_APPROVAL_WORKER
    )
    assert (
        decide_native_retry_target(
            "awaiting_visuals", {"stage": "awaiting_visuals", "retryable": True}
        )
        == NativeRetryTarget.VISUALS
    )
    assert (
        decide_native_retry_target("failed_terminal", {"stage": "planning_teaching"})
        == NativeRetryTarget.NOT_RETRYABLE
    )


def test_next_action_names_are_stable() -> None:
    assert next_action_for_retry_target(NativeRetryTarget.ITEM_GENERATION) == "retry_items"
    assert next_action_for_retry_target(NativeRetryTarget.TEACHING_PLAN) == "retry_teaching"
    assert next_action_for_retry_target(NativeRetryTarget.NOT_RETRYABLE) == "inspect_error"
