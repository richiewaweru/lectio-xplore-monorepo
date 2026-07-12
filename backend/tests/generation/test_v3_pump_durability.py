from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest

from app import app
from core.auth.middleware import get_current_user
from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from core.entities.user import User
from generation.v3_studio import router as v3_router
from generation.v3_studio.generation_writer import V3GenerationWriter
from generation.v3_studio.router import _pump_sse_to_queue
from httpx import ASGITransport, AsyncClient

TEST_USER = User(
    id="v3-pump-user",
    email="v3pump@example.com",
    name="V3 Pump",
    picture_url=None,
    has_profile=True,
    created_at="2026-03-25T00:00:00+00:00",
    updated_at="2026-03-25T00:00:00+00:00",
)


def _example_bp():
    import json
    from pathlib import Path

    from v3_blueprint.models import ProductionBlueprint

    raw = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "v3_blueprint"
        / "examples"
        / "amara_compound_area.json"
    )
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


async def _override_user() -> User:
    return TEST_USER


async def _ensure_user() -> None:
    async with async_session_factory() as session:
        model = await session.get(UserModel, TEST_USER.id)
        if model is None:
            session.add(
                UserModel(
                    id=TEST_USER.id,
                    email=TEST_USER.email,
                    name=TEST_USER.name,
                    picture_url=None,
                )
            )
            await session.commit()


async def _seed_generation(
    generation_id: str,
    *,
    document_json: dict | None,
) -> None:
    async with async_session_factory() as session:
        session.add(
            GenerationModel(
                id=generation_id,
                user_id=TEST_USER.id,
                subject="Math",
                context="Area",
                mode="v3",
                status="running",
                requested_template_id="guided-concept-path",
                resolved_template_id="guided-concept-path",
                requested_preset_id="v3-studio",
                resolved_preset_id="v3-studio",
                report_json={},
                document_json=document_json,
                section_count=1,
            )
        )
        await session.commit()


async def _load(generation_id: str) -> GenerationModel:
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        return model


