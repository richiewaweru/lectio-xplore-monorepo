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
