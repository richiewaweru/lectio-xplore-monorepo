"""Legacy PathPlan helpers and non-critical-path merge critic coverage.

Active planner contract tests live in test_canonical_path.py and
test_path_planner_repair.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from planning.agents import run_adjacent_merge_critics
from planning.models import MergeCriticResult, PathPlan, PathPlannerRequest
from planning.prompts import prompt_text
from planning.validation import (
    PathApprovalBlocked,
    assert_approvable,
    normalize_declared_external_prerequisites,
    validate_path_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "handoff" / "fixtures"
PROMPT_PACK = REPO_ROOT / "patch" / "20_PROMPT_PACK.md"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_legacy_fixtures_still_parse_as_path_plan() -> None:
    for name in (
        "grade4-photosynthesis-path.json",
        "grade12-photosynthesis-path.json",
        "grade8-unreachable-destination-path.json",
    ):
        plan = PathPlan.model_validate(_fixture(name))
        assert plan.lessons


def test_legacy_unreachable_fixture_blocks_legacy_assert_approvable() -> None:
    plan = PathPlan.model_validate(_fixture("grade8-unreachable-destination-path.json"))
    with pytest.raises(PathApprovalBlocked):
        assert_approvable(plan)


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


def test_legacy_normalize_moves_declared_starting_knowledge() -> None:
    payload = _fixture("grade4-photosynthesis-path.json")
    declared = payload["starting_knowledge"][0]
    first_lesson = payload["modules"][0]["lessons"][0]
    first_lesson["prerequisites"] = [declared]
    first_lesson["external_prerequisites"] = []

    normalized = normalize_declared_external_prerequisites(PathPlan.model_validate(payload))
    assert normalized.lessons[0].prerequisites == []
    assert declared in normalized.lessons[0].external_prerequisites
    validate_path_plan(normalized)


@pytest.mark.parametrize(
    ("resource_name", "section", "title_pattern"),
    [
        ("path-structural-planner-v1.txt", 5, r"Structural Planner \(rewrite\)"),
    ],
)
def test_phase5_prompts_are_verbatim(resource_name: str, section: int, title_pattern: str) -> None:
    import re

    source = PROMPT_PACK.read_text(encoding="utf-8")
    match = re.search(
        rf"## {section}\. {title_pattern}.*?### System prompt\s*\n```\n(.*?)\n```",
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    assert prompt_text(resource_name) == match.group(1) + "\n"


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
