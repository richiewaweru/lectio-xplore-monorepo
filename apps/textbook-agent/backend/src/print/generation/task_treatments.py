"""Print-only learner-task treatments.

Maps Teaching Plan learner actions → paper response treatments. Legal mappings
come from ``backend/resources/policies/print-action-map.yaml``. Object ids
(questions / choices / worked-example) stay Print-local.
"""

from __future__ import annotations

from typing import Literal

from core.policies.loader import (
    passive_learner_actions,
    print_defaults,
    print_treatment_for_action,
)

PrintTaskTreatment = Literal["questions", "choices", "worked-example"]

PRINT_TASK_TREATMENTS: frozenset[str] = frozenset(
    {"questions", "choices", "worked-example"}
)

PASSIVE_LEARNER_ACTIONS: frozenset[str] = passive_learner_actions()

LEARNER_ACTION_TO_PRINT_TREATMENT: dict[str, PrintTaskTreatment] = {
    key: value  # type: ignore[misc]
    for key, value in print_defaults().items()
    if value in PRINT_TASK_TREATMENTS
}


def print_treatment_for_learner_action(
    action: str | None,
    *,
    intent: str | None = None,
) -> PrintTaskTreatment | None:
    """Return a Print task treatment, or None when no response surface is needed."""
    treatment = print_treatment_for_action(action, intent=intent)
    if treatment in PRINT_TASK_TREATMENTS:
        return treatment  # type: ignore[return-value]
    return None


__all__ = [
    "LEARNER_ACTION_TO_PRINT_TREATMENT",
    "PASSIVE_LEARNER_ACTIONS",
    "PRINT_TASK_TREATMENTS",
    "PrintTaskTreatment",
    "print_treatment_for_learner_action",
]
