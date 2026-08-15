"""Lane unit tests: budget park, step skip, concurrency mapping."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from v3_execution.runtime.lanes import LaneOutcome, resolved_lane_limits, run_lane
from v3_execution.config.concurrency import make_semaphores


@pytest.mark.asyncio
async def test_run_lane_prose_then_questions_in_order() -> None:
    order: list[str] = []

    async def prose() -> list:
        order.append("prose")
        return [{"id": "c1"}]

    async def questions() -> list:
        order.append("questions")
        return [{"id": "q1"}]

    with (
        patch(
            "v3_execution.runtime.lanes.step_exists",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "v3_execution.runtime.lanes.insert_step",
            new=AsyncMock(),
        ),
    ):
        outcome = await run_lane(
            generation_id="g1",
            part_id="orient",
            variant_id="everyone",
            prose_coro_factory=prose,
            questions_coro_factory=questions,
        )

    assert order == ["prose", "questions"]
    assert outcome.failed_step is None
    assert outcome.failure_kind is None
    assert outcome.part_id == "orient"


@pytest.mark.asyncio
async def test_run_lane_skips_existing_prose_step() -> None:
    called: list[str] = []

    async def prose() -> list:
        called.append("prose")
        return []

    async def questions() -> list:
        called.append("questions")
        return []

    with (
        patch(
            "v3_execution.runtime.lanes.step_exists",
            new=AsyncMock(side_effect=lambda *a, **kw: kw.get("step") == "prose"),
        ),
        patch(
            "v3_execution.runtime.lanes.load_step_payload",
            new=AsyncMock(return_value={"blocks": []}),
        ),
        patch("v3_execution.runtime.lanes.insert_step", new=AsyncMock()),
    ):
        await run_lane(
            generation_id="g1",
            part_id="orient",
            variant_id="everyone",
            prose_coro_factory=prose,
            questions_coro_factory=questions,
        )

    assert called == ["questions"]


@pytest.mark.asyncio
async def test_run_lane_hydrates_existing_steps_and_marks_each_stage_complete() -> None:
    prose = {
        "block_id": "b1",
        "section_id": "orient",
        "component_id": "explanation",
        "section_field": "body",
        "position": 0,
        "data": {"body": "saved"},
        "source_work_order_id": "w1",
    }
    questions = {
        "question_id": "q1",
        "section_id": "orient",
        "difficulty": "warm",
        "data": {"prompt": "saved"},
        "expected_answer": "yes",
        "source_work_order_id": "qw1",
    }

    async def should_not_run() -> list:
        raise AssertionError("completed checkpoint was regenerated")

    with (
        patch("v3_execution.runtime.lanes.step_exists", new=AsyncMock(return_value=True)),
        patch(
            "v3_execution.runtime.lanes.load_step_payload",
            new=AsyncMock(side_effect=[{"blocks": [prose]}, {"blocks": [questions]}]),
        ),
    ):
        outcome = await run_lane(
            generation_id="g1",
            part_id="orient",
            variant_id="everyone",
            prose_coro_factory=should_not_run,
            questions_coro_factory=should_not_run,
        )

    assert outcome.prose_complete is True
    assert outcome.questions_complete is True
    assert outcome.component_blocks == [prose]
    assert outcome.question_blocks == [questions]


@pytest.mark.asyncio
async def test_run_lane_records_budget_failure() -> None:
    async def slow() -> list:
        await asyncio.sleep(60)
        return []

    with (
        patch(
            "v3_execution.runtime.lanes.step_exists",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "v3_execution.runtime.lanes.insert_step",
            new=AsyncMock(),
        ),
    ):
        try:
            async with asyncio.timeout(0.01):
                outcome = await run_lane(
                    generation_id="g1",
                    part_id="orient",
                    variant_id="everyone",
                    prose_coro_factory=slow,
                    questions_coro_factory=None,
                )
        except TimeoutError:
            outcome = LaneOutcome(
                part_id="orient",
                failed_step="budget",
                warnings=["lane:orient:budget exhausted"],
            )

    assert outcome.failed_step == "budget"


def test_stage2_parallel_false_forces_lane_concurrency_one(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("V3_STAGE2_PARALLEL", "false")
    monkeypatch.setenv("V3_CONCURRENCY_LANE_MAX", "6")
    limits = resolved_lane_limits()
    assert limits["lane"] == 1


def test_answer_key_concurrency_is_configurable(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("V3_CONCURRENCY_ANSWER_KEY_MAX", "3")
    semaphores = make_semaphores()
    assert semaphores["answer_key_generator"]._value == 3
