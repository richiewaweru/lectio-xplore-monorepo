from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from core.auth.middleware import get_current_user
from core.events import TraceClosedEvent, TraceRegisteredEvent
from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from core.entities.user import User
from generation.v3_studio import router as v3_router
from generation.v3_studio.dtos import V3InputForm
from generation.v3_studio.planning_artifact import (
    SCHEMA_VERSION,
    build_planning_artifact,
    parse_planning_artifact,
)
from generation.v3_studio.session_store import v3_studio_store
from generation.v3_studio.router import _pump_sse_to_queue
from telemetry.v3_trace import event_types as trace_events
from telemetry.v3_trace.repository import V3TraceRepository

TEST_USER_A = User(
    id="v3-studio-user-a",
    email="v3a@example.com",
    name="V3 Studio A",
    picture_url=None,
    has_profile=True,
    created_at="2026-03-25T00:00:00+00:00",
    updated_at="2026-03-25T00:00:00+00:00",
)

TEST_USER_B = User(
    id="v3-studio-user-b",
    email="v3b@example.com",
    name="V3 Studio B",
    picture_url=None,
    has_profile=True,
    created_at="2026-03-25T00:00:00+00:00",
    updated_at="2026-03-25T00:00:00+00:00",
)


def _example_bp(name: str):
    from v3_blueprint.models import ProductionBlueprint

    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / name
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


async def _override_user_a() -> User:
    return TEST_USER_A


async def _override_user_b() -> User:
    return TEST_USER_B


async def _ensure_user(user: User) -> None:
    async with async_session_factory() as session:
        model = await session.get(UserModel, user.id)
        if model is None:
            session.add(
                UserModel(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    picture_url=user.picture_url,
                )
            )
            await session.commit()


async def _upsert_generation_row(
    *,
    generation_id: str,
    user_id: str,
    document_json: dict | None,
    report_json: dict | None = None,
    mode: str = "v3",
    requested_preset_id: str = "v3-studio",
    status: str = "running",
    subject: str = "Math",
    context: str = "Algebra",
    section_count: int | None = None,
) -> None:
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        if model is None:
            model = GenerationModel(
                id=generation_id,
                user_id=user_id,
                subject=subject,
                context=context,
                mode=mode,
                status=status,
                requested_template_id="guided-concept-path",
                resolved_template_id="guided-concept-path",
                requested_preset_id=requested_preset_id,
                resolved_preset_id=requested_preset_id,
                report_json=report_json or {},
                document_json=document_json,
                section_count=section_count,
            )
            session.add(model)
        else:
            model.user_id = user_id
            model.document_json = document_json
            model.report_json = report_json or {}
            model.mode = mode
            model.status = status
            model.subject = subject
            model.context = context
            model.requested_preset_id = requested_preset_id
            model.resolved_preset_id = requested_preset_id
            model.section_count = section_count
        await session.commit()


async def _write_planning_artifact(generation_id: str, artifact: dict) -> None:
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        model.planning_spec_json = json.dumps(artifact)
        await session.commit()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _reset_app_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_v3_generate_start_returns_json_and_sse_stream_closes() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    await v3_studio_store.put_blueprint(TEST_USER_A.id, blueprint_id, bp, "guided-concept-path")

    async def fake_pump(queue, *, blueprint, generation_id, blueprint_id, template_id, **_kwargs):
        _ = blueprint, generation_id, blueprint_id, template_id
        await queue.put("event: component_ready\ndata: {}\n\n")
        await queue.put(None)

    with patch("generation.v3_studio.router._pump_sse_to_queue", new=fake_pump):
        async with _client() as client:
            post = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                    "template_id": "guided-concept-path",
                },
            )
            assert post.status_code == 200
            assert post.json() == {"generation_id": generation_id}

            async with client.stream(
                "GET",
                f"/api/v1/v3/generations/{generation_id}/events",
            ) as resp:
                assert resp.status_code == 200
                payload = await resp.aread()
                assert b"component_ready" in payload

    assert await v3_studio_store.get_generation_queue(generation_id) is None


