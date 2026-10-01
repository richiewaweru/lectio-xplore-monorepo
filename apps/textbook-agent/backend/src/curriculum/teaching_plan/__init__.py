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
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.instance_ids import assign_slot_instance_ids
from curriculum.teaching_plan.models import (
    AnchorUsageEntry,
    Difficulty,
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
from curriculum.teaching_plan.revisions import (
    TeachingRevisionApprovedItemError,
    TeachingRevisionStore,
    approved_item_snapshot_hash,
    read_approved_item_snapshot,
)

__all__ = [
    "ActionSourceIncompatibleError",
    "AnchorUsageEntry",
    "Difficulty",
    "LearnerActionBrief",
    "NativeTeachingConsumer",
    "TeachingPlan",
    "TeachingPlanBlock",
    "TeachingPlanDraft",
    "TeachingPlanDraftBlock",
    "TeachingPlanDraftSection",
    "TeachingPlanSection",
    "TeachingRevisionApprovedItemError",
    "TeachingRevisionRecord",
    "TeachingRevisionStore",
    "accept_approved_teaching_revision",
    "approved_item_snapshot_hash",
    "assert_action_compatible_with_sources",
    "assign_slot_instance_ids",
    "materialize_teaching_plan",
    "read_approved_item_snapshot",
    "teaching_plan_content_hash",
]
