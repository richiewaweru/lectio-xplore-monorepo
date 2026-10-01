"""Whole-lesson native planning package (v1.1)."""

from print.generation.whole_lesson.legality import (
    LessonLegalitySnapshot,
    build_lesson_legality_snapshot,
    project_slot_intent_policy,
    validate_legality_snapshot,
)
from print.generation.whole_lesson.packet import ImmutableLessonPacket
from print.generation.whole_lesson.teaching_plan import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanDraft,
    TeachingPlanDraftBlock,
    TeachingPlanDraftSection,
    TeachingPlanSection,
    materialize_teaching_plan,
)

__all__ = [
    "ImmutableLessonPacket",
    "LessonLegalitySnapshot",
    "TeachingPlan",
    "TeachingPlanBlock",
    "TeachingPlanDraft",
    "TeachingPlanDraftBlock",
    "TeachingPlanDraftSection",
    "TeachingPlanSection",
    "build_lesson_legality_snapshot",
    "materialize_teaching_plan",
    "project_slot_intent_policy",
    "validate_legality_snapshot",
]