@pytest.mark.asyncio
async def test_v3_generation_events_emit_heartbeat_before_late_chunk() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await v3_studio_store.register_generation_stream(
        user_id=TEST_USER_A.id,
        generation_id=generation_id,
        blueprint_id=f"bp-{generation_id}",
        queue=queue,
    )

    async def delayed_emit() -> None:
        await asyncio.sleep(0.03)
        await queue.put("event: component_ready\ndata: {}\n\n")
        await queue.put(None)

    with patch.object(v3_router, "HEARTBEAT_SECONDS", 0.01):
        producer = asyncio.create_task(delayed_emit())
        async with _client() as client:
            async with client.stream(
                "GET",
                f"/api/v1/v3/generations/{generation_id}/events",
            ) as resp:
                assert resp.status_code == 200
                payload = await resp.aread()
        await producer

    assert b": ping\n\n" in payload
    assert b"component_ready" in payload
    assert await v3_studio_store.get_generation_queue(generation_id) is None


@pytest.mark.asyncio
async def test_v3_generate_start_conflict_when_generation_id_reused() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    await v3_studio_store.put_blueprint(TEST_USER_A.id, blueprint_id, bp, "guided-concept-path")

    async def fake_pump(queue, **_kwargs):
        await queue.put(None)

    with patch("generation.v3_studio.router._pump_sse_to_queue", new=fake_pump):
        async with _client() as client:
            first = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                },
            )
            assert first.status_code == 200
            second = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                },
            )
            assert second.status_code == 409


@pytest.mark.asyncio
async def test_v3_generation_events_forbidden_for_other_user() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    await _ensure_user(TEST_USER_B)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    await v3_studio_store.put_blueprint(TEST_USER_A.id, blueprint_id, bp, "guided-concept-path")

    async def fake_pump(queue, **_kwargs):
        await queue.put(None)

    with patch("generation.v3_studio.router._pump_sse_to_queue", new=fake_pump):
        async with _client() as client:
            await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                },
            )

    app.dependency_overrides[get_current_user] = _override_user_b

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/events")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_v3_generate_start_creates_trace_before_stream_open() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    await v3_studio_store.put_blueprint(TEST_USER_A.id, blueprint_id, bp, "guided-concept-path")

    async def fake_pump(queue, **_kwargs):
        await queue.put(None)

    with patch("generation.v3_studio.router._pump_sse_to_queue", new=fake_pump):
        async with _client() as client:
            post = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                    "template_id": "guided-concept-path",
                },
            )
            assert post.status_code == 200

    repo = V3TraceRepository(async_session_factory)
    run = await repo.get_run_by_generation(generation_id)
    assert run is not None
    events = await repo.get_events(run.trace_id)
    event_types = [event.event_type for event in events]
    assert trace_events.GENERATION_START_REQUESTED in event_types
    assert trace_events.BLUEPRINT_SNAPSHOT_SAVED in event_types


@pytest.mark.asyncio
async def test_v3_generate_start_fails_when_trace_initialization_fails() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    await v3_studio_store.put_blueprint(TEST_USER_A.id, blueprint_id, bp, "guided-concept-path")

    with patch(
        "generation.v3_studio.router.V3TraceWriter.start_run",
        side_effect=RuntimeError("trace down"),
    ):
        async with _client() as client:
            post = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                    "template_id": "guided-concept-path",
                },
            )
            assert post.status_code == 500
            assert "could not start generation" in post.json()["detail"].lower()

    assert await v3_studio_store.get_generation_queue(generation_id) is None


@pytest.mark.asyncio
async def test_v3_trace_endpoints_are_user_scoped() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    await _ensure_user(TEST_USER_B)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    await v3_studio_store.put_blueprint(TEST_USER_A.id, blueprint_id, bp, "guided-concept-path")

    async def fake_pump(queue, **_kwargs):
        await queue.put(None)

    with patch("generation.v3_studio.router._pump_sse_to_queue", new=fake_pump):
        async with _client() as client:
            post = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                    "template_id": "guided-concept-path",
                },
            )
            assert post.status_code == 200

            by_generation = await client.get(f"/api/v1/v3/generations/{generation_id}/trace")
            assert by_generation.status_code == 200
            body = by_generation.json()
            assert body["generation_id"] == generation_id
            assert body["trace_id"]

            by_trace = await client.get(f"/api/v1/v3/traces/{body['trace_id']}")
            assert by_trace.status_code == 200
            assert by_trace.json()["trace_id"] == body["trace_id"]

    app.dependency_overrides[get_current_user] = _override_user_b
    async with _client() as client:
        other_user_resp = await client.get(f"/api/v1/v3/generations/{generation_id}/trace")
        assert other_user_resp.status_code == 404


