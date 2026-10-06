"""Scoped reviews for the staged teaching planner (section-local and whole-lesson).

The reviewer prompt and loop are reused by import from ``semantic_review``; only a
scope wrapper is appended here.
"""

from __future__ import annotations

from typing import Any

from curriculum.prompts import teaching_plan_semantic_reviewer_prompt
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanDraftV2
from curriculum.teaching_plan.semantic_review import (
    TeachingPlanSemanticFinding,
    TeachingPlanSemanticReviewError,
    TeachingPlanSemanticReviewResult,
    _review_candidate,
)
from curriculum.teaching_plan.staged import TeachingSpine

SECTION_REVIEW_CODES: frozenset[str] = frozenset(
    {
        "task_evidence_gap",
        "assessment_item_reused",
        "misconception_unresolved",
        "factual_inaccuracy",
    }
)
LESSON_REVIEW_CODES: frozenset[str] = frozenset(
    {
        "progression_gap",
        "adjacent_exit_entry",
        "target_coverage_gap",
        "duplicate_section_responsibility",
        "visual_missing_for_figure_objective",
    }
)

SECTION_REVIEW_SCOPE = (
    "## REVIEW SCOPE\n\n"
    "This is a SECTION-SCOPED review. Review only the one section contained in "
    "`materialized_candidate`. The `teaching_spine` in the payload is read-only context "
    "describing the rest of the lesson; do not review or report on other sections. "
    "Report only these finding codes: task_evidence_gap, assessment_item_reused, "
    "misconception_unresolved, factual_inaccuracy. Do not report any other code."
)
LESSON_REVIEW_SCOPE = (
    "## REVIEW SCOPE\n\n"
    "This is a WHOLE-LESSON review. Each section was already reviewed separately for "
    "block-level defects, so do not report block-level findings. Report only these finding "
    "codes: progression_gap, adjacent_exit_entry, target_coverage_gap, "
    "duplicate_section_responsibility, visual_missing_for_figure_objective. Judge "
    "cross-section progression, handoffs between adjacent sections, coverage of the "
    "lesson target state, and duplicated section responsibilities. Do not report any "
    "other code."
)


def section_review_prompt() -> str:
    return f"{teaching_plan_semantic_reviewer_prompt()}\n\n{SECTION_REVIEW_SCOPE}"


def lesson_review_prompt() -> str:
    return f"{teaching_plan_semantic_reviewer_prompt()}\n\n{LESSON_REVIEW_SCOPE}"


async def review_teaching_section(
    *,
    spine: TeachingSpine,
    slot_id: str,
    section_plan: TeachingPlan,
    section_draft: TeachingPlanDraftV2,
    lesson_context: dict[str, Any],
    trace_id: str | None = None,
    generation_id: str | None = None,
) -> list[TeachingPlanSemanticFinding]:
    """Review one materialized section; only section-local codes are returned."""
    if [section.slot_id for section in section_plan.sections] != [slot_id]:
        raise TeachingPlanSemanticReviewError(
            "TEACHING_SEMANTIC_REVIEW_INVALID",
            "section review requires a one-section plan for the given slot_id",
        )
    return await _review_candidate(
        draft=section_draft,
        plan=section_plan,
        lesson_context=lesson_context,
        trace_id=trace_id,
        generation_id=generation_id,
        system_prompt=section_review_prompt(),
        extra_payload={
            "teaching_spine": spine.model_dump(mode="json"),
            "review_scope": {
                "kind": "section",
                "slot_id": slot_id,
                "allowed_codes": sorted(SECTION_REVIEW_CODES),
            },
        },
        allowed_codes=SECTION_REVIEW_CODES,
        caller="teaching_section_reviewer",
    )


async def review_teaching_lesson(
    *,
    spine: TeachingSpine,
    plan: TeachingPlan,
    draft: TeachingPlanDraftV2,
    lesson_context: dict[str, Any],
    trace_id: str | None = None,
    generation_id: str | None = None,
) -> TeachingPlanSemanticReviewResult:
    """Whole-lesson check; only lesson-level codes, bound to the plan content hash."""
    findings = await _review_candidate(
        draft=draft,
        plan=plan,
        lesson_context=lesson_context,
        trace_id=trace_id,
        generation_id=generation_id,
        system_prompt=lesson_review_prompt(),
        extra_payload={
            "teaching_spine": spine.model_dump(mode="json"),
            "review_scope": {
                "kind": "lesson",
                "allowed_codes": sorted(LESSON_REVIEW_CODES),
            },
        },
        allowed_codes=LESSON_REVIEW_CODES,
        caller="teaching_lesson_reviewer",
    )
    return TeachingPlanSemanticReviewResult(
        content_hash=teaching_plan_content_hash(plan),
        findings=findings,
    )


__all__ = [
    "LESSON_REVIEW_CODES",
    "SECTION_REVIEW_CODES",
    "review_teaching_lesson",
    "review_teaching_section",
]
