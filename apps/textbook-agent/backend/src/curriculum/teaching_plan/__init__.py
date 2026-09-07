"""Shared instructional teaching plan — curriculum ownership.

Print and Learn consume approved teaching revisions; they do not own the
instructional model or planner service.
"""

from curriculum.teaching_plan.compatibility import (
    ActionSourceIncompatibleError,
    assert_action_compatible_with_sources,
)
from curriculum.teaching_plan.consumers import (
    NativeTeachingConsumer,
    accept_approved_teaching_revision,
)
from curriculum.teaching_plan.instance_ids import assign_slot_instance_ids
from curriculum.teaching_plan.models import (
    AnchorUsageEntry,
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanDraft,
    TeachingPlanDraftBlock,
    TeachingPlanDraftSection,
    TeachingPlanSection,
    TeachingRevisionRecord,
    materialize_teaching_plan,
)
from curriculum.teaching_plan.revisions import TeachingRevisionStore

__all__ = [
    "ActionSourceIncompatibleError",
    "AnchorUsageEntry",
    "LearnerActionBrief",
    "NativeTeachingConsumer",
    "TeachingPlan",
    "TeachingPlanBlock",
    "TeachingPlanDraft",
    "TeachingPlanDraftBlock",
    "TeachingPlanDraftSection",
    "TeachingPlanSection",
    "TeachingRevisionRecord",
    "TeachingRevisionStore",
    "accept_approved_teaching_revision",
    "assert_action_compatible_with_sources",
    "assign_slot_instance_ids",
    "materialize_teaching_plan",
]
