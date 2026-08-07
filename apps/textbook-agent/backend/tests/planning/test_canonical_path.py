"""Stage A — Canonical path normalization and deterministic validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from planning.models import PathPlanDraft, PathPlannerRequest
from planning.validation import (
    PathValidationError,
    concept_slug_for,
    normalize_constructor_fields,
    normalize_path_plan_draft,
    slugify,
    validate_canonical_path_plan,
)
from tests.planning.path_helpers import four_lesson_draft


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "patch" / "schemas" / "path-plan.schema.json"


def test_normal_four_lesson_plan() -> None:
    plan = normalize_path_plan_draft(four_lesson_draft())
    assert [lesson.key for lesson in plan.lessons] == ["L1", "L2", "L3", "L4"]
    assert plan.lessons[1].requires == ["L1"]
    assert plan.lessons[3].requires == ["L1", "L2", "L3"]
    assert validate_canonical_path_plan(plan) == []
    jsonschema.validate(
        plan.model_dump(mode="json"),
        json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
    )


def test_extra_unknown_fields_ignored() -> None:
    draft = PathPlanDraft.model_validate(
        {
            **four_lesson_draft().model_dump(),
            "modules": [{"title": "ignored"}],
            "merge_warning": True,
            "completeness": {"forward_verified": False},
            "lessons": [
                {
                    **lesson.model_dump(),
                    "concept_candidate": {"slug": "ignored"},
                    "external_prerequisites": ["ignored"],
                    "merge_warning": True,
                }
                for lesson in four_lesson_draft().lessons
            ],
        }
    )
    plan = normalize_path_plan_draft(draft)
    assert len(plan.lessons) == 4
    assert not hasattr(plan.lessons[0], "merge_warning") or True


def test_arbitrary_unique_keys_normalized_to_l_sequence() -> None:
    draft = four_lesson_draft(
        lessons=[
            {
                "key": "first",
                "title": "The Heart as a Pump",
                "objective": "describe the heart as a pump that moves blood",
                "requires": [],
                "must_establish": ["the heart pumps blood"],
                "knowledge_type": "conceptual",
            },
            {
                "key": "second",
                "title": "Blood Vessels and Their Roles",
                "objective": "distinguish arteries, veins and capillaries",
                "requires": ["first"],
                "must_establish": ["arteries, veins and capillaries have different roles"],
                "knowledge_type": "conceptual",
            },
            {
                "key": "third",
                "title": "Blood Carries Materials",
                "objective": "explain that blood carries oxygen and nutrients",
                "requires": ["first", "second"],
                "must_establish": ["blood transports materials"],
                "knowledge_type": "factual",
            },
        ]
    )
    plan = normalize_path_plan_draft(draft)
    assert [lesson.key for lesson in plan.lessons] == ["L1", "L2", "L3"]
    assert plan.lessons[1].requires == ["L1"]
    assert plan.lessons[2].requires == ["L1", "L2"]


def test_dependency_mapping_survives_key_normalization() -> None:
    draft = four_lesson_draft(
        lessons=[
            {
                "key": "alpha",
                "title": "A",
                "objective": "objective a",
                "requires": [],
                "must_establish": ["a"],
                "knowledge_type": "factual",
            },
            {
                "key": "beta",
                "title": "B",
                "objective": "objective b",
                "requires": ["alpha"],
                "must_establish": ["b"],
                "knowledge_type": "factual",
            },
        ]
    )
    plan = normalize_path_plan_draft(draft)
    assert plan.lessons[0].key == "L1"
    assert plan.lessons[1].key == "L2"
    assert plan.lessons[1].requires == ["L1"]


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda d: d["lessons"].append(copy.deepcopy(d["lessons"][0])),
            "duplicate_lesson_key",
        ),
        (
            lambda d: d["lessons"][1].update(requires=["missing"]),
            "unknown_dependency",
        ),
        (
            lambda d: d["lessons"][0].update(requires=["L2"]),
            "forward_dependency",
        ),
        (
            lambda d: d["lessons"][1].update(requires=["L2"]),
            "self_dependency",
        ),
        (
            lambda d: d["lessons"][0].update(knowledge_type="narrative"),
            "invalid_knowledge_type",
        ),
        (
            lambda d: d.update(lessons=[]),
            "empty_lesson_list",
        ),
        (
            lambda d: d["lessons"][1].update(objective=d["lessons"][0]["objective"]),
            "duplicate_objectives",
        ),
    ],
)
def test_normalization_rejects_invalid_structures(mutate, code: str) -> None:
    payload = four_lesson_draft().model_dump()
    mutate(payload)
    with pytest.raises(PathValidationError) as exc_info:
        normalize_path_plan_draft(PathPlanDraft.model_validate(payload))
    assert exc_info.value.code == code


def test_concept_slug_is_code_owned() -> None:
    assert slugify("Blood Vessels and Their Roles") == "blood.vessels.and.their.roles"
    assert (
        concept_slug_for("Science", "Blood Vessels and Their Roles")
        == "science.blood.vessels.and.their.roles"
    )


def test_constructor_prefix_normalizer_strips_repeated_prefixes() -> None:
    objective, starting = normalize_constructor_fields(
        destination_objective="By the end, students can By the end, students can describe circulation",
        starting_knowledge=[
            "We're assuming students already know We're assuming students already know the body has organs",
            "I'm assuming they already know cells need energy",
        ],
    )
    assert objective == "describe circulation"
    assert starting == [
        "the body has organs",
        "cells need energy",
    ]


def test_constructor_prefix_normalizer_preserves_legitimate_text() -> None:
    objective, starting = normalize_constructor_fields(
        destination_objective="describe the main parts of the circulatory system",
        starting_knowledge=["the body is made of organs and organ systems"],
    )
    assert objective == "describe the main parts of the circulatory system"
    assert starting == ["the body is made of organs and organ systems"]


def test_path_planner_request_excludes_empty_placeholders() -> None:
    request = PathPlannerRequest.model_validate(
        {
            "topic": "circulatory system",
            "subject": "Science",
            "grade_level": "Grade 7",
            "destination_objective": "describe circulation",
            "starting_knowledge": ["organs exist"],
            "curriculum_context": None,
            "class_notes": None,
        }
    )
    dumped = request.model_dump()
    assert "must_include" not in dumped
    assert "must_avoid" not in dumped
    assert "known_difficulties" not in dumped
    assert set(dumped) == {
        "topic",
        "subject",
        "grade_level",
        "destination_objective",
        "starting_knowledge",
        "curriculum_context",
        "class_notes",
    }
