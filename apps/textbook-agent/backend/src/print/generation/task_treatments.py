"""Print-only learner-task treatments (Phase H).

Maps Teaching Plan learner actions → paper response treatments. These object
ids (questions / choices / worked-example) stay Print-local and must not be
written into Teaching Plan vocabulary or Learn composition plans.
"""

from __future__ import annotations

from typing import Literal

PrintTaskTreatment = Literal["questions", "choices", "worked-example"]

PRINT_TASK_TREATMENTS: frozenset[str] = frozenset(
    {"questions", "choices", "worked-example"}
)

# Passive actions do not require a Print response surface.
PASSIVE_LEARNER_ACTIONS: frozenset[str] = frozenset(
    {"compare-without-response", "read-explanation"}
)

_WORKED_EXAMPLE_INTENTS: frozenset[str] = frozenset(
    {"demonstrate", "model", "worked-example", "walkthrough"}
)

# Learner action → default Print task object (paper response treatment).
LEARNER_ACTION_TO_PRINT_TREATMENT: dict[str, PrintTaskTreatment] = {
    "select-one": "choices",
    "select-many": "choices",
    "complete-missing-values": "questions",
    "classify-items": "questions",
    "match-pairs": "questions",
    "order-items": "questions",
    "enter-number": "questions",
    "enter-text": "questions",
    "reconstruct-order": "questions",
}


def print_treatment_for_learner_action(
    action: str | None,
    *,
    intent: str | None = None,
) -> PrintTaskTreatment | None:
    """Return a Print task treatment, or None when no response surface is needed."""
    if not action or action in PASSIVE_LEARNER_ACTIONS:
        return None
    normalized_intent = (intent or "").strip().lower().replace("_", "-")
    if (
        normalized_intent in _WORKED_EXAMPLE_INTENTS
        and action in {"enter-text", "enter-number"}
    ):
        return "worked-example"
    return LEARNER_ACTION_TO_PRINT_TREATMENT.get(action, "questions")


__all__ = [
    "LEARNER_ACTION_TO_PRINT_TREATMENT",
    "PASSIVE_LEARNER_ACTIONS",
    "PRINT_TASK_TREATMENTS",
    "PrintTaskTreatment",
    "print_treatment_for_learner_action",
]
