"""Stage B — Path planner repair-loop simulation."""

from __future__ import annotations

import pytest
from tests.planning.path_helpers import four_lesson_draft

from curriculum.agents import run_path_planner
from curriculum.path_models import PathPlanDraft, PathPlannerRequest
from curriculum.validation import PathPlanningError, normalize_path_plan_draft


def _request() -> PathPlannerRequest:
    return PathPlannerRequest(
        topic="circulatory system",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="describe how blood moves around the body",
        starting_knowledge=["the body is made of organs"],
    )


@pytest.mark.asyncio
async def test_planner_repairs_invalid_forward_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    invalid = four_lesson_draft().model_dump()
    invalid["lessons"][0]["requires"] = ["L2"]
    valid = four_lesson_draft()
    calls: list[int] = []

    async def fake_structured(**kwargs):
        calls.append(1)
        if len(calls) == 1:
            return PathPlanDraft.model_validate(invalid)
        return valid

    monkeypatch.setattr("curriculum.agents._run_structured", fake_structured)

    plan = await run_path_planner(_request(), trace_id="repair-ok")
    assert len(calls) == 2
    assert [lesson.key for lesson in plan.lessons] == ["L1", "L2", "L3", "L4"]
    assert plan.lessons[0].requires == []


@pytest.mark.asyncio
async def test_planner_fails_recoverably_after_two_invalid_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = four_lesson_draft().model_dump()
    invalid["lessons"][0]["requires"] = ["L2"]
    calls: list[int] = []

    async def fake_structured(**kwargs):
        calls.append(1)
        return PathPlanDraft.model_validate(invalid)

    monkeypatch.setattr("curriculum.agents._run_structured", fake_structured)

    with pytest.raises(PathPlanningError) as exc_info:
        await run_path_planner(_request(), trace_id="repair-fail")
    assert len(calls) == 2
    assert exc_info.value.errors


@pytest.mark.asyncio
async def test_planner_succeeds_on_first_valid_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def fake_structured(**kwargs):
        calls.append(1)
        return four_lesson_draft()

    monkeypatch.setattr("curriculum.agents._run_structured", fake_structured)

    plan = await run_path_planner(_request(), trace_id="one-shot")
    assert len(calls) == 1
    assert normalize_path_plan_draft(four_lesson_draft()).model_dump() == plan.model_dump()


def _draft_without_modes() -> dict:
    payload = four_lesson_draft().model_dump()
    for lesson in payload["lessons"]:
        lesson.pop("lesson_mode", None)
        lesson.pop("lesson_mode_reason", None)
    return payload


@pytest.mark.asyncio
async def test_missing_lesson_mode_triggers_repair_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads: list[dict] = []
    valid = four_lesson_draft()

    async def fake_structured(**kwargs):
        payloads.append(kwargs["user_payload"])
        if len(payloads) == 1:
            # The structured runner raises the draft's ValidationError.
            return PathPlanDraft.model_validate(_draft_without_modes())
        return valid

    monkeypatch.setattr("curriculum.agents._run_structured", fake_structured)

    plan = await run_path_planner(_request(), trace_id="mode-repair")
    assert len(payloads) == 2
    assert "repair" not in payloads[0]
    errors = payloads[1]["repair"]["validation_errors"]
    assert any("lesson_mode is required for every lesson" in err for err in errors)
    assert all(lesson.lesson_mode == "first_exposure" for lesson in plan.lessons)


@pytest.mark.asyncio
async def test_missing_lesson_mode_after_repair_fails_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def fake_structured(**kwargs):
        calls.append(1)
        return PathPlanDraft.model_validate(_draft_without_modes())

    monkeypatch.setattr("curriculum.agents._run_structured", fake_structured)

    with pytest.raises(PathPlanningError) as exc_info:
        await run_path_planner(_request(), trace_id="mode-fail")
    assert len(calls) == 2
    assert any("lesson_mode is required" in err for err in exc_info.value.errors)