@pytest.mark.asyncio
async def test_v3_document_endpoint_returns_persisted_document_for_owner() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "v3_booklet_pack",
            "generation_id": generation_id,
            "template_id": "guided-concept-path",
            "status": "draft_ready",
            "sections": [{"section_id": "s-1", "header": {"title": "Intro"}}],
        },
    )

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/document")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.json()["sections"][0]["section_id"] == "s-1"


@pytest.mark.asyncio
async def test_v3_document_endpoint_returns_persisted_skeleton_document() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "v3_booklet_pack",
            "generation_id": generation_id,
            "template_id": "guided-concept-path",
            "status": "streaming_preview",
            "sections": [
                {
                    "section_id": "skeleton-1",
                    "template_id": "guided-concept-path",
                    "title": "Skeleton 1",
                    "components": [{"component_id": "explanation-card", "intent": "Explain"}],
                }
            ],
        },
    )

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/document")
    assert resp.status_code == 200
    assert resp.json()["status"] == "streaming_preview"
    assert resp.json()["sections"][0]["section_id"] == "skeleton-1"


@pytest.mark.asyncio
async def test_v3_document_endpoint_forbidden_for_other_user() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    await _ensure_user(TEST_USER_B)

    generation_id = str(uuid.uuid4())
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "v3_booklet_pack",
            "generation_id": generation_id,
            "sections": [{"section_id": "s-1"}],
        },
    )

    app.dependency_overrides[get_current_user] = _override_user_b
    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/document")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_v3_document_endpoint_missing_when_document_has_no_sections() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={"kind": "v3_booklet_pack", "sections": []},
    )

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/document")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_v3_visual_regenerate_replaces_visual_block_and_section_diagram() -> None:
    from v3_execution.compile_orders import compile_execution_bundle
    from v3_execution.models import GeneratedVisualBlock

    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    blueprint_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    bundle = compile_execution_bundle(
        bp,
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        template_id="guided-concept-path",
    )
    order = next(o for o in bundle.visual_orders if o.visual.attaches_to == "practice")
    old_block = GeneratedVisualBlock(
        visual_id=order.visual.id,
        attaches_to=order.visual.attaches_to,
        mode=order.visual.mode,
        image_url="https://cdn.example/old.png",
        caption="old caption",
        alt_text="old alt",
        source_work_order_id=order.work_order_id,
        component_id=order.visual.component_id,
    )
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "v3_booklet_pack",
            "generation_id": generation_id,
            "blueprint_id": blueprint_id,
            "template_id": "guided-concept-path",
            "subject": bp.metadata.subject,
            "status": "draft_ready",
            "sections": [
                {
                    "section_id": order.visual.attaches_to,
                    "template_id": "guided-concept-path",
                    "title": "Practice",
                    "diagram": {
                        "image_url": "https://cdn.example/old.png",
                        "caption": "old caption",
                        "alt_text": "old alt",
                    },
                }
            ],
            "visual_blocks": [old_block.model_dump(mode="json", exclude_none=True)],
            "warnings": [],
        },
    )
    await _write_planning_artifact(
        generation_id,
        build_planning_artifact(
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            template_id="guided-concept-path",
            blueprint=bp,
            form=None,
        ),
    )

    async def fake_execute_visual(regenerated_order, emit, **_kwargs):
        await emit("visual_ready", {})
        assert regenerated_order.work_order_id == order.work_order_id
        assert "Correction: make it cleaner" in regenerated_order.visual.purpose
        return [
            GeneratedVisualBlock(
                visual_id=order.visual.id,
                attaches_to=order.visual.attaches_to,
                mode=order.visual.mode,
                image_url="https://cdn.example/new.png",
                caption="new caption",
                alt_text="new alt",
                source_work_order_id=order.work_order_id,
                component_id=order.visual.component_id,
            )
        ]

    with patch("generation.v3_studio.router.execute_visual", side_effect=fake_execute_visual):
        async with _client() as client:
            resp = await client.post(
                f"/api/v1/v3/generations/{generation_id}/visuals/{order.visual.id}/regenerate",
                json={"teacher_hint": "make it cleaner"},
            )

    assert resp.status_code == 200
    assert resp.json()["image_url"] == "https://cdn.example/new.png"

    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        persisted = model.document_json
    assert persisted["visual_blocks"][0]["image_url"] == "https://cdn.example/new.png"
    assert persisted["sections"][0]["diagram"]["image_url"] == "https://cdn.example/new.png"
    assert persisted["sections"][0]["diagram"]["caption"] == "new caption"


