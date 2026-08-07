"""Whole-lesson native planning package (v1.1)."""

from planning.whole_lesson.form_plan import (
    FormDecision,
    FormPlan,
    FormPlanBlock,
    FormPlanSection,
    coerce_form_plan,
)
from planning.whole_lesson.legality import (
    LessonLegalitySnapshot,
    build_lesson_legality_snapshot,
    validate_legality_snapshot,
)
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.resolved_block_plan import (
    ResolvedBlockPlan,
    ResolvedLessonPlan,
    ResolvedSectionPlan,
    resolve_block_plans,
)
from planning.whole_lesson.teaching_plan import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)

__all__ = [
    "FormDecision",
    "FormPlan",
    "FormPlanBlock",
    "FormPlanSection",
    "ImmutableLessonPacket",
    "LessonLegalitySnapshot",
    "ResolvedBlockPlan",
    "ResolvedLessonPlan",
    "ResolvedSectionPlan",
    "TeachingPlan",
    "TeachingPlanBlock",
    "TeachingPlanSection",
    "build_lesson_legality_snapshot",
    "coerce_form_plan",
    "resolve_block_plans",
    "validate_legality_snapshot",
]
