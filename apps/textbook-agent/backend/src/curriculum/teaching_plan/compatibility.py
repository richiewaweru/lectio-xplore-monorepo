"""Approved-item meaning vs learner-action compatibility."""

from __future__ import annotations

from typing import Any, Literal

from curriculum.approved_items import approved_item_kind

# Actions that require a closed multiple-choice source when an approved item is bound.
_MCQ_ACTIONS = frozenset({"select-one", "select-many"})
# Actions that require open / constructed response when an approved item is bound.
_OPEN_ACTIONS = frozenset(
    {
        "enter-text",
        "enter-number",
        "produce-extended-response",
        "complete-missing-values",
        "order-items",
        "match-pairs",
        "classify-items",
    }
)


class ActionSourceIncompatibleError(ValueError):
    """Raised when an approved item cannot express the declared learner action."""

    code = "ACTION_SOURCE_INCOMPATIBLE"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"{self.code}: {message}")


def assert_action_compatible_with_sources(
    *,
    action: str,
    source_items: list[Any],
) -> None:
    """Fail rather than silently rewrite assessment meaning.

    Binding an MCQ item to an ordering action (or the reverse) must reject;
    selectors/writers may not change the approved item's assessment form.
    """
    if not source_items:
        return
    kinds = [approved_item_kind(item) for item in source_items]
    if action in _MCQ_ACTIONS:
        if any(kind != "multiple_choice" for kind in kinds):
            raise ActionSourceIncompatibleError(
                f"action {action!r} requires multiple-choice sources; got {kinds}"
            )
        return
    if action in _OPEN_ACTIONS:
        if any(kind != "open_response" for kind in kinds):
            raise ActionSourceIncompatibleError(
                f"action {action!r} is incompatible with multiple-choice sources; "
                f"got {kinds}. Reauthoring requires a versioned task revision."
            )
        return
    # Passive / unknown actions must not bind assessment sources.
    raise ActionSourceIncompatibleError(
        f"action {action!r} cannot bind approved assessment sources"
    )


def expected_source_kind_for_action(
    action: str,
) -> Literal["multiple_choice", "open_response"] | None:
    if action in _MCQ_ACTIONS:
        return "multiple_choice"
    if action in _OPEN_ACTIONS:
        return "open_response"
    return None
