"""Cross-input validation for structural planner output.

The prompt-facing schema in :mod:`planning.models` can express shape but not
context: it cannot know which skeleton slots this lesson has, or how many of
them. This module carries those invariants.

It lives outside ``planning.bridge`` deliberately — the bridge imports
``planning.agents``, and the planner needs the validator, so putting it in the
bridge would close an import cycle.

Scope note: this validator does NOT check the concept card's ``id`` or
``objective`` against the lesson. ``planning.bridge`` *assigns* both
(see ``_normalize_page_concept_card_payload``) precisely so drift is impossible;
re-validating the raw model output would convert cases the bridge silently
corrects today into hard preparation failures.
"""

from __future__ import annotations

from collections.abc import Mapping

from planning.models import PathStructuralPlan


class PathStructuralContextError(ValueError):
    """Structural planner output violated the fixed lesson contract."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__(
            "Structural planner output violated the fixed lesson contract: "
            + "; ".join(self.errors)
        )


def validate_path_structural_result(
    plan: PathStructuralPlan,
    *,
    expected_slots: list[str],
    expected_visual_required: Mapping[str, bool] | None = None,
) -> list[str]:
    """Return contract violations. An empty list means the plan is usable.

    ``expected_slots`` is the ordered list of fixed skeleton slot ids. Section
    ``id`` and ``role`` must both equal the slot id at the same position — that
    is what ``planning.bridge`` enforces downstream, so disagreeing here would
    only move the failure.
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

    section_ids = [section.id for section in plan.sections]
    section_roles = [section.role for section in plan.sections]

    if len(plan.sections) != len(expected_slots):
        errors.append(
            f"sections: expected {len(expected_slots)} sections "
            f"{expected_slots}, got {len(plan.sections)} {section_ids}"
        )
    else:
        if section_ids != expected_slots:
            errors.append(
                f"sections[].id: must equal the fixed slots in order "
                f"{expected_slots}, got {section_ids}"
            )
        if section_roles != expected_slots:
            errors.append(
                f"sections[].role: must equal the fixed slots in order "
                f"{expected_slots}, got {section_roles}"
            )

    duplicates = sorted({sid for sid in section_ids if section_ids.count(sid) > 1})
    if duplicates:
        errors.append(f"sections[].id: duplicate section ids {duplicates}")

    for index, section in enumerate(plan.sections):
        if not (section.title or "").strip():
            errors.append(f"sections[{index}].title: must not be blank")

        if expected_visual_required is not None:
            expected = bool(expected_visual_required.get(section.id, False))
            if bool(section.visual_required) != expected:
                errors.append(
                    f"sections[{index}].visual_required: must echo the fixed "
                    f"slot flag {expected} for {section.id!r}, got "
                    f"{bool(section.visual_required)}"
                )

    if plan.sections and (plan.sections[0].transition_note or "").strip():
        errors.append("sections[0].transition_note: must be null for the first section")

    return errors
