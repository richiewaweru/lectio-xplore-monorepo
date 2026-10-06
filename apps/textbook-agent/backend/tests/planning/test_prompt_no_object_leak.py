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
