"""Canonical path contract and prompt-pack coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from planning.models import CanonicalPathPlan, PathPlannerRequest
from planning.prompts import prompt_text


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "handoff" / "fixtures"
PROMPT_PACK = REPO_ROOT / "patch" / "20_PROMPT_PACK.md"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_canonical_fixtures_parse() -> None:
    for name in (
        "grade4-photosynthesis-path.json",
        "grade12-photosynthesis-path.json",
        "grade8-unreachable-destination-path.json",
    ):
        plan = CanonicalPathPlan.model_validate(_fixture(name))
        assert plan.lessons
        assert plan.scope.must_cover
        assert isinstance(plan.scope.do_not_cover, list)


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
