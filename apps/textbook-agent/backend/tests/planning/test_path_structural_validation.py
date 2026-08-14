"""Cross-input validation of structural planner output against the fixed lesson.

The schema cannot know this lesson's skeleton, so these invariants live here. The
negative space matters as much as the positive: this validator must not re-check
values the bridge assigns, or it turns silent corrections into failures.
"""

from __future__ import annotations

from planning.models import PathStructuralPlan
from planning.structural_validation import (
    PathStructuralContextError,
    validate_path_structural_result,
)

SLOTS = ["orient", "explain", "contrast", "confront", "check"]


def _plan(sections: list[dict] | None = None, **overrides: object) -> PathStructuralPlan:
    if sections is None:
        sections = [
            {
                "id": slot,
                "role": slot,
                "title": f"{slot} section",
                "visual_required": False,
                "transition_note": None if index == 0 else f"follows {SLOTS[index - 1]}",
            }
            for index, slot in enumerate(SLOTS)
        ]
    else:
        sections = [
            {**section, "visual_required": section.get("visual_required", False)}
            for section in sections
        ]
    payload: dict = {
        "anchor": {"description": "two basil plants", "source": "new"},
        "cards": [{"id": "concept-1", "title": "Light", "objective": "Explain why."}],
        "sections": sections,
        "deviation_request": None,
        "objective_concern": None,
    }
    payload.update(overrides)
    return PathStructuralPlan.model_validate(payload)


def test_well_formed_plan_has_no_violations() -> None:
    assert validate_path_structural_result(_plan(), expected_slots=SLOTS) == []


def test_rejects_visual_flag_drift_against_fixed_slots() -> None:
    sections = [
        {
            "id": slot,
            "role": slot,
            "title": f"{slot} section",
            "visual_required": slot == "explain",
            "transition_note": None if index == 0 else "x",
        }
        for index, slot in enumerate(SLOTS)
    ]
    plan = _plan(sections)
    errors = validate_path_structural_result(
        plan,
        expected_slots=SLOTS,
        expected_visual_required={"explain": False},
    )
    assert any("visual_required" in error and "explain" in error for error in errors)


def test_rejects_wrong_section_order() -> None:
    reordered = list(SLOTS)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    sections = [
        {"id": slot, "role": slot, "title": slot, "transition_note": None if i == 0 else "x"}
        for i, slot in enumerate(reordered)
    ]
    errors = validate_path_structural_result(_plan(sections), expected_slots=SLOTS)
    assert any("sections[].id" in error for error in errors)


def test_rejects_duplicate_section_ids() -> None:
    sections = [
        {"id": "orient", "role": SLOTS[i], "title": "t", "transition_note": None if i == 0 else "x"}
        for i in range(len(SLOTS))
    ]
    errors = validate_path_structural_result(_plan(sections), expected_slots=SLOTS)
    assert any("duplicate section ids" in error for error in errors)


def test_rejects_section_count_mismatch() -> None:
    sections = [{"id": "orient", "role": "orient", "title": "t", "transition_note": None}]
    errors = validate_path_structural_result(_plan(sections), expected_slots=SLOTS)
    assert any("expected 5 sections" in error for error in errors)


def test_rejects_role_that_uses_the_slot_role_instead_of_the_slot_id() -> None:
    """Slots carry both ``slot_id`` and a different ``role``; only ``slot_id`` is right."""
    sections = [
        {
            "id": slot,
            "role": "teaching" if index else slot,
            "title": slot,
            "transition_note": None if index == 0 else "x",
        }
        for index, slot in enumerate(SLOTS)
    ]
    errors = validate_path_structural_result(_plan(sections), expected_slots=SLOTS)
    assert any("sections[].role" in error for error in errors)


def test_rejects_non_null_first_transition_note() -> None:
    sections = [
        {"id": slot, "role": slot, "title": slot, "transition_note": "always set"}
        for slot in SLOTS
    ]
    errors = validate_path_structural_result(_plan(sections), expected_slots=SLOTS)
    assert any("transition_note" in error for error in errors)


def test_rejects_blank_title() -> None:
    sections = [
        {"id": slot, "role": slot, "title": "   " if index == 2 else slot,
         "transition_note": None if index == 0 else "x"}
        for index, slot in enumerate(SLOTS)
    ]
    errors = validate_path_structural_result(_plan(sections), expected_slots=SLOTS)
    assert any("title" in error for error in errors)


def test_rejects_zero_cards_when_no_concern_is_raised() -> None:
    errors = validate_path_structural_result(_plan(cards=[]), expected_slots=SLOTS)
    assert any("exactly 1 concept card" in error for error in errors)


# ── the invariants this validator deliberately does not own ───────────────


def test_ignores_rewritten_objective() -> None:
    """The bridge assigns the objective, so drift here is corrected, not fatal."""
    plan = _plan(cards=[{"id": "concept-1", "title": "L", "objective": "A paraphrase."}])
    assert validate_path_structural_result(plan, expected_slots=SLOTS) == []


def test_ignores_wrong_card_id() -> None:
    """Likewise the concept id — assignment makes drift impossible downstream."""
    plan = _plan(cards=[{"id": "wrong-id", "title": "L", "objective": "Explain why."}])
    assert validate_path_structural_result(plan, expected_slots=SLOTS) == []


def test_objective_concern_short_circuits_every_other_check() -> None:
    """A concern is an answer, not a contract violation, and must not trigger repair."""
    plan = _plan(sections=[], cards=[], objective_concern="Objective spans two concepts.")
    assert validate_path_structural_result(plan, expected_slots=SLOTS) == []


def test_deviation_request_short_circuits_every_other_check() -> None:
    plan = _plan(
        sections=[],
        cards=[],
        deviation_request={
            "operation": "insert",
            "target_slot": "explain",
            "replacement_slot": None,
            "reason": "Needs a second contrast.",
        },
    )
    assert validate_path_structural_result(plan, expected_slots=SLOTS) == []


def test_context_error_carries_structured_errors() -> None:
    error = PathStructuralContextError(["a: bad", "b: worse"])
    assert error.errors == ["a: bad", "b: worse"]
    assert "a: bad" in str(error)
