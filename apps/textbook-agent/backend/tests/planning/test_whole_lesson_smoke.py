"""Injectable whole-lesson pipeline smoke test (not an official proof run)."""

from __future__ import annotations

from planning.catalogue_projections import (
    assert_teaching_guidance_has_no_object_ids,
    project_teaching_guidance,
)
from planning.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    MisconceptionRecord,
    ScopeContract,
    ScopeEntry,
    SlotRecord,
)
from planning.whole_lesson.prompt_render import render_teaching_prompt
from planning.whole_lesson.teaching_plan import (
    AnchorUsageEntry,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from planning.whole_lesson.validation import validate_teaching_plan
from resource_specs.loader import load_all_specs


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-science-1",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light to make food.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[
                ScopeEntry(id="must-1", statement="Light is required for plants to make food.")
            ],
            must_not_introduce=[
                ScopeEntry(id="exclude-1", statement="Detailed chlorophyll chemistry")
            ],
            terminology=["light", "food", "leaf", "plant"],
        ),
        anchor=AnchorRecord(
            id="anchor-plant-window",
            description="Two identical plants in different light conditions.",
        ),
        misconceptions=[
            MisconceptionRecord(
                id="misconception-1",
                statement="Plants get their food from soil.",
            )
        ],
        approved_items=[
            ApprovedItemRef(
                id="item-plant-light-03",
                card_id="card-plant-light",
                stem="Why did the covered leaf fail to make food?",
                options=[{"key": "A", "text": "No light"}, {"key": "B", "text": "No soil"}],
                correct_key="A",
            )
        ],
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain-cause", "explain"]),
            SlotRecord(slot_id="confront", typical_intents=["diagnose-misconception"]),
            SlotRecord(slot_id="check", typical_intents=["check-understanding"]),
        ],
        limits=LessonLimits(),
    )


def _valid_plan() -> TeachingPlan:
    briefs = {
        "orient": (
            "Open on anchor-plant-window by showing two identical plants that grew "
            "differently so learners notice light before any cause is named."
        ),
        "explain": (
            "Using the same two plants, isolate light as the only changed condition "
            "and state that plants need light to make food in the leaf."
        ),
        "confront": (
            "Return to the soil-food belief and use the covered plant to show why "
            "soil alone cannot explain the food difference under light."
        ),
        "check": (
            "Ask item-plant-light-03 so learners explain a new covered-leaf case "
            "using light and food without inventing new question text."
        ),
    }
    intents = {
        "orient": "orient",
        "explain": "explain-cause",
        "confront": "diagnose-misconception",
        "check": "check-understanding",
    }
    sections = []
    for slot in ("orient", "explain", "confront", "check"):
        sections.append(
            TeachingPlanSection(
                slot_id=slot,
                specific_purpose=f"Purpose for {slot}",
                blocks=[
                    TeachingPlanBlock(
                        id=f"{slot}-b1",
                        position=0,
                        intent=intents[slot],
                        brief=briefs[slot],
                        evidence_refs=["lesson.objective", "must-1", "anchor.anchor-plant-window"],
                        evidence=(
                            "This intent belongs here because the learner needs a concrete "
                            "difference before the cause and check."
                        ),
                        source_question_ids=["item-plant-light-03"] if slot == "check" else [],
                    )
                ],
            )
        )
    return TeachingPlan(
        arc=(
            "The lesson opens on two identical plants that grew differently, uses that "
            "difference to isolate light, confronts the soil-food belief, and closes by "
            "asking the learner to explain a new covered-leaf case."
        ),
        anchor_usage=[
            AnchorUsageEntry(slot_id="orient", usage="Introduce the two plants."),
            AnchorUsageEntry(slot_id="explain", usage="Reuse them to isolate light."),
            AnchorUsageEntry(
                slot_id="confront", usage="Use covered plant against soil belief."
            ),
            AnchorUsageEntry(
                slot_id="check", usage="Transfer to a new covered-leaf case."
            ),
        ],
        misconception_focus_ids=["misconception-1"],
        sections=sections,
    )


def test_teaching_prompt_and_valid_plan_smoke() -> None:
    load_all_specs()
    packet = _packet()
    guidance = project_teaching_guidance(
        permitted_intent_ids={
            "orient",
            "explain",
            "explain-cause",
            "diagnose-misconception",
            "check-understanding",
        }
    )
    assert_teaching_guidance_has_no_object_ids(guidance)
    prompt = render_teaching_prompt(packet, guidance)
    assert "Resource: " in prompt
    assert "worked-example" not in prompt
    plan = _valid_plan()
    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={
            "orient",
            "explain",
            "explain-cause",
            "diagnose-misconception",
            "check-understanding",
        },
        excluded_intents=set(),
        typical_by_slot={
            "orient": {"orient"},
            "explain": {"explain-cause", "explain"},
            "confront": {"diagnose-misconception"},
            "check": {"check-understanding"},
        },
    )
    assert report.ok, report.to_dict()