@pytest.mark.asyncio
async def test_v3_visual_regenerate_returns_404_for_unknown_visual() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "v3_booklet_pack",
            "generation_id": generation_id,
            "sections": [{"section_id": "s-1"}],
            "visual_blocks": [],
        },
    )

    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{generation_id}/visuals/missing/regenerate",
            json={},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_v3_visual_regenerate_returns_409_when_generation_lock_busy() -> None:
    generation_id = str(uuid.uuid4())
    lock = asyncio.Lock()
    await lock.acquire()
    v3_router._visual_regenerate_locks[generation_id] = lock
    app.dependency_overrides[get_current_user] = _override_user_a

    try:
        async with _client() as client:
            resp = await client.post(
                f"/api/v1/v3/generations/{generation_id}/visuals/vis-1/regenerate",
                json={},
            )
    finally:
        lock.release()
        v3_router._visual_regenerate_locks.pop(generation_id, None)

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_v3_generation_list_and_detail_are_user_scoped_and_v3_filtered() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    await _ensure_user(TEST_USER_B)

    a_v3_id = str(uuid.uuid4())
    a_v3_preset_id = str(uuid.uuid4())
    a_v2_id = str(uuid.uuid4())
    b_v3_id = str(uuid.uuid4())

    await _upsert_generation_row(
        generation_id=a_v3_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "v3_booklet_pack",
            "status": "final_ready",
            "sections": [{"section_id": "s-1"}],
        },
        report_json={"booklet_status": "final_ready"},
        mode="v3",
        requested_preset_id="v3-studio",
        status="completed",
        subject="Science",
        context="Photosynthesis",
        section_count=3,
    )
    await _upsert_generation_row(
        generation_id=a_v3_preset_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "v3_booklet_pack",
            "status": "draft_ready",
            "sections": [{"section_id": "s-2"}],
        },
        report_json={"booklet_status": "draft_ready"},
        mode="balanced",
        requested_preset_id="v3-studio",
        status="running",
        subject="Math",
        context="Fractions",
        section_count=2,
    )
    await _upsert_generation_row(
        generation_id=a_v2_id,
        user_id=TEST_USER_A.id,
        document_json=None,
        report_json={},
        mode="balanced",
        requested_preset_id="blue-classroom",
        status="completed",
    )
    await _upsert_generation_row(
        generation_id=b_v3_id,
        user_id=TEST_USER_B.id,
        document_json={
            "kind": "v3_booklet_pack",
            "status": "final_ready",
            "sections": [{"section_id": "s-3"}],
        },
        report_json={"booklet_status": "final_ready"},
        mode="v3",
        requested_preset_id="v3-studio",
        status="completed",
    )

    async with _client() as client:
        list_resp = await client.get("/api/v1/v3/generations")
        assert list_resp.status_code == 200
        payload = list_resp.json()
        ids = [item["id"] for item in payload]
        assert a_v3_id in ids
        assert a_v3_preset_id in ids
        assert a_v2_id not in ids
        assert b_v3_id not in ids
        assert payload[0]["id"] == a_v3_preset_id
        assert payload[1]["id"] == a_v3_id

        detail_resp = await client.get(f"/api/v1/v3/generations/{a_v3_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == a_v3_id
        assert detail["title"] == "Photosynthesis"
        assert detail["booklet_status"] == "final_ready"
        assert detail["section_count"] == 3
        assert detail["document_section_count"] == 1

    app.dependency_overrides[get_current_user] = _override_user_b
    async with _client() as client:
        forbidden = await client.get(f"/api/v1/v3/generations/{a_v3_id}")
        assert forbidden.status_code == 404


@pytest.mark.asyncio
async def test_v3_generation_detail_returns_404_for_non_v3_row() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "pipeline_document",
            "sections": [{"section_id": "s-1"}],
        },
        mode="balanced",
        requested_preset_id="blue-classroom",
        status="completed",
    )

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_v3_pdf_export_surfaces_actionable_error_detail() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    await v3_studio_store.put_blueprint(TEST_USER_A.id, blueprint_id, bp, "guided-concept-path")
    await v3_studio_store.register_generation_stream(
        user_id=TEST_USER_A.id,
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        queue=asyncio.Queue(),
    )
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={
            "kind": "v3_booklet_pack",
            "generation_id": generation_id,
            "template_id": "guided-concept-path",
            "status": "draft_ready",
            "subject": "Math",
            "sections": [{"section_id": "intro", "header": {"title": "Intro"}}],
            "warnings": [],
            "section_diagnostics": [],
            "booklet_issues": [],
        },
    )

    with patch(
        "generation.v3_studio.router.export_v3_studio_pdf",
        side_effect=RuntimeError("playwright timed out while rendering print page"),
    ):
        async with _client() as client:
            resp = await client.post(
                f"/api/v1/v3/generations/{generation_id}/export/pdf",
                json={
                    "school_name": "School",
                    "teacher_name": "Teacher",
                    "include_toc": False,
                    "include_answers": True,
                },
            )

    assert resp.status_code == 500
    body = resp.json()["detail"]
    assert isinstance(body, dict)
    assert body["message"].startswith("RuntimeError:")
    assert "playwright timed out" in body["message"]
    assert body["debug"] == {}


