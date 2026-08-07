"""Shared helpers for path-planning tests."""

from __future__ import annotations

import json
from pathlib import Path

from planning.models import (
    CanonicalPathPlan,
    PathPlanDraft,
    UnitCreate,
)
from planning.validation import normalize_path_plan_draft

FIXTURES = Path(__file__).resolve().parents[3] / "handoff" / "fixtures"

UNIT_FIXTURE_META: dict[str, dict[str, object]] = {
    "grade4-photosynthesis-path.json": {
        "title": "Photosynthesis",
        "topic": "Photosynthesis",
        "subject": "Science",
        "grade_level": "Grade 4",
        "destination_objective": (
            "Explain why photosynthesis matters for plants and for other living things."
        ),
        "starting_knowledge": [
            "plants have roots, stems and leaves",
            "living things need food to grow",
        ],
    },
    "grade12-photosynthesis-path.json": {
        "title": "Photosynthesis",
        "topic": "Photosynthesis",
        "subject": "Biology",
        "grade_level": "Grade 12",
        "destination_objective": (
            "Explain how light energy is converted to chemical energy "
            "and used to fix carbon into carbohydrate."
        ),
        "starting_knowledge": [
            "cell and organelle structure",
            "enzymes lower activation energy",
            "the concept of a concentration gradient",
        ],
    },
    "grade8-unreachable-destination-path.json": {
        "title": "Photosynthesis and enzyme rate",
        "topic": "Photosynthesis and enzyme rate",
        "subject": "Science",
        "grade_level": "Grade 8",
        "destination_objective": (
            "Explain how enzyme saturation limits the rate of carbon fixation "
            "at high carbon dioxide concentration."
        ),
        "starting_knowledge": [
            "plants make food in their leaves",
            "plants need light, water and carbon dioxide",
        ],
    },
}


def load_canonical_plan(name: str) -> CanonicalPathPlan:
    return CanonicalPathPlan.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def unit_create_from_fixture(name: str) -> UnitCreate:
    meta = UNIT_FIXTURE_META[name]
    return UnitCreate(
        title=str(meta["title"]),
        topic=str(meta["topic"]),
        subject=str(meta["subject"]),
        grade_level=str(meta["grade_level"]),
        destination_objective=str(meta["destination_objective"]),
        starting_knowledge=list(meta["starting_knowledge"]),  # type: ignore[arg-type]
    )


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
    return normalize_path_plan_draft(four_lesson_draft())


def overlapping_pair_plan() -> CanonicalPathPlan:
    """Two adjacent lessons with high must_establish overlap for merge-hint tests."""
    return normalize_path_plan_draft(
        four_lesson_draft(
            lessons=[
                {
                    "key": "L1",
                    "title": "Heart Structure",
                    "objective": "identify the chambers of the heart",
                    "requires": [],
                    "must_establish": [
                        "the heart has four chambers",
                        "blood flows through the heart",
                    ],
                    "knowledge_type": "conceptual",
                },
                {
                    "key": "L2",
                    "title": "Heart Function",
                    "objective": "explain how the heart pumps blood",
                    "requires": ["L1"],
                    "must_establish": [
                        "the heart has four chambers",
                        "blood flows through the heart",
                        "the heart acts as a pump",
                    ],
                    "knowledge_type": "conceptual",
                },
                {
                    "key": "L3",
                    "title": "Blood Vessels",
                    "objective": "name arteries veins and capillaries",
                    "requires": ["L2"],
                    "must_establish": ["arteries carry blood away from the heart"],
                    "knowledge_type": "factual",
                },
            ]
        )
    )
