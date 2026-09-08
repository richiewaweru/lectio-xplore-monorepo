"""Compatibility shim — instructional teaching models live in curriculum."""

from __future__ import annotations

from curriculum.teaching_plan.models import (
    AnchorUsageEntry,
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanDraft,
    TeachingPlanDraftBlock,
    TeachingPlanDraftSection,
    TeachingPlanSection,
    materialize_teaching_plan,
)
from curriculum.teaching_plan.service import bind_shared_teaching_runner
from print.generation.whole_lesson.teaching_agent import run_lesson_approach_planner

# Ensure Print composition binds the shared teaching runner when this shim loads.
bind_shared_teaching_runner(run_lesson_approach_planner)

__all__ = [
    "AnchorUsageEntry",
    "LearnerActionBrief",
    "TeachingPlan",
    "TeachingPlanBlock",
    "TeachingPlanDraft",
    "TeachingPlanDraftBlock",
    "TeachingPlanDraftSection",
    "TeachingPlanSection",
    "materialize_teaching_plan",
]
