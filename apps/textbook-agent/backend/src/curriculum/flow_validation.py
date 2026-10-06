"""Validation for the smart lesson journey selected by the structural planner."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from curriculum.models import FlowChoice


MAX_CONFRONT_SLOTS = 2


class FlowValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("Invalid selected lesson flow: " + "; ".join(self.errors))


def validate_flow_choice(
    choice: FlowChoice,
    *,
    recommended_slots: Sequence[str],
    legal_slots: Mapping[str, Mapping[str, object]],
    max_slots: int,
) -> list[str]:
    """Return structural flow violations; an empty list means the choice is legal."""
    selected = list(choice.selected_slots or recommended_slots)
    errors: list[str] = []
    legal = set(legal_slots)
    if not selected:
        errors.append("selected_slots must not be empty")
    if len(selected) > max_slots:
        errors.append(f"selected_slots exceeds max_slots={max_slots}")
    # A role may repeat only as often as the code-owned recommendation repeats
    # it; ``confront`` may also repeat up to MAX_CONFRONT_SLOTS (one per
    # high-risk misconception), since that count depends on the planner's own
    # misconception risk ratings.
    recommended_counts = Counter(recommended_slots)
    if any(
        count > max(recommended_counts.get(role, 1), MAX_CONFRONT_SLOTS if role == "confront" else 1)
        for role, count in Counter(selected).items()
    ):
        errors.append("selected_slots must not contain duplicate roles")
    unknown = sorted(set(selected) - legal)
    if unknown:
        errors.append(f"selected_slots contains unknown roles: {unknown}")
    if "check" not in selected:
        errors.append("selected_slots must retain the final verification/check capability")
    elif selected[-1] != "check":
        errors.append("selected_slots must place the final verification/check capability last")
    if choice.recommended_slots and list(choice.recommended_slots) != list(recommended_slots):
        errors.append("recommended_slots must echo the code-owned recommendation")
    if selected != list(recommended_slots) and not choice.rationale.strip():
        errors.append("flow_rationale is required when selected_slots depart from recommendation")
    if selected != list(recommended_slots) and not choice.departures:
        errors.append("flow_departures are required when selected_slots depart from recommendation")
    return errors


def flow_choice_from_plan(
    plan: object,
    *,
    recommended_slots: Sequence[str],
) -> FlowChoice:
    """Adapt legacy structural outputs that predate smart flow selection."""
    selected = list(getattr(plan, "selected_slots", None) or recommended_slots)
    return FlowChoice(
        recommended_slots=list(recommended_slots),
        selected_slots=selected,
        rationale=str(getattr(plan, "flow_rationale", "") or ""),
        departures=list(getattr(plan, "flow_departures", None) or []),
    )


__all__ = ["FlowValidationError", "flow_choice_from_plan", "validate_flow_choice"]
