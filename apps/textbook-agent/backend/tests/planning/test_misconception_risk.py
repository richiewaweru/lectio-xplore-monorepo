"""Misconception risk drives how many `confront` slots a lesson earns."""

from __future__ import annotations

import pytest

from curriculum.items.prompt import build_item_messages
from curriculum.models import PathStructuralPagePlan
from curriculum.planning.models import ConceptCard
from curriculum.structural_validation import (
    high_risk_misconception_count,
    recommended_slots_for_high_risk_count,
    validate_path_structural_result,
)
from print.generation.whole_lesson.packet_builder import build_lesson_packet

BASE = ["orient", "explain", "check"]
BY_COUNT = {
    "0": BASE,
    "1": ["orient", "explain", "confront", "check"],
    "2": ["orient", "explain", "confront", "confront", "check"],
}
LEGAL = {slot: {"slot_id": slot} for slot in {"orient", "explain", "confront", "check"}}


def _page_plan(
    risks: list[str | None], selected: list[str], **extra: object
) -> PathStructuralPagePlan:
    return PathStructuralPagePlan.model_validate(
        {
            **extra,
            "anchor": {"description": "two basil plants", "source": "new"},
            "cards": [
                {
                    "title": "Light",
                    "misconceptions": [
                        {"id": f"M{i}", "description": f"belief {i}", "risk": risk}
                        for i, risk in enumerate(risks, start=1)
                    ],
                }
            ],
            "sections": [
                {"title": f"{slot} {i}", "transition_note": None if i == 0 else "next"}
                for i, slot in enumerate(selected)
            ],
            "selected_slots": selected,
        }
    )


def _validate(plan: PathStructuralPagePlan) -> list[str]:
    return validate_path_structural_result(
        plan,
        expected_slots=BASE,
        legal_slots=LEGAL,
        max_slots=6,
        recommended_slots_by_high_risk_count=BY_COUNT,
    )


def test_risk_survives_structural_dump_and_stays_absent_when_unset() -> None:
    plan = _page_plan(["low", None], BASE)
    dumped = plan.cards[0].model_dump(mode="json", exclude_none=True)
    assert dumped["misconceptions"][0]["risk"] == "low"
    assert "risk" not in dumped["misconceptions"][1]


def test_planning_misconception_risk_defaults_high_and_rejects_junk() -> None:
    card = ConceptCard.model_validate(
        {
            "id": "c",
            "title": "t",
            "objective": "o",
            "misconceptions": [{"id": "M1", "description": "d"}],
        }
    )
    assert card.misconceptions[0].risk == "high"
    with pytest.raises(ValueError):
        ConceptCard.model_validate(
            {
                "id": "c",
                "title": "t",
                "objective": "o",
                "misconceptions": [{"id": "M1", "description": "d", "risk": "medium"}],
            }
        )


@pytest.mark.parametrize(
    ("high_count", "expected_confront"), [(0, 0), (1, 1), (2, 2), (3, 2)]
)
def test_confront_count_must_equal_min_high_risk_and_two(
    high_count: int, expected_confront: int
) -> None:
    risks: list[str | None] = ["high"] * high_count + ["low"]
    right = list(BY_COUNT[str(min(high_count, 2))])
    assert right.count("confront") == expected_confront
    # Right confront count, matching the recommendation: no errors and no
    # departure rationale needed.
    assert _validate(_page_plan(risks, right)) == []

    for wrong in ({0, 1, 2} - {expected_confront}):
        selected = ["orient", "explain", *["confront"] * wrong, "check"]
        errors = _validate(_page_plan(risks, selected))
        assert any("confront" in error and "high-risk" in error for error in errors), errors


def test_low_risk_only_requires_no_confront_and_keeps_all_misconceptions() -> None:
    plan = _page_plan(["low", "low", "low"], BASE)
    assert high_risk_misconception_count(plan.cards[0].misconceptions) == 0
    assert _validate(plan) == []
    assert any("confront" in e for e in _validate(_page_plan(["low", "low"], BY_COUNT["1"])))

    card = ConceptCard.model_validate(
        {
            "id": "c",
            "title": "t",
            "objective": "o",
            "misconceptions": [
                {"id": f"M{i}", "description": f"d{i}", "risk": "low"} for i in (1, 2, 3)
            ],
        }
    ).with_item_context(subject="Biology", level="Grade 8", notation=None)
    text = "\n".join(build_item_messages(card, allowed_misconception_ids=["M1", "M2", "M3"]))
    for mid in ("M1", "M2", "M3"):
        assert mid in text


