"""Shared helpers for path-planning tests."""

from __future__ import annotations

import json
from pathlib import Path

from planning.models import (
    CanonicalPathLesson,
    CanonicalPathPlan,
    CanonicalPathScope,
    PathPlan,
    PathPlanDraft,
)

FIXTURES = Path(__file__).resolve().parents[3] / "handoff" / "fixtures"


def load_legacy_path_plan(name: str) -> PathPlan:
    return PathPlan.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def legacy_to_canonical(plan: PathPlan) -> CanonicalPathPlan:
    """Convert an old PathPlan fixture into the active CanonicalPathPlan shape."""
    lessons = plan.lessons
    slug_to_key = {
        lesson.concept_candidate.slug: f"L{index}"
        for index, lesson in enumerate(lessons, start=1)
    }
    return CanonicalPathPlan(
        scope=CanonicalPathScope(
            must_cover=list(plan.scope_contract.must_establish),
            do_not_cover=list(plan.scope_contract.must_not_introduce),
        ),
        lessons=[
            CanonicalPathLesson(
                key=slug_to_key[lesson.concept_candidate.slug],
                title=lesson.concept_candidate.title,
                objective=lesson.objective,
                requires=[
                    slug_to_key[prerequisite]
                    for prerequisite in lesson.prerequisites
                    if prerequisite in slug_to_key
                ],
                must_establish=list(lesson.must_establish),
                knowledge_type=lesson.primary_knowledge_type,
            )
            for lesson in lessons
        ],
    )


def load_canonical_plan(name: str) -> CanonicalPathPlan:
    return legacy_to_canonical(load_legacy_path_plan(name))


def four_lesson_draft(**overrides: object) -> PathPlanDraft:
    payload: dict[str, object] = {
        "scope": {
            "must_cover": ["heart", "blood vessels", "blood movement"],
            "do_not_cover": ["advanced cardiac electrophysiology"],
        },
        "lessons": [
            {
                "key": "L1",
                "title": "The Heart as a Pump",
                "objective": "describe the heart as a pump that moves blood",
                "requires": [],
                "must_establish": ["the heart pumps blood"],
                "knowledge_type": "conceptual",
            },
            {
                "key": "L2",
                "title": "Blood Vessels and Their Roles",
                "objective": "distinguish arteries, veins and capillaries",
                "requires": ["L1"],
                "must_establish": ["arteries, veins and capillaries have different roles"],
                "knowledge_type": "conceptual",
            },
            {
                "key": "L3",
                "title": "Blood Carries Materials",
                "objective": "explain that blood carries oxygen and nutrients",
                "requires": ["L1", "L2"],
                "must_establish": ["blood transports materials"],
                "knowledge_type": "factual",
            },
            {
                "key": "L4",
                "title": "Circulation Around the Body",
                "objective": "explain how blood moves around the body",
                "requires": ["L1", "L2", "L3"],
                "must_establish": ["blood circulates through the body"],
                "knowledge_type": "conceptual",
            },
        ],
    }
    payload.update(overrides)
    return PathPlanDraft.model_validate(payload)


def sample_canonical_plan() -> CanonicalPathPlan:
    from planning.validation import normalize_path_plan_draft

    return normalize_path_plan_draft(four_lesson_draft())
