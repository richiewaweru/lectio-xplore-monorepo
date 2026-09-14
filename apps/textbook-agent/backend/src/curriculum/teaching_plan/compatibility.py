"""Approved-item meaning vs learner-action compatibility."""

from __future__ import annotations

from typing import Any, Literal

from core.policies.loader import (
    canonical_non_passive_actions,
    resolve_learner_action,
)
from curriculum.approved_items import approved_item_kind

# Closed response families. Aliases are canonicalized through learner-actions.yaml
# before comparison, so this module cannot drift from the policy vocabulary.
_MCQ_ACTIONS = frozenset({"select-one", "select-many"})
_OPEN_ACTIONS = frozenset(
    {
        "enter-text",
        "enter-number",
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


def _canonical_action(action: str) -> str:
    return str(resolve_learner_action(action) or action).strip()


def response_bearing_action(action: str | None) -> bool:
    """Return True only for a canonical response-bearing learner action."""
    if not action:
        return False
    canonical = str(resolve_learner_action(action) or action).strip()
    return canonical in canonical_non_passive_actions()


def allowed_actions_for_source_kind(
    kind: Literal["multiple_choice", "open_response"],
) -> tuple[str, ...]:
    """Exact learner-action vocabulary legal for a typed approved source.

    The teaching planner receives this projection verbatim. It must choose from
    this set instead of inferring compatibility from prose.
    """
    if kind == "multiple_choice":
        return tuple(sorted(_MCQ_ACTIONS))
    return tuple(sorted(_OPEN_ACTIONS))


def allowed_actions_for_source_item(item: Any) -> tuple[str, ...]:
    return allowed_actions_for_source_kind(approved_item_kind(item))


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
    original_action = action
    action = _canonical_action(action)
    kinds = [approved_item_kind(item) for item in source_items]
    if action in _MCQ_ACTIONS:
        if any(kind != "multiple_choice" for kind in kinds):
            raise ActionSourceIncompatibleError(
                f"action {original_action!r} requires multiple-choice sources; got {kinds}"
            )
        return
    if action in _OPEN_ACTIONS:
        if any(kind != "open_response" for kind in kinds):
            raise ActionSourceIncompatibleError(
                f"action {original_action!r} is incompatible with multiple-choice sources; "
                f"got {kinds}. Reauthoring requires a versioned task revision."
            )
        return
    # Passive / unknown actions must not bind assessment sources.
    raise ActionSourceIncompatibleError(
        f"action {original_action!r} cannot bind approved assessment sources"
    )


def expected_source_kind_for_action(
    action: str,
) -> Literal["multiple_choice", "open_response"] | None:
    canonical = _canonical_action(action)
    if canonical in _MCQ_ACTIONS:
        return "multiple_choice"
    if canonical in _OPEN_ACTIONS:
        return "open_response"
    return None


__all__ = [
    "ActionSourceIncompatibleError",
    "allowed_actions_for_source_item",
    "allowed_actions_for_source_kind",
    "assert_action_compatible_with_sources",
    "expected_source_kind_for_action",
    "response_bearing_action",
]