PROC_BASE = ["orient", "recall", "model", "guided", "check"]
PROC_BY_COUNT = {"0": PROC_BASE, "1": PROC_BASE, "2": PROC_BASE}
PROC_LEGAL = {slot: {"slot_id": slot} for slot in [*PROC_BASE, "confront"]}


def _validate_proc(plan: PathStructuralPagePlan) -> list[str]:
    return validate_path_structural_result(
        plan,
        expected_slots=PROC_BASE,
        legal_slots=PROC_LEGAL,
        max_slots=7,
        recommended_slots_by_high_risk_count=PROC_BY_COUNT,
    )


def test_recipe_without_confront_needs_none_for_high_risk_misconception() -> None:
    assert _validate_proc(_page_plan(["high"], PROC_BASE)) == []
    assert _validate_proc(_page_plan(["high", "high", "high"], PROC_BASE)) == []


def test_recipe_without_confront_allows_confront_only_as_departure() -> None:
    with_confront = ["orient", "recall", "model", "confront", "guided", "check"]
    errors = _validate_proc(_page_plan(["high"], with_confront))
    assert any("flow_rationale" in e for e in errors)
    departure = {
        "flow_rationale": "Learners hold a firm wrong rule.",
        "flow_departures": [
            {"operation": "insert", "to_slot": "confront", "reason": "firm wrong rule"}
        ],
    }
    plan = _page_plan(["high"], with_confront, **departure)
    assert _validate_proc(plan) == []
    # More confront slots than high-risk misconceptions is still rejected.
    two = ["orient", "recall", "confront", "confront", "model", "guided", "check"]
    errors = _validate_proc(_page_plan(["high"], two, **departure))
    assert any("at most 1" in e for e in errors)


def test_zero_high_risk_rejects_confront_in_any_recipe() -> None:
    with_confront = ["orient", "recall", "model", "confront", "guided", "check"]
    for risks in ([], ["low", "low"]):
        errors = _validate_proc(_page_plan(risks, with_confront))
        assert any("no misconception is high-risk" in e for e in errors)


def test_missing_risk_counts_as_high_and_blank_rows_do_not_count() -> None:
    plan = _page_plan([None], BY_COUNT["1"])
    assert high_risk_misconception_count(plan.cards[0].misconceptions) == 1
    assert _validate(plan) == []
    assert high_risk_misconception_count([{"id": "M1"}, {"description": " "}]) == 0


def test_high_risk_confront_is_not_a_departure_but_other_changes_still_are() -> None:
    assert _validate(_page_plan(["high"], BY_COUNT["1"])) == []
    errors = _validate(_page_plan(["high"], ["orient", "confront", "check"]))
    assert any("flow_rationale" in error for error in errors)


def test_validation_skipped_without_recommendation_map() -> None:
    plan = _page_plan(["high", "high"], BASE)
    assert (
        validate_path_structural_result(
            plan, expected_slots=BASE, legal_slots=LEGAL, max_slots=6
        )
        == []
    )


def test_recommendation_lookup_caps_at_two() -> None:
    assert recommended_slots_for_high_risk_count(BY_COUNT, 5, default=BASE) == BY_COUNT["2"]
    assert recommended_slots_for_high_risk_count(None, 1, default=BASE) == BASE


def test_packet_misconception_record_carries_risk() -> None:
    packet = build_lesson_packet(
        path_lesson_id="l1",
        subject="Biology",
        grade_level="Grade 8",
        objective="Explain photosynthesis.",
        knowledge_type="conceptual",
        lesson_mode="first_exposure",
        must_establish=[],
        must_not_introduce=[],
        terminology=[],
        anchor_id="a1",
        anchor_description="basil",
        misconceptions=[
            {"id": "M1", "description": "Soil is food.", "risk": "low"},
            {"id": "M2", "description": "Light is food."},
        ],
        prior_established=[],
        approved_items=[],
        slot_ids=BASE,
        required_assessment_slots=[],
    )
    assert [(m.id, m.risk) for m in packet.misconceptions] == [("M1", "low"), ("M2", "high")]
    assert packet.misconceptions[0].statement == "Soil is food."
