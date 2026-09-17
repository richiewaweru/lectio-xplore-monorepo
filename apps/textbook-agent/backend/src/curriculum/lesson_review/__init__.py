"""Whole-lesson coherence review and bounded, targeted repair contracts."""

from .issue_projection import (
    LessonIssue,
    LessonIssueCounts,
    LessonIssuesResponse,
    collect_lesson_issues,
)
from .models import CoherenceReport, RepairEvent, RepairTarget, ReviewIssue
from .persistence import invalidate_stale_smart_artifacts, persist_smart_lesson_artifacts
from .repair import enforce_repair_cap, run_targeted_repair
from .reviewer import run_semantic_reviewer
from .service import (
    build_coherence_report,
    check_slope_consistency,
    compare_path_task_semantics,
    repair_targets_for_report,
    review_with_targeted_repairs,
)

__all__ = [
    "CoherenceReport",
    "LessonIssue",
    "LessonIssueCounts",
    "LessonIssuesResponse",
    "RepairEvent",
    "RepairTarget",
    "ReviewIssue",
    "build_coherence_report",
    "check_slope_consistency",
    "collect_lesson_issues",
    "compare_path_task_semantics",
    "enforce_repair_cap",
    "invalidate_stale_smart_artifacts",
    "persist_smart_lesson_artifacts",
    "repair_targets_for_report",
    "review_with_targeted_repairs",
    "run_semantic_reviewer",
    "run_targeted_repair",
]