@pytest.mark.asyncio
async def test_pump_sse_parses_events_and_dispatches_generation_writer() -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    generation_writer = AsyncMock()
    bp = _example_bp("amara_compound_area.json")

    async def fake_stream(**_kwargs):
        yield (
            'event: skeleton_ready\n'
            'data: {"generation_id":"gen-1","section_count":1,"booklet_status":"streaming_preview","pack":{"generation_id":"gen-1","blueprint_id":"bp-1","template_id":"guided-concept-path","subject":"Mathematics","status":"streaming_preview","sections":[{"section_id":"intro","template_id":"guided-concept-path","title":"Intro","components":[]}],"warnings":[],"section_diagnostics":[],"booklet_issues":[]}}\n\n'
        )
        yield (
            'event: section_ready\n'
            'data: {"generation_id":"gen-1","section_id":"intro","booklet_status":"streaming_preview","pack":{"generation_id":"gen-1","blueprint_id":"bp-1","template_id":"guided-concept-path","subject":"Mathematics","status":"streaming_preview","sections":[{"section_id":"intro","template_id":"guided-concept-path","header":{"title":"Intro"},"explanation":{"body":"Ready"}}],"warnings":[],"section_diagnostics":[],"booklet_issues":[]}}\n\n'
        )
        yield (
            'event: coherence_review_started\n'
            'data: {"generation_id":"gen-1"}\n\n'
        )
        yield (
            'event: draft_pack_ready\n'
            'data: {"generation_id":"gen-1","booklet_status":"draft_ready","pack":{"generation_id":"gen-1","blueprint_id":"bp-1","template_id":"guided-concept-path","subject":"Mathematics","status":"draft_ready","sections":[],"warnings":[],"section_diagnostics":[],"booklet_issues":[]}}\n\n'
        )
        yield (
            'event: coherence_report_ready\n'
            'data: {"generation_id":"gen-1","status":"failed","coherence_report":{"status":"failed","blocking_count":2,"major_count":0,"minor_count":0,"issues":[{"issue_id":"i-1"}]}}\n\n'
        )
        yield (
            'event: generation_complete\n'
            'data: {"generation_id":"gen-1","coherence_review":{"status":"passed","blocking_count":0}}\n\n'
        )
        yield (
            'event: coherence_report_ready\n'
            'data: {"generation_id":"gen-1","status":"passed","blocking_count":0,"major_count":0,"minor_count":0}\n\n'
        )
        yield (
            'event: resource_finalised\n'
            'data: {"generation_id":"gen-1","status":"passed","booklet_status":"final_ready"}\n\n'
        )

    with patch("generation.v3_studio.router.sse_event_stream", new=fake_stream):
        await _pump_sse_to_queue(
            queue,
            blueprint=bp,
            generation_id="gen-1",
            blueprint_id="bp-1",
            template_id="guided-concept-path",
            generation_writer=generation_writer,
        )

    assert generation_writer.write_draft.await_count == 3
    first_draft_payload = generation_writer.write_draft.await_args_list[0].args[1]
    assert first_draft_payload["pack"]["status"] == "streaming_preview"
    assert first_draft_payload["pack"]["sections"][0]["section_id"] == "intro"
    assert first_draft_payload["pack"]["progress"]["stage"] == "writing"
    section_payload = generation_writer.write_draft.await_args_list[1].args[1]
    assert section_payload["pack"]["progress"]["sections"]["intro"] == "ready"
    generation_writer.update_document_progress_stage.assert_any_await(
        "gen-1",
        stage="reviewing",
    )
    generation_writer.update_document_progress_stage.assert_any_await(
        "gen-1",
        stage="completed",
    )
    assert generation_writer.write_coherence_result.await_count == 2
    generation_writer.write_generation_complete.assert_awaited_once()
    generation_writer.write_resource_finalised.assert_awaited_once()

    streamed: list[str | None] = []
    while not queue.empty():
        streamed.append(queue.get_nowait())
    assert any(isinstance(item, str) and "draft_pack_ready" in item for item in streamed)
    assert streamed[-1] is None


