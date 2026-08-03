from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from planning.agents import run_adjacent_merge_critics
from planning.models import MergeCriticResult, PathPlan, PathPlannerRequest
from planning.prompts import prompt_text
from planning.validation import (
    PathApprovalBlocked,
    PathValidationError,
    assert_approvable,
    normalize_declared_external_prerequisites,
    validate_path_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "handoff" / "fixtures"
SCHEMA_PATH = REPO_ROOT / "patch" / "schemas" / "path-plan.schema.json"
PROMPT_PACK = REPO_ROOT / "patch" / "20_PROMPT_PACK.md"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _prompt_section(number: int, title_pattern: str) -> str:
    source = PROMPT_PACK.read_text(encoding="utf-8")
    match = re.search(
        rf"## {number}\. {title_pattern}.*?### System prompt\s*\n```\n(.*?)\n```",
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    return match.group(1) + "\n"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "grade4-photosynthesis-path.json",
        "grade12-photosynthesis-path.json",
        "grade8-unreachable-destination-path.json",
    ],
)
def test_supplied_path_fixtures_pass_schema_and_machine_checks(fixture_name: str) -> None:
    payload = _fixture(fixture_name)
    jsonschema.validate(payload, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    plan = PathPlan.model_validate(payload)

    validate_path_plan(plan)


def test_grade_scopes_share_no_concept_slug() -> None:
    grade4 = PathPlan.model_validate(_fixture("grade4-photosynthesis-path.json"))
    grade12 = PathPlan.model_validate(_fixture("grade12-photosynthesis-path.json"))

    assert grade4.concept_slugs.isdisjoint(grade12.concept_slugs)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda p: p["modules"][0]["lessons"][1]["concept_candidate"].update(
                slug=p["modules"][0]["lessons"][0]["concept_candidate"]["slug"]
            ),
            "duplicate_concept_slug",
        ),
        (
            lambda p: p["modules"][0]["lessons"][0].update(
                prerequisites=[
                    p["modules"][0]["lessons"][1]["concept_candidate"]["slug"]
                ]
            ),
            "prerequisite_not_earlier",
        ),
        (
            lambda p: p["modules"][0]["lessons"][0].update(
                external_prerequisites=["undeclared capability"]
            ),
            "undeclared_external_prerequisite",
        ),
        (
            lambda p: p["modules"][0]["lessons"][0].update(objective="Explain ATP synthesis."),
            "must_not_introduce_violation",
        ),
        (
            lambda p: p.update(
                prerequisite_risks=[
                    {"missing": "x", "needed_by": "y", "note": "z"}
                ]
            ),
            "risks_require_unreachable",
        ),
    ],
)
def test_machine_checks_reject_silent_path_failures(mutate, code: str) -> None:
    payload = copy.deepcopy(_fixture("grade4-photosynthesis-path.json"))
    mutate(payload)
    plan = PathPlan.model_validate(payload)

    with pytest.raises(PathValidationError) as exc_info:
        validate_path_plan(plan)

    assert exc_info.value.code == code


def test_unreachable_fixture_blocks_approval() -> None:
    plan = PathPlan.model_validate(_fixture("grade8-unreachable-destination-path.json"))

    with pytest.raises(PathApprovalBlocked, match="prerequisite"):
        assert_approvable(plan)


def test_declared_starting_knowledge_is_reclassified_as_external() -> None:
    payload = copy.deepcopy(_fixture("grade4-photosynthesis-path.json"))
    declared = payload["starting_knowledge"][0]
    first_lesson = payload["modules"][0]["lessons"][0]
    first_lesson["prerequisites"] = [declared]
    first_lesson["external_prerequisites"] = []

    normalized = normalize_declared_external_prerequisites(PathPlan.model_validate(payload))

    assert normalized.lessons[0].prerequisites == []
    assert normalized.lessons[0].external_prerequisites == [declared]
    validate_path_plan(normalized)


def test_undeclared_prerequisite_is_not_normalized_away() -> None:
    payload = copy.deepcopy(_fixture("grade4-photosynthesis-path.json"))
    payload["modules"][0]["lessons"][0]["prerequisites"] = ["unknown.capability"]

    normalized = normalize_declared_external_prerequisites(PathPlan.model_validate(payload))

    with pytest.raises(PathValidationError, match="does not resolve"):
        validate_path_plan(normalized)


def test_planner_request_forbids_count_and_duration() -> None:
    request = {
        "topic": "Photosynthesis",
        "subject": "Science",
        "grade_level": "Grade 4",
        "destination_objective": "Explain why photosynthesis matters.",
        "starting_knowledge": ["plants are living things"],
    }
    assert "lesson_count" not in PathPlannerRequest.model_validate(request).model_dump()

    with pytest.raises(ValidationError):
        PathPlannerRequest.model_validate({**request, "lesson_count": 5})
    with pytest.raises(ValidationError):
        PathPlannerRequest.model_validate({**request, "duration_minutes": 120})


@pytest.mark.parametrize(
    ("resource_name", "section", "title_pattern"),
    [
        ("path-planner-v1.txt", 1, "Path Planner"),
        ("merge-critic-v1.txt", 3, "Merge Critic"),
        ("component-selector-v1.txt", 4, "Component Selector"),
        ("path-structural-planner-v1.txt", 5, r"Structural Planner \(rewrite\)"),
    ],
)
def test_phase5_prompts_are_verbatim(resource_name: str, section: int, title_pattern: str) -> None:
    assert prompt_text(resource_name) == _prompt_section(section, title_pattern)


async def test_merge_critic_runs_once_per_nominated_pair(monkeypatch) -> None:
    plan = PathPlan.model_validate(_fixture("grade4-photosynthesis-path.json"))
    assert plan.adjacent_merge_reviews, "fixture must nominate at least one pair"
    calls: list[tuple[str, str]] = []

    async def fake_critic(lesson_a, lesson_b, *, trace_id=None):
        _ = trace_id
        calls.append((lesson_a.concept_candidate.slug, lesson_b.concept_candidate.slug))
        return MergeCriticResult(
            verdict="keep_separate",
            reason="The capabilities remain independently diagnosable.",
            merged_objective=None,
            diagnostic_cost=None,
        )

    monkeypatch.setattr("planning.agents.run_merge_critic", fake_critic)
    results = await run_adjacent_merge_critics(plan, trace_id="fixture")

    expected = {
        (review.lesson_a, review.lesson_b) for review in plan.adjacent_merge_reviews
    }
    assert set(calls) == expected
    assert len(results) == len(expected)


async def test_merge_critic_runs_zero_times_when_nominations_empty(monkeypatch) -> None:
    plan = PathPlan.model_validate(_fixture("grade4-photosynthesis-path.json"))
    plan = plan.model_copy(update={"adjacent_merge_reviews": []})
    for lesson in plan.lessons:
        lesson.merge_warning = False
    calls: list[tuple[str, str]] = []

    async def fake_critic(lesson_a, lesson_b, *, trace_id=None):
        _ = trace_id
        calls.append((lesson_a.concept_candidate.slug, lesson_b.concept_candidate.slug))
        return MergeCriticResult(
            verdict="keep_separate",
            reason="unused",
            merged_objective=None,
            diagnostic_cost=None,
        )

    monkeypatch.setattr("planning.agents.run_merge_critic", fake_critic)
    results = await run_adjacent_merge_critics(plan, trace_id="fixture")

    assert calls == []
    assert results == []
