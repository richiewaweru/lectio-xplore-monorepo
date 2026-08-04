from __future__ import annotations

import pytest

from core.database.models import UserModel
from telemetry.v3_trace.event_types import BLUEPRINT_GENERATED, GENERATION_COMPLETED
from telemetry.v3_trace.repository import V3TraceRepository


async def _seed_user(db_session_factory, user_id: str = "u-01") -> None:
    async with db_session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                name="Trace User",
                picture_url=None,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_create_run_and_append_events(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = V3TraceRepository(db_session_factory)

    await repo.create_run(
        trace_id="t-01",
        user_id="u-01",
        title="Pythagorean Theorem",
        subject="Mathematics",
    )

    await repo.append_event(
        trace_id="t-01",
        phase="blueprint",
        event_type=BLUEPRINT_GENERATED,
        payload={"blueprint_id": "b-01", "section_count": 3, "lens_ids": ["first_exposure"]},
    )
    await repo.append_event(
        trace_id="t-01",
        phase="terminal",
        event_type=GENERATION_COMPLETED,
        payload={
            "status": "completed",
            "sections_ready": 3,
            "sections_failed": 0,
            "duration_seconds": 143.2,
            "total_cost_usd": 0.91,
            "llm_summary": {},
        },
    )

    trace = await repo.get_full_trace("t-01")
    assert trace is not None
    assert trace["title"] == "Pythagorean Theorem"
    assert len(trace["events"]) == 2
    assert trace["events"][0]["event_type"] == BLUEPRINT_GENERATED
    assert trace["events"][0]["sequence"] == 1
    assert trace["events"][1]["sequence"] == 2


@pytest.mark.asyncio
async def test_bind_generation(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = V3TraceRepository(db_session_factory)

    await repo.create_run(trace_id="t-02", user_id="u-01")
    await repo.bind_generation(trace_id="t-02", generation_id="g-99")

    run = await repo.get_run("t-02")
    assert run is not None
    assert run.generation_id == "g-99"
    assert run.status == "generating"

    by_generation = await repo.get_run_by_generation("g-99")
    assert by_generation is not None
    assert by_generation.trace_id == "t-02"


@pytest.mark.asyncio
async def test_update_report_written_at_boundary(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = V3TraceRepository(db_session_factory)

    await repo.create_run(trace_id="t-03", user_id="u-01")

    run = await repo.get_run("t-03")
    assert run is not None
    assert run.report_json is None

    await repo.update_report(
        trace_id="t-03",
        report={"terminal": {"status": "completed"}},
        status="completed",
    )

    run = await repo.get_run("t-03")
    assert run is not None
    assert run.report_json is not None
    assert run.status == "completed"