@pytest.mark.asyncio
async def test_v3_generate_start_persists_planning_artifact_before_stream() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    form = V3InputForm(
        grade_level="Grade 8",
        subject="Mathematics",
        duration_minutes=50,
        topic="Compound area",
        resource_type="lesson",
        outcome="Students can find the area of compound shapes.",
        struggle="They miss one of the rectangles when splitting the shape.",
    )
    await v3_studio_store.put_blueprint(
        TEST_USER_A.id,
        blueprint_id,
        bp,
        "guided-concept-path",
        form=form,
    )

    async def fake_pump(queue, **_kwargs):
        await queue.put(None)

    with patch("generation.v3_studio.router._pump_sse_to_queue", new=fake_pump):
        async with _client() as client:
            post = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                    "template_id": "guided-concept-path",
                },
            )
            assert post.status_code == 200

    async with async_session_factory() as session:
        result = await session.execute(
            select(GenerationModel).where(GenerationModel.id == generation_id)
        )
        model = result.scalar_one_or_none()
        assert model is not None
        artifact = parse_planning_artifact(model.planning_spec_json)
        assert artifact is not None
        assert artifact["schema_version"] == SCHEMA_VERSION
        assert artifact["blueprint_id"] == blueprint_id
        assert artifact["form"]["topic"] == "Compound area"
        planning = model.report_json.get("planning") if isinstance(model.report_json, dict) else None
        assert isinstance(planning, dict)
        assert planning["has_full_planning_artifact"] is True
        assert planning["blueprint_id"] == blueprint_id


@pytest.mark.asyncio
async def test_v3_generation_detail_exposes_planning_artifact() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    blueprint_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    artifact = build_planning_artifact(
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        template_id="guided-concept-path",
        blueprint=bp,
        form=None,
    )
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json=None,
        report_json={"booklet_status": "final_ready", "planning": {"blueprint_id": blueprint_id}},
        mode="v3",
        status="completed",
        subject=bp.metadata.subject,
        context=bp.metadata.title,
        section_count=len(bp.sections),
    )
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        model.planning_spec_json = json.dumps(artifact)
        await session.commit()

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["blueprint_id"] == blueprint_id
    assert detail["planning_artifact"]["blueprint_id"] == blueprint_id
    assert isinstance(detail["planning_artifact"]["blueprint"], dict)
    assert detail["report_json"]["planning"]["blueprint_id"] == blueprint_id


@pytest.mark.asyncio
async def test_v3_generation_detail_without_planning_artifact_is_compatible() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json=None,
        report_json={"booklet_status": "streaming_preview"},
        mode="v3",
        status="running",
    )

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["planning_artifact"] is None
    assert detail["blueprint_id"] is None


@pytest.mark.asyncio
async def test_v3_generation_blueprint_endpoint_uses_db_after_session_store_missing() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    blueprint_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    form = V3InputForm(
        grade_level="Grade 8",
        subject="Mathematics",
        duration_minutes=50,
        topic="Compound area",
        resource_type="lesson",
        outcome="Students can find the area of compound shapes.",
        struggle="They miss one of the rectangles when splitting the shape.",
    )
    artifact = build_planning_artifact(
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        template_id="guided-concept-path",
        blueprint=bp,
        form=form,
    )
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json=None,
        report_json={},
        mode="v3",
        status="completed",
        subject=bp.metadata.subject,
        context=bp.metadata.title,
        section_count=len(bp.sections),
    )
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        model.planning_spec_json = json.dumps(artifact)
        await session.commit()

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/blueprint")
    assert resp.status_code == 200
    preview = resp.json()
    assert preview["blueprint_id"] == blueprint_id
    assert preview["title"] == bp.metadata.title
    assert preview["learner_context"]["grade_level"] == "Grade 8"
    assert len(preview["section_plan"]) == len(bp.sections)


