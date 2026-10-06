"""Prompt barrier: rendered lesson-approach prompt must not leak object catalogue."""

from __future__ import annotations

import pytest

from curriculum.planning.skeletons import load_skeleton_catalog
from print.generation.catalogue_projections import project_teaching_guidance
from print.generation.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    ScopeEntry,
    SlotRecord,
)
from print.generation.whole_lesson.prompt_render import render_teaching_prompt
from resource_specs.loader import load_all_specs


def _packet(knowledge_type: str = "conceptual") -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-1",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light to make food.",
            knowledge_type=knowledge_type,
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[ScopeEntry(id="must-1", statement="Light is required to make food.")],
            must_not_introduce=[ScopeEntry(id="exclude-1", statement="chlorophyll chemistry")],
            terminology=["light", "food", "leaf"],
        ),
        anchor=AnchorRecord(
            id="anchor-plant-window",
            description="Two identical plants in different light conditions.",
        ),
        approved_items=[
            ApprovedItemRef(
                id="item-1",
                card_id="card-1",
                stem="Why did the covered plant fail to make food?",
                options=[{"key": "A", "text": "No light"}],
                correct_key="A",
            )
        ],
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain-cause"]),
            SlotRecord(slot_id="confront", typical_intents=["diagnose-misconception"]),
            SlotRecord(slot_id="check", typical_intents=["check-understanding"]),
        ],
        limits=LessonLimits(),
    )


def test_rendered_lesson_approach_prompt_has_no_object_catalogue_leak() -> None:
    load_all_specs()
    guidance = project_teaching_guidance(
        permitted_intent_ids={
            "orient",
            "explain",
            "explain-cause",
            "diagnose-misconception",
            "check-understanding",
        }
    )
    rendered = render_teaching_prompt(_packet(), guidance)
    assert "{resource_identity}" not in rendered
    assert "Resource: " in rendered
    assert "worked-example" not in rendered
    assert "available_objects" not in rendered
    assert "valid_objects" not in rendered
    assert "content_schema" not in rendered


@pytest.mark.parametrize("knowledge_type", ["conceptual", "procedural", "factual", "evaluative"])
def test_prompt_carries_recipe_guidance_for_knowledge_type(knowledge_type: str) -> None:
    load_all_specs()
    guidance = project_teaching_guidance(permitted_intent_ids={"orient", "explain"})
    rendered = render_teaching_prompt(_packet(knowledge_type), guidance)
    recipe = load_skeleton_catalog().knowledge_type_guidance(knowledge_type)
    assert recipe is not None
    assert f"Lesson design (from the {knowledge_type} recipe" in rendered
    for demand in recipe.demands:
        assert demand in rendered
    for item in recipe.contraindicated:
        assert item in rendered
    other = "procedural" if knowledge_type != "procedural" else "conceptual"
    other_recipe = load_skeleton_catalog().knowledge_type_guidance(other)
    assert other_recipe.demands[0] not in rendered
    assert "must not skip the modelling step" not in rendered
    assert "orient -> build -> model" not in rendered


def test_prompt_omits_recipe_block_for_unknown_knowledge_type() -> None:
    load_all_specs()
    guidance = project_teaching_guidance(permitted_intent_ids={"orient", "explain"})
    rendered = render_teaching_prompt(_packet("any"), guidance)
    assert "Lesson design (from the" not in rendered


_GUIDANCE_INTENTS = {
    "orient",
    "explain",
    "explain-cause",
    "diagnose-misconception",
    "check-understanding",
}

_BACKBONE = {
    "anchor": {
        "id": "anchor-1",
        "story": "Two identical plants, one in a dark cupboard.",
        "data": {"days": 7},
        "answer": None,
        "figure_ids": [],
    },
    "variants": [],
    "figures": [],
}


def test_backbone_block_present_only_when_packet_has_backbone() -> None:
    load_all_specs()
    guidance = project_teaching_guidance(permitted_intent_ids=_GUIDANCE_INTENTS)
    plain = render_teaching_prompt(_packet(), guidance)
    assert "## Lesson backbone" not in plain
    with_backbone = _packet().model_copy(
        update={"backbone": _BACKBONE, "item_backbone_refs": {"item-1": {"target": "anchor-1", "figure_id": None}}}
    )
    rendered = render_teaching_prompt(with_backbone, guidance)
    assert "## Lesson backbone" in rendered
    assert "{resource_identity}" not in rendered
    assert rendered.index("## Lesson backbone") < rendered.index("## LEARNER ACTION POLICY")
    assert '"item_backbone_refs"' in rendered
    assert "Share the anchor scenario" in rendered
    assert "same question about the same target" in rendered
    assert "takes precedence over any rule about avoiding" not in rendered


def test_packet_without_backbone_serializes_and_loads_as_before() -> None:
    packet = _packet()
    dumped = packet.model_dump(mode="json")
    assert "backbone" not in dumped and "item_backbone_refs" not in dumped
    assert "backbone" not in packet.planner_payload()
    assert ImmutableLessonPacket.model_validate(dumped) == packet  # old persisted rows load
    with_backbone = packet.model_copy(update={"backbone": _BACKBONE})
    round_tripped = ImmutableLessonPacket.model_validate(with_backbone.model_dump(mode="json"))
    assert round_tripped.backbone == _BACKBONE


def test_build_lesson_packet_uses_backbone_anchor_and_refs() -> None:
    from curriculum.approved_items import ApprovedItemRecord
    from curriculum.backbone.models import LessonBackbone
    from print.generation.whole_lesson.packet_builder import build_lesson_packet

    record = ApprovedItemRecord(
        id="p:c.i1", card_id="c", stem="s", options=({"key": "a", "text": "x"},), correct_key="a", diagnoses={}
    )
    packet = build_lesson_packet(
        path_lesson_id="l",
        subject="S",
        grade_level="G",
        objective="o",
        knowledge_type="conceptual",
        lesson_mode="first_exposure",
        must_establish=[],
        must_not_introduce=[],
        terminology=[],
        anchor_id="old",
        anchor_description="old description",
        misconceptions=[],
        prior_established=[],
        approved_items=[record],
        backbone=LessonBackbone.model_validate(_BACKBONE),
        item_backbone_refs={"p:c.i1": {"target": "anchor-1", "figure_id": None}, "gone": {"target": "x"}},
    )
    assert packet.anchor.id == "anchor-1"
    assert packet.anchor.description == _BACKBONE["anchor"]["story"]
    assert packet.item_backbone_refs == {"p:c.i1": {"target": "anchor-1", "figure_id": None}}
    assert "backbone" in packet.planner_payload()
