"""Prompt barrier: rendered lesson-approach prompt must not leak object catalogue."""

from __future__ import annotations

from planning.catalogue_projections import project_teaching_guidance
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
from planning.whole_lesson.prompt_render import render_teaching_prompt
from resource_specs.loader import load_all_specs


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-1",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light to make food.",
            knowledge_type="conceptual",
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
