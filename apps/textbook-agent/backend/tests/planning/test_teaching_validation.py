"""Teaching-plan validation and departure rules."""

from __future__ import annotations

import pytest

from planning.page_blocks import PageBlockPlanError, validate_intent_departure
from planning.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    ScopeEntry,
    SlotRecord,
)
from planning.whole_lesson.teaching_plan import (
    AnchorUsage,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from planning.whole_lesson.validation import validate_teaching_plan


def test_typical_intent_forbids_departure_reason() -> None:
    with pytest.raises(PageBlockPlanError):
        validate_intent_departure(
            intent="orient",
            typical_intents={"orient"},
            permitted_intents={"orient", "emphasise"},
            excluded_intents={"investigate"},
            departure_reason="just because",
        )


def test_atypical_intent_requires_departure_reason() -> None:
    with pytest.raises(PageBlockPlanError):
        validate_intent_departure(
            intent="emphasise",
            typical_intents={"orient"},
            permitted_intents={"orient", "emphasise"},
            excluded_intents=set(),
            departure_reason=None,
        )
    validate_intent_departure(
        intent="emphasise",
        typical_intents={"orient"},
        permitted_intents={"orient", "emphasise"},
        excluded_intents=set(),
        departure_reason="Need a short reminder before the check.",
    )


def test_excluded_intent_rejected() -> None:
    with pytest.raises(PageBlockPlanError):
        validate_intent_departure(
            intent="investigate",
            typical_intents=set(),
            permitted_intents={"orient"},
            excluded_intents={"investigate"},
            departure_reason=None,
        )


def test_generic_brief_fails_validation() -> None:
    packet = ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="l1",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light to make food.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[ScopeEntry(id="must-1", statement="Light is required.")],
            terminology=["light", "food"],
        ),
        anchor=AnchorRecord(id="anchor-1", description="Two plants"),
        approved_items=[
            ApprovedItemRef(id="item-1", card_id="c1", stem="Q?", correct_key="A")
        ],
        slots=[SlotRecord(slot_id=s) for s in ("orient", "explain", "confront", "check")],
        limits=LessonLimits(),
    )
    plan = TeachingPlan(
        arc="Opens on two plants, isolates light, confronts soil-food belief, checks with a new case.",
        anchor_usage=AnchorUsage(
            orient="show plants",
            explain="reuse plants",
            confront="test soil belief",
            check="new case",
        ),
        sections=[
            TeachingPlanSection(
                slot_id=slot,
                blocks=[
                    TeachingPlanBlock(
                        id=f"{slot}-b1",
                        position=0,
                        intent="orient" if slot == "orient" else "explain",
                        brief="explain the concept clearly for learners today",
                        evidence_refs=["lesson.objective"],
                        evidence="Because the objective needs an opening.",
                    )
                ],
            )
            for slot in ("orient", "explain", "confront", "check")
        ],
    )
    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "explain"},
        excluded_intents=set(),
        typical_by_slot={
            "orient": {"orient"},
            "explain": {"explain"},
            "confront": {"explain"},
            "check": {"explain"},
        },
    )
    assert not report.ok
    codes = {issue.code for issue in report.issues}
    assert "BRIEF_GENERIC" in codes or "BRIEF_TOO_SHORT" in codes or "BRIEF_NO_ANCHOR_OR_TERM" in codes
