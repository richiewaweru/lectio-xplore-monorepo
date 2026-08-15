from __future__ import annotations

import pytest

from core.database.models import UserModel
from telemetry.v3_trace import event_types as et
from telemetry.v3_trace.repository import V3TraceRepository
from telemetry.v3_trace.writer import V3TraceWriter


async def _seed_user(db_session_factory, user_id: str = "trace-writer-user") -> None:
    async with db_session_factory() as session:
        existing = await session.get(UserModel, user_id)
        if existing is None:
            session.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    name="Trace Writer",
                    picture_url=None,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_start_run_creates_run_and_first_event(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = V3TraceRepository(db_session_factory)
    writer = V3TraceWriter(
        repository=repo,
        trace_id="tw-trace-1",
        generation_id="tw-gen-1",
    )

    await writer.start_run(
        user_id="trace-writer-user",
        blueprint_id="bp-1",
        template_id="guided-concept-path",
        title="Title",
        subject="Science",
    )

    run = await repo.get_run("tw-trace-1")
    assert run is not None
    assert run.generation_id == "tw-gen-1"
    events = await repo.get_events("tw-trace-1")
    assert len(events) == 1
    assert events[0].event_type == et.GENERATION_START_REQUESTED


@pytest.mark.asyncio
async def test_record_execution_summary_writes_payload(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = V3TraceRepository(db_session_factory)
    writer = V3TraceWriter(
        repository=repo,
        trace_id="tw-trace-2",
        generation_id="tw-gen-2",
    )
    await writer.start_run(
        user_id="trace-writer-user",
        blueprint_id="bp-2",
        template_id="guided-concept-path",
        title="Title",
        subject="Science",
    )

    await writer.record_execution_summary(
        sections_attempted=4,
        sections_succeeded=3,
        sections_failed=1,
        components_planned=10,
        components_delivered=9,
        questions_planned=5,
        questions_delivered=5,
        visuals_planned=2,
        visuals_delivered=1,
        warnings=["warn"],
        failure_kinds={"network": 1},
    )

    full = await repo.get_full_trace("tw-trace-2")
    assert full is not None
    summary_event = next(
        event for event in full["events"] if event["event_type"] == et.EXECUTION_SUMMARY_READY
    )
    assert summary_event["payload"]["sections_attempted"] == 4
    assert summary_event["payload"]["visuals_delivered"] == 1
    assert summary_event["payload"]["failure_kinds"] == {"network": 1}


@pytest.mark.asyncio
async def test_record_visual_failed_writes_canonical_payload(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = V3TraceRepository(db_session_factory)
    writer = V3TraceWriter(
        repository=repo,
        trace_id="tw-trace-visual-failed",
        generation_id="tw-gen-visual-failed",
    )
    await writer.start_run(
        user_id="trace-writer-user",
        blueprint_id="bp-vf",
        template_id="guided-concept-path",
        title="Title",
        subject="Science",
    )

    await writer.record_visual_failed(
        generation_id="tw-gen-visual-failed",
        visual_id="vis-practice-0",
        attaches_to="practice",
        component_id="diagram-block",
        parent_visual_id=None,
        mode="diagram",
        frame_count=1,
        error_summary="provider timeout",
    )

    full = await repo.get_full_trace("tw-trace-visual-failed")
    assert full is not None
    visual_event = next(event for event in full["events"] if event["event_type"] == et.VISUAL_FAILED)
    assert visual_event["payload"] == {
        "generation_id": "tw-gen-visual-failed",
        "visual_id": "vis-practice-0",
        "attaches_to": "practice",
        "component_id": "diagram-block",
        "parent_visual_id": None,
        "mode": "diagram",
        "frame_count": 1,
        "ok": False,
        "error_summary": "provider timeout",
    }


@pytest.mark.asyncio
async def test_record_visual_completed_writes_canonical_payload(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = V3TraceRepository(db_session_factory)
    writer = V3TraceWriter(
        repository=repo,
        trace_id="tw-trace-visual-ready",
        generation_id="tw-gen-visual-ready",
    )
    await writer.start_run(
        user_id="trace-writer-user",
        blueprint_id="bp-vc",
        template_id="guided-concept-path",
        title="Title",
        subject="Science",
    )

    await writer.record_visual_completed(
        generation_id="tw-gen-visual-ready",
        visual_id="vis-model-0",
        attaches_to="model",
        component_id="diagram-series",
        parent_visual_id=None,
        mode="diagram_series",
        frame_count=3,
    )

    full = await repo.get_full_trace("tw-trace-visual-ready")
    assert full is not None
    visual_event = next(
        event for event in full["events"] if event["event_type"] == et.VISUAL_COMPLETED
    )
    assert visual_event["payload"] == {
        "generation_id": "tw-gen-visual-ready",
        "visual_id": "vis-model-0",
        "attaches_to": "model",
        "component_id": "diagram-series",
        "parent_visual_id": None,
        "mode": "diagram_series",
        "frame_count": 3,
        "ok": True,
    }


@pytest.mark.asyncio
async def test_record_booklet_status_dedupes_unchanged_status(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = V3TraceRepository(db_session_factory)
    writer = V3TraceWriter(
        repository=repo,
        trace_id="tw-trace-3",
        generation_id="tw-gen-3",
    )
    await writer.start_run(
        user_id="trace-writer-user",
        blueprint_id="bp-3",
        template_id="guided-concept-path",
        title="Title",
        subject="Science",
    )

    await writer.record_booklet_status(
        booklet_status="draft_ready",
        reason="first",
        draft_available=True,
        final_available=False,
        classroom_ready=False,
        export_allowed=True,
    )
    await writer.record_booklet_status(
        booklet_status="draft_ready",
        reason="duplicate",
        draft_available=True,
        final_available=False,
        classroom_ready=False,
        export_allowed=True,
    )

    events = await repo.get_events("tw-trace-3")
    statuses = [event for event in events if event.event_type == et.BOOKLET_STATUS_ASSIGNED]
    assert len(statuses) == 1


@pytest.mark.asyncio
async def test_record_terminal_retries_once_then_succeeds() -> None:
    class FlakyRepo:
        def __init__(self) -> None:
            self.append_calls = 0
            self.updated = False

        async def append_event(self, **_kwargs) -> None:
            self.append_calls += 1
            if self.append_calls == 1:
                raise RuntimeError("first failure")

        async def update_report(self, **_kwargs) -> None:
            self.updated = True

    repo = FlakyRepo()
    writer = V3TraceWriter(
        repository=repo,  # type: ignore[arg-type]
        trace_id="tw-trace-4",
        generation_id="tw-gen-4",
    )

    await writer.record_terminal(
        terminal_event_type=et.RESOURCE_FINALISED,
        process_status="completed",
        booklet_status="final_ready",
        draft_available=True,
        final_available=True,
        classroom_ready=True,
        export_allowed=True,
        error_summary=None,
    )

    assert repo.append_calls == 2
    assert repo.updated is True