@pytest.mark.asyncio
async def test_v3_generation_blueprint_endpoint_forbidden_for_other_user() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    await _ensure_user(TEST_USER_B)

    generation_id = str(uuid.uuid4())
    blueprint_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    artifact = build_planning_artifact(
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        template_id="guided-concept-path",
        blueprint=bp,
        form=None,
    )
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json=None,
        report_json={},
        mode="v3",
        status="completed",
    )
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        model.planning_spec_json = json.dumps(artifact)
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user_b
    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/blueprint")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_blueprint_adjust_preserves_planning_source() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    parent_generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")

    planning_source = {
        "kind": "supplement",
        "parent_generation_id": parent_generation_id,
        "parent_blueprint_id": "bp-parent-123",
        "target_resource_type": "exit_ticket",
    }

    await v3_studio_store.put_blueprint(
        TEST_USER_A.id,
        blueprint_id,
        bp,
        "guided-concept-path",
        form=None,
        planning_source=planning_source,
    )

    with patch(
        "generation.v3_studio.router.adjust_production_blueprint",
        new=AsyncMock(return_value=bp),
    ), patch(
        "generation.v3_studio.router.blueprint_to_preview_dto",
        return_value={
            "blueprint_id": blueprint_id,
            "resource_type": "lesson",
            "title": "Adjusted blueprint",
            "template_id": "guided-concept-path",
        },
    ):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/v3/blueprint/adjust",
                json={
                    "blueprint_id": blueprint_id,
                    "adjustment": "Make it shorter.",
                },
            )
            assert resp.status_code == 200

    stored = await v3_studio_store.get_blueprint(TEST_USER_A.id, blueprint_id)
    assert stored is not None
    assert stored.planning_source is not None
    assert stored.planning_source["kind"] == "supplement"
    assert stored.planning_source["parent_generation_id"] == parent_generation_id
    assert stored.planning_source["target_resource_type"] == "exit_ticket"


@pytest.mark.asyncio
async def test_blueprint_adjust_registers_and_closes_trace_for_telemetry() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    await v3_studio_store.put_blueprint(
        TEST_USER_A.id,
        blueprint_id,
        bp,
        "guided-concept-path",
        form=None,
        planning_source={"kind": "teacher_approved_blueprint"},
    )

    published: list[tuple[str, object]] = []

    def capture(trace_id: str, event: object) -> None:
        published.append((trace_id, event))

    with (
        patch("generation.v3_studio.router.event_bus.publish", side_effect=capture),
        patch(
            "generation.v3_studio.router.adjust_production_blueprint",
            new=AsyncMock(return_value=bp),
        ),
        patch(
            "generation.v3_studio.router.blueprint_to_preview_dto",
            return_value={
                "blueprint_id": blueprint_id,
                "resource_type": "lesson",
                "title": "Adjusted blueprint",
                "template_id": "guided-concept-path",
            },
        ),
    ):
        async with _client() as client:
            response = await client.post(
                "/api/v1/v3/blueprint/adjust",
                json={
                    "blueprint_id": blueprint_id,
                    "adjustment": "Make section one shorter.",
                },
            )

    assert response.status_code == 200
    assert len(published) == 2
    trace_id, registered = published[0]
    closed_trace_id, closed = published[1]
    assert trace_id == closed_trace_id
    assert isinstance(registered, TraceRegisteredEvent)
    assert registered.user_id == TEST_USER_A.id
    assert registered.source == "planning"
    assert isinstance(closed, TraceClosedEvent)
    assert closed.source == "planning"


