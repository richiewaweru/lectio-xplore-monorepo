"""Cross-input validation for structural planner output.

The prompt-facing schema in :mod:`curriculum.path_models` can express shape but not
context: it cannot know which skeleton slots this lesson has, or how many of
them. This module carries those invariants.

It lives outside ``application.unit_lesson`` deliberately — the bridge imports
``curriculum.agents``, and the planner needs the validator, so putting it in the
bridge would close an import cycle.

Scope note: this validator does NOT check the concept card's ``id`` or
``objective`` against the lesson. ``application.unit_lesson`` *assigns* both
(see ``_normalize_page_concept_card_payload``) precisely so drift is impossible;
re-validating the raw model output would convert cases the bridge silently
corrects today into hard preparation failures.

Native page plans (``PathStructuralPagePlan``) omit identity entirely. This
validator then only checks semantic payload shape: card count, section count,
titles, and the first transition note.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from curriculum.flow_validation import MAX_CONFRONT_SLOTS, validate_flow_choice
from curriculum.models import FlowChoice, normalize_misconception_risk
from curriculum.path_models import PathStructuralPagePlan, PathStructuralPlan


def high_risk_misconception_count(misconceptions: Iterable[object]) -> int:
    """Count usable misconceptions rated high-risk (missing/unknown risk is high).

    Rows with no description are dropped by the bridge normaliser, so they must
    not count here either.
    """
    count = 0
    for item in misconceptions:
        if isinstance(item, Mapping):
            text = item.get("description") or item.get("statement")
            risk = item.get("risk")
        else:
            text = getattr(item, "description", None) or getattr(item, "statement", None)
            risk = getattr(item, "risk", None)
        if not (isinstance(text, str) and text.strip()):
            continue
        if normalize_misconception_risk(risk) == "high":
            count += 1
    return count


def recommended_slots_for_high_risk_count(
    by_count: Mapping[str, Sequence[str]] | None,
    high_risk_count: int,
    *,
    default: Sequence[str],
) -> list[str]:
    """Recommended flow for a plan with ``high_risk_count`` high-risk misconceptions."""
    if not by_count:
        return list(default)
    key = str(min(max(high_risk_count, 0), MAX_CONFRONT_SLOTS))
    return list(by_count.get(key) or default)


class PathStructuralContextError(ValueError):
    """Structural planner output violated the fixed lesson contract."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__(
            "Structural planner output violated the fixed lesson contract: "
            + "; ".join(self.errors)
        )


def validate_path_structural_result(
    plan: PathStructuralPlan | PathStructuralPagePlan,
    *,
    expected_slots: list[str],
    legal_slots: Mapping[str, Mapping[str, object]] | None = None,
    max_slots: int | None = None,
    recommended_slots_by_high_risk_count: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Return contract violations. An empty list means the plan is usable.

    ``expected_slots`` is the ordered list of fixed skeleton slot ids. On the
    legacy prompt-facing contract, section ``id`` and ``role`` must both equal
    the slot id at the same position. Native page plans omit those fields;
    application code stamps them after validation.
    """
    # The planner's escape hatches are legitimate answers, not contract
    # violations. They belong to the bridge, which turns them into a readable
    # message, and they must never trigger a repair attempt.
    if plan.deviation_request is not None or plan.objective_concern:
        return []

    errors: list[str] = []

    if len(plan.cards) != 1:
        errors.append(
            f"cards: expected exactly 1 concept card, got {len(plan.cards)}"
        )

    recommended_slots = list(expected_slots)
    if recommended_slots_by_high_risk_count:
        # Misconception risk is rated by the planner, so the recommendation it is
        # measured against is the one matching its own high-risk count. Confront
        # slots earned by high-risk misconceptions are not flow departures.
        high_risk_count = high_risk_misconception_count(
            plan.cards[0].misconceptions if plan.cards else []
        )
        recommended_slots = recommended_slots_for_high_risk_count(
            recommended_slots_by_high_risk_count,
            high_risk_count,
            default=expected_slots,
        )
    selected_slots = list(plan.selected_slots or recommended_slots)
    if recommended_slots_by_high_risk_count:
        cap = min(high_risk_count, MAX_CONFRONT_SLOTS)
        # Recipes with a confront slot get exactly the recommended number. A
        # recipe without one (e.g. procedural) may add confront only as an
        # ordinary flow departure, which validate_flow_choice then requires a
        # rationale for.
        want = min(recommended_slots.count("confront"), cap)
        got = selected_slots.count("confront")
        if high_risk_count == 0 and got:
            errors.append(
                f"selected_slots: {got} 'confront' slot(s) but no misconception "
                "is high-risk; remove them or re-rate the misconceptions' risk."
            )
        elif want > 0 and got != want:
            errors.append(
                f"selected_slots: expected exactly {want} 'confront' slot(s) "
                f"for {high_risk_count} high-risk misconception(s) (one per "
                f"high-risk misconception, at most {MAX_CONFRONT_SLOTS}), got "
                f"{got}. Follow the recommended_slots_by_high_risk_count entry, "
                "or re-rate each misconception's risk."
            )
        elif want == 0 and got > cap:
            errors.append(
                f"selected_slots: at most {cap} 'confront' slot(s) for "
                f"{high_risk_count} high-risk misconception(s), got {got}."
            )
    if legal_slots is not None:
        choice = FlowChoice(
            recommended_slots=list(recommended_slots),
            selected_slots=selected_slots,
            rationale=plan.flow_rationale,
            departures=plan.flow_departures,
        )
        errors.extend(
            validate_flow_choice(
                choice,
                recommended_slots=recommended_slots,
                legal_slots=legal_slots,
                max_slots=max_slots or len(expected_slots),
            )
        )

    if isinstance(plan, PathStructuralPagePlan):
        if len(plan.sections) != len(selected_slots):
            errors.append(
                f"sections: expected {len(selected_slots)} semantic section payloads "
                f"for {selected_slots}, got {len(plan.sections)}"
            )
        for index, section in enumerate(plan.sections):
            if not (section.title or "").strip():
                errors.append(f"sections[{index}].title: must not be blank")
        if plan.sections and (plan.sections[0].transition_note or "").strip():
            errors.append("sections[0].transition_note: must be null for the first section")
        return errors

    section_ids = [section.id for section in plan.sections]
    section_roles = [section.role for section in plan.sections]

    if len(plan.sections) != len(selected_slots):
        errors.append(
            f"sections: expected {len(expected_slots)} sections "
            f"{selected_slots}, got {len(plan.sections)} {section_ids}"
        )
    else:
        if section_ids != selected_slots:
            errors.append(
                f"sections[].id: must equal selected slots in order "
                f"{selected_slots}, got {section_ids}"
            )
        if section_roles != selected_slots:
            errors.append(
                f"sections[].role: must equal selected slots in order "
                f"{selected_slots}, got {section_roles}"
            )

    duplicates = sorted({sid for sid in section_ids if section_ids.count(sid) > 1})
    if duplicates:
        errors.append(f"sections[].id: duplicate section ids {duplicates}")

    for index, section in enumerate(plan.sections):
        if not (section.title or "").strip():
            errors.append(f"sections[{index}].title: must not be blank")

    if plan.sections and (plan.sections[0].transition_note or "").strip():
        errors.append("sections[0].transition_note: must be null for the first section")

    return errors
