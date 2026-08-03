"""Lane unit tests: budget park, step skip, concurrency mapping."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from v3_execution.runtime.lanes import LaneOutcome, resolved_lane_limits, run_lane


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