@pytest.mark.asyncio
async def test_v3_generate_start_persists_supplement_planning_source() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    parent_generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    planning_source = {
        "kind": "supplement",
        "parent_generation_id": parent_generation_id,
        "parent_blueprint_id": "bp-parent-123",
        "target_resource_type": "exit_ticket",
    }
    await v3_studio_store.put_blueprint(
        TEST_USER_A.id,
        blueprint_id,
        bp,
        "guided-concept-path",
        form=None,
        planning_source=planning_source,
    )

    async def fake_pump(queue, **_kwargs):
        await queue.put(None)

    with patch("generation.v3_studio.router._pump_sse_to_queue", new=fake_pump):
        async with _client() as client:
            post = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                    "template_id": "guided-concept-path",
                },
            )
            assert post.status_code == 200

    async with async_session_factory() as session:
        result = await session.execute(
            select(GenerationModel).where(GenerationModel.id == generation_id)
        )
        model = result.scalar_one_or_none()
        assert model is not None
        artifact = parse_planning_artifact(model.planning_spec_json)
        assert artifact is not None
        assert artifact["source"]["kind"] == "supplement"
        assert artifact["source"]["parent_generation_id"] == parent_generation_id
        assert artifact["source"]["target_resource_type"] == "exit_ticket"


@pytest.mark.asyncio
async def test_supplement_adjust_then_start_persists_lineage_in_db() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    blueprint_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    parent_generation_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    planning_source = {
        "kind": "supplement",
        "parent_generation_id": parent_generation_id,
        "parent_blueprint_id": "bp-parent-123",
        "target_resource_type": "exit_ticket",
    }
    await v3_studio_store.put_blueprint(
        TEST_USER_A.id,
        blueprint_id,
        bp,
        "guided-concept-path",
        form=None,
        planning_source=planning_source,
    )

    with patch(
        "generation.v3_studio.router.adjust_production_blueprint",
        new=AsyncMock(return_value=bp),
    ):
        async with _client() as client:
            adjust_resp = await client.post(
                "/api/v1/v3/blueprint/adjust",
                json={
                    "blueprint_id": blueprint_id,
                    "adjustment": "Shorten the exit ticket.",
                },
            )
            assert adjust_resp.status_code == 200

    async def fake_pump(queue, **_kwargs):
        await queue.put(None)

    with patch("generation.v3_studio.router._pump_sse_to_queue", new=fake_pump):
        async with _client() as client:
            post = await client.post(
                "/api/v1/v3/generate/start",
                json={
                    "generation_id": generation_id,
                    "blueprint_id": blueprint_id,
                    "template_id": "guided-concept-path",
                },
            )
            assert post.status_code == 200

    async with async_session_factory() as session:
        result = await session.execute(
            select(GenerationModel).where(GenerationModel.id == generation_id)
        )
        model = result.scalar_one_or_none()
        assert model is not None
        artifact = parse_planning_artifact(model.planning_spec_json)
        assert artifact is not None
        assert artifact["source"]["kind"] == "supplement"
        assert artifact["source"]["parent_generation_id"] == parent_generation_id
        assert artifact["source"]["target_resource_type"] == "exit_ticket"


async def _seed_parent_generation_with_artifact(
    *,
    generation_id: str,
    resource_type: str = "lesson",
) -> tuple[str, object]:
    blueprint_id = str(uuid.uuid4())
    bp = _example_bp("amara_compound_area.json")
    bp.lesson.resource_type = resource_type
    artifact = build_planning_artifact(
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        template_id="guided-concept-path",
        blueprint=bp,
        form=None,
    )
    await _upsert_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        document_json={"sections": [{"id": "s1"}]},
        report_json={"booklet_status": "final_ready"},
        mode="v3",
        status="completed",
        subject=bp.metadata.subject,
        context=bp.metadata.title,
        section_count=len(bp.sections),
    )
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        model.planning_spec_json = json.dumps(artifact)
        await session.commit()
    return blueprint_id, bp


@pytest.mark.asyncio
async def test_supplement_options_are_parked() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    await _seed_parent_generation_with_artifact(generation_id=generation_id)

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/supplements/options")
    assert resp.status_code == 410
    assert "parked" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_supplement_blueprint_is_parked() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    generation_id = str(uuid.uuid4())
    await _seed_parent_generation_with_artifact(generation_id=generation_id)

    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{generation_id}/supplements/blueprint",
            json={"resource_type": "exit_ticket"},
        )
    assert resp.status_code == 410
    assert "parked" in resp.json()["detail"].lower()