async def _drain_background_tasks() -> None:
    pending = [task for task in v3_router._background_tasks if not task.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def _run_pump(generation_id: str, fake_stream) -> asyncio.Queue[str | None]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    with patch("generation.v3_studio.router.sse_event_stream", new=fake_stream):
        await _pump_sse_to_queue(
            queue,
            blueprint=_example_bp(),
            generation_id=generation_id,
            blueprint_id="bp-1",
            template_id="guided-concept-path",
            generation_writer=V3GenerationWriter(async_session_factory),
        )
    await _drain_background_tasks()
    return queue


def _skeleton_chunk(generation_id: str) -> str:
    return (
        "event: skeleton_ready\n"
        'data: {"generation_id":"' + generation_id + '","pack":{'
        '"generation_id":"' + generation_id + '",'
        '"template_id":"guided-concept-path","status":"streaming_preview",'
        '"sections":[{"section_id":"intro","title":"Intro",'
        '"components":[{"component_id":"explanation-card","intent":"Explain"}],'
        '"header":{"title":"Intro"}}]}}\n\n'
    )


@pytest.mark.asyncio
async def test_pump_crash_mid_stream_leaves_failed_terminal_snapshot() -> None:
    """Regression (H1): a pump that dies mid-run must land stage=failed in the DB."""
    await _ensure_user()
    generation_id = str(uuid.uuid4())
    await _seed_generation(generation_id, document_json=None)

    async def broken_stream(**_kwargs):
        yield _skeleton_chunk(generation_id)
        raise RuntimeError("provider connection dropped")

    queue = await _run_pump(generation_id, broken_stream)

    model = await _load(generation_id)
    assert model.status == "failed"
    assert model.error_type == "generation_pump_failure"
    assert "provider connection dropped" in (model.error or "")
    assert model.document_json["progress"]["stage"] == "failed"

    items: list[str | None] = []
    while not queue.empty():
        items.append(queue.get_nowait())
    assert items[-1] is None  # /events consumers still get the close sentinel


@pytest.mark.asyncio
async def test_pump_stream_ending_without_terminal_event_marks_failed() -> None:
    await _ensure_user()
    generation_id = str(uuid.uuid4())
    await _seed_generation(generation_id, document_json=None)

    async def silent_stream(**_kwargs):
        yield _skeleton_chunk(generation_id)

    await _run_pump(generation_id, silent_stream)

    model = await _load(generation_id)
    assert model.status == "failed"
    assert model.document_json["progress"]["stage"] == "failed"


@pytest.mark.asyncio
async def test_pump_normal_terminal_event_is_not_marked_failed() -> None:
    await _ensure_user()
    generation_id = str(uuid.uuid4())
    await _seed_generation(
        generation_id,
        document_json={
            "kind": "v3_booklet_pack",
            "generation_id": generation_id,
            "status": "final_ready",
            "sections": [{"section_id": "intro"}],
            "progress": {"stage": "writing", "sections": {"intro": "ready"}},
        },
    )

    async def finished_stream(**_kwargs):
        yield (
            "event: resource_finalised\n"
            'data: {"generation_id":"' + generation_id + '",'
            '"status":"passed","booklet_status":"final_ready"}\n\n'
        )

    await _run_pump(generation_id, finished_stream)

    model = await _load(generation_id)
    assert model.status == "completed"
    assert model.document_json["progress"]["stage"] == "completed"


@pytest.mark.asyncio
async def test_pump_cancellation_marks_failed_terminal_snapshot() -> None:
    await _ensure_user()
    generation_id = str(uuid.uuid4())
    await _seed_generation(generation_id, document_json=None)

    started = asyncio.Event()

    async def hanging_stream(**_kwargs):
        yield _skeleton_chunk(generation_id)
        started.set()
        await asyncio.sleep(3600)
        yield ""  # pragma: no cover

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    with patch("generation.v3_studio.router.sse_event_stream", new=hanging_stream):
        task = asyncio.create_task(
            _pump_sse_to_queue(
                queue,
                blueprint=_example_bp(),
                generation_id=generation_id,
                blueprint_id="bp-1",
                template_id="guided-concept-path",
                generation_writer=V3GenerationWriter(async_session_factory),
            )
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    await _drain_background_tasks()

    model = await _load(generation_id)
    assert model.status == "failed"
    assert model.document_json["progress"]["stage"] == "failed"


@pytest.mark.asyncio
async def test_pump_component_ready_persists_body_before_draft_pack() -> None:
    """Regression (H2): incremental content must reach the polled snapshot."""
    await _ensure_user()
    generation_id = str(uuid.uuid4())
    await _seed_generation(generation_id, document_json=None)

    async def partial_stream(**_kwargs):
        yield _skeleton_chunk(generation_id)
        yield (
            "event: component_ready\n"
            'data: {"generation_id":"' + generation_id + '",'
            '"component_id":"explanation-card","section_id":"intro","position":0,'
            '"section_field":"explanation","data":{"body":"Live body text"}}\n\n'
        )
        yield (
            "event: question_ready\n"
            'data: {"generation_id":"' + generation_id + '",'
            '"question_id":"q-1","section_id":"intro","difficulty":"medium",'
            '"data":{"question":"How many rectangles?","hints":["Split it"]}}\n\n'
        )
        yield (
            "event: visual_ready\n"
            'data: {"generation_id":"' + generation_id + '",'
            '"visual_id":"vis-1","attaches_to":"intro","frame_index":null,'
            '"image_url":"https://cdn.example/area.png","status":"completed"}\n\n'
        )
        raise RuntimeError("killed before draft_pack_ready")

    await _run_pump(generation_id, partial_stream)

    app.dependency_overrides[get_current_user] = _override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/v3/generations/{generation_id}/document")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    document = resp.json()
    section = document["sections"][0]
    assert section["section_id"] == "intro"
    assert section["explanation"] == {"body": "Live body text"}
    assert section["practice"]["problems"][0]["question"] == "How many rectangles?"
    assert section["diagram"]["image_url"] == "https://cdn.example/area.png"
    assert document["progress"]["stage"] == "failed"
