from __future__ import annotations

from print.generation.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from print.generation.whole_lesson.service import assessment_slots_from_structural_plan
from print.generation.whole_lesson.teaching_agent import (
    _assessment_source_policy,
    _repair_sources_outside_structural_slots,
)
from print.generation.whole_lesson.teaching_plan import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from print.generation.whole_lesson.legality import build_lesson_legality_snapshot


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="ineq",
            subject="Math",
            grade_level="Grade 6",
            objective="Interpret inequality symbols.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["inequality", "greater", "less"]),
        anchor=AnchorRecord(id="scale", description="A balance scale compares amounts."),
        slots=[
            SlotRecord(slot_id="guided", typical_intents=["practise-guided"]),
            SlotRecord(slot_id="check", typical_intents=["check-understanding"]),
        ],
        required_assessment_slots=["check"],
        approved_items=[
            ApprovedItemRef(
                id="item-check-1",
                card_id="card-1",
                stem="Which symbol means less than?",
                options=[
                    {"key": "A", "text": "<"},
                    {"key": "B", "text": ">"},
                ],
                correct_key="A",
            )
        ],
        limits=LessonLimits(),
    )


def test_structural_question_plan_becomes_required_assessment_slot() -> None:
    plan = {
        "sections": [
            {"id": "guided", "role": "guided"},
            {"id": "check", "role": "check"},
        ],
        "question_plan": [
            {"section_id": "check", "question_id": "q-check-1", "temperature": "cold"}
        ],
    }
    assert assessment_slots_from_structural_plan(plan) == ["check"]


def test_policy_exposes_exact_source_shape_and_allowed_actions() -> None:
    packet = _packet()
    policy = _assessment_source_policy(packet, build_lesson_legality_snapshot(packet))
    assert policy["required_assessment_slots"] == ["check"]
    source = policy["approved_sources"][0]
    assert source["approved_item_id"] == "item-check-1"
    assert source["kind"] == "multiple_choice"
    assert source["allowed_actions"] == ["select-many", "select-one"]
    assert source["evidence_ref"] == "item.item-check-1"
    assert source["stem"] == "Which symbol means less than?"


def test_guided_block_cannot_steal_check_source() -> None:
    packet = _packet()
    plan = TeachingPlan(
        arc="Compare then check.",
        sections=[
            TeachingPlanSection(
                slot_id="guided",
                blocks=[
                    TeachingPlanBlock(
                        id="guided-b1",
                        position=0,
                        intent="practise-guided",
                        brief="Compare inequality symbols using the balance scale anchor.",
                        evidence="Learner interprets the inequality relation correctly.",
                        source_question_ids=["item-check-1"],
                        learner_action=LearnerActionBrief(
                            action="enter-text",
                            target="inequality reading",
                            purpose="guided articulation",
                            expected_evidence="learner writes the relation in words",
                            difficulty="guided",
                        ),
                    )
                ],
            ),
            TeachingPlanSection(
                slot_id="check",
                blocks=[
                    TeachingPlanBlock(
                        id="check-b1",
                        position=0,
                        intent="check-understanding",
                        brief="Check inequality symbol meaning against the lesson objective.",
                        evidence="Learner selects the symbol meaning independently.",
                    )
                ],
            ),
        ],
    )
    _repair_sources_outside_structural_slots(plan, packet)
    assert plan.sections[0].blocks[0].source_question_ids == []
    assert plan.sections[1].blocks[0].source_question_ids == []
