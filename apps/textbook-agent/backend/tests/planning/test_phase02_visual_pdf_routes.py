"""Patch 02.1A: real visual callback + PDF gate route tests."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from core.entities.user import User
from generation.page_objects.document_assembly import persist_document_json
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.repository import PageDocumentRepository, empty_page_document_state


TEST_USER = User(
    id="visual-route-owner",
    email="visual-route@example.invalid",
    name="Visual Route",
    created_at="2026-07-31T00:00:00+00:00",
    updated_at="2026-07-31T00:00:00+00:00",
)

ANSWER_PHRASE = "TEACHER_ONLY_ANSWER_PHRASE_42"


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-visual-route",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light", "plant"]),
        anchor=AnchorRecord(id="anchor-1", description="Two plants."),
        slots=[SlotRecord(slot_id="explain", typical_intents=["explain"])],
        limits=LessonLimits(),
    )


def _document(*, figures: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": "doc-visual-route",
        "title": "Plants and light",
        "language": "en",
        "metadata": {"catalogue_version": "1.1.0", "resource_type": "lesson"},
        "sections": [
            {
                "id": "explain",
                "title": "Explain",
                "blocks": list(figures),
            }
        ],
    }


def _figure(
    *,
    block_id: str,
    request_id: str,
    status: str = "pending",
    position: int = 0,
    src: str | None = None,
) -> dict[str, Any]:
    asset: dict[str, Any] = {
        "status": status,
        "request_id": request_id,
        "kind": "image",
    }
    if src is not None:
        asset["src"] = src
    return {
        "id": block_id,
        "object": "figure",
        "intent": "show-structure",
        "position": position,
        "content": {
            "alt_text": "Two plants",
            "caption": "Lit vs covered",
            "asset": asset,
        },
        "layout": {"placement": "main"},
    }


async def _seed(
    *,
    status: str = "awaiting_visuals",
    figures: list[dict[str, Any]] | None = None,
    include_block_execution: bool = True,
) -> str:
    gid = str(uuid.uuid4())
    figs = figures or [
        _figure(block_id="fig-1", request_id="req-fig-1", position=0),
    ]
    doc = _document(figures=figs)
    state = empty_page_document_state()
    state["lesson_packet"] = _packet().model_dump(mode="json")
    state["teaching_plan"] = {"arc": "test", "sections": []}
    state["form_validation"] = {"ok": True}
    state["document_revision"] = 1
    if include_block_execution:
        block_execution: dict[str, Any] = {}
        for fig in figs:
            rid = fig["content"]["asset"]["request_id"]
            asset_status = str(fig["content"]["asset"]["status"] or "")
            block_execution[f"explain:{fig['id']}:everyone"] = {
                "status": (
                    "ready"
                    if asset_status == "ready"
                    else "failed_recoverable"
                    if asset_status == "failed"
                    else "visual_pending"
                ),
                "block_id": fig["id"],
                "request_id": rid,
                "object": "figure",
                "intent": "show-structure",
                "content": fig["content"],
            }
        state["block_execution"] = block_execution
    async with async_session_factory() as session:
        existing = await session.get(UserModel, TEST_USER.id)
        if existing is None:
            session.add(
                UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name)
            )
        session.add(
            GenerationModel(
                id=gid,
                user_id=TEST_USER.id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status=status,
                document_json=persist_document_json(None, doc),
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": status,
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()
    return gid


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.clear()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_visual_callback_404_unknown_request() -> None:
    gid = await _seed()
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "missing-req",
                "asset": {"status": "ready", "kind": "image", "src": "https://x/a.png"},
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_visual_callback_409_block_id_mismatch() -> None:
    gid = await _seed()
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "block_id": "wrong-block",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/a.png",
                },
            },
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_visual_callback_idempotent_and_partial_then_final() -> None:
    gid = await _seed(
        figures=[
            _figure(block_id="fig-1", request_id="req-fig-1", position=0),
            _figure(block_id="fig-2", request_id="req-fig-2", position=1),
        ]
    )
    ready_asset = {
        "status": "ready",
        "kind": "image",
        "src": "https://example.test/a.png",
        "request_id": "req-fig-1",
    }
    async with _client() as client:
        first = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={"request_id": "req-fig-1", "asset": ready_asset},
        )
        assert first.status_code == 200
        body = first.json()
        assert body["idempotent"] is False
        assert body["status"] == "awaiting_visuals"
        rev1 = body["document_revision"]

        again = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={"request_id": "req-fig-1", "asset": ready_asset},
        )
        assert again.status_code == 200
        assert again.json()["idempotent"] is True
        assert again.json()["document_revision"] == rev1
        assert again.json()["status"] == "awaiting_visuals"

        final = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-2",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/b.png",
                    "request_id": "req-fig-2",
                },
            },
        )
        assert final.status_code == 200
        assert final.json()["status"] == "ready"
        assert final.json()["document_revision"] > rev1

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "ready"
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        outcome = state["block_execution"]["explain:fig-1:everyone"]
        assert outcome["status"] == "ready"
        assert outcome["content"]["asset"]["status"] == "ready"
        events = state.get("events") or []
        assert any(e.get("type") == "visual_callback" for e in events)
        doc = (generation.document_json or {}).get("lectio_document") or {}
        assets = [
            ((b.get("content") or {}).get("asset") or {})
            for s in doc.get("sections") or []
            for b in s.get("blocks") or []
            if b.get("object") == "figure"
        ]
        assert all(a.get("status") == "ready" for a in assets)


@pytest.mark.asyncio
async def test_pdf_export_figures_not_ready_then_passes_gate(tmp_path) -> None:
    gid = await _seed(status="awaiting_visuals")
    async with _client() as client:
        blocked = await client.post(
            f"/api/v1/v3/generations/{gid}/export/pdf",
            json={
                "school_name": "School",
                "teacher_name": "Teacher",
                "include_toc": False,
                "include_answers": True,
            },
        )
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] == "FIGURES_NOT_READY"

    async with _client() as client:
        done = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/a.png",
                },
            },
        )
        assert done.status_code == 200
        assert done.json()["status"] == "ready"

    pdf_path = tmp_path / "ready.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

    with patch(
        "generation.v3_studio.router.export_v3_studio_pdf",
        new=AsyncMock(
            return_value=type(
                "R",
                (),
                {
                    "pdf_path": pdf_path,
                    "filename": "ready.pdf",
                    "page_count": 1,
                    "file_size_bytes": pdf_path.stat().st_size,
                    "generation_time_ms": 1,
                    "cleanup_paths": [],
                    "print_page_debug": {},
                },
            )()
        ),
    ):
        async with _client() as client:
            ok = await client.post(
                f"/api/v1/v3/generations/{gid}/export/pdf",
                json={
                    "school_name": "School",
                    "teacher_name": "Teacher",
                    "include_toc": False,
                    "include_answers": True,
                },
            )
    assert ok.status_code == 200
    assert ok.headers.get("content-type", "").startswith("application/pdf")


@pytest.mark.asyncio
async def test_native_malformed_pdf_returns_explicit_contract_error() -> None:
    gid = await _seed(status="ready")
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        generation.document_json = {
            "document_version": 2,
            "lectio_document": {"title": "Missing sections"},
        }
        await session.commit()

    async with _client() as client:
        response = await client.post(
            f"/api/v1/v3/generations/{gid}/export/pdf",
            json={"school_name": "School", "teacher_name": "Teacher", "edition": "teacher"},
        )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "NATIVE_DOCUMENT_CONTRACT"


async def _snapshot(gid: str) -> dict[str, Any]:
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        return {
            "status": generation.status,
            "revision": int(state.get("document_revision") or 0),
            "document_json": generation.document_json,
            "block_execution": dict(state.get("block_execution") or {}),
        }


@pytest.mark.asyncio
async def test_visual_callback_rejects_missing_execution_outcome() -> None:
    gid = await _seed(include_block_execution=False)
    before = await _snapshot(gid)
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/a.png",
                },
            },
        )
    assert resp.status_code == 409
    after = await _snapshot(gid)
    assert after["status"] == "awaiting_visuals"
    assert after["revision"] == before["revision"]
    assert after["document_json"] == before["document_json"]
    assert after["block_execution"] == {}
    assert "ready" not in {
        str((o or {}).get("status") or "") for o in after["block_execution"].values()
    }


@pytest.mark.asyncio
async def test_visual_callback_pending_remains_visual_pending() -> None:
    gid = await _seed()
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "asset": {"status": "pending", "kind": "image", "request_id": "req-fig-1"},
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "awaiting_visuals"
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_visuals"
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        outcome = state["block_execution"]["explain:fig-1:everyone"]
        assert outcome["status"] == "visual_pending"
        asset = ((generation.document_json or {}).get("lectio_document") or {})[
            "sections"
        ][0]["blocks"][0]["content"]["asset"]
        assert asset["status"] == "pending"


@pytest.mark.asyncio
async def test_visual_callback_generating_remains_visual_pending() -> None:
    gid = await _seed()
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "asset": {
                    "status": "generating",
                    "kind": "image",
                    "request_id": "req-fig-1",
                },
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "awaiting_visuals"
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_visuals"
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        assert state["block_execution"]["explain:fig-1:everyone"]["status"] == (
            "visual_pending"
        )


@pytest.mark.asyncio
async def test_visual_callback_failed_is_recoverable_and_not_ready() -> None:
    gid = await _seed()
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "asset": {
                    "status": "failed",
                    "kind": "image",
                    "request_id": "req-fig-1",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "awaiting_visuals"
        blocked = await client.post(
            f"/api/v1/v3/generations/{gid}/export/pdf",
            json={
                "school_name": "School",
                "teacher_name": "Teacher",
                "include_toc": False,
                "include_answers": True,
            },
        )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "FIGURES_NOT_READY"
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_visuals"
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        assert state["block_execution"]["explain:fig-1:everyone"]["status"] == (
            "failed_recoverable"
        )


@pytest.mark.asyncio
async def test_visual_callback_unknown_asset_status_rejected() -> None:
    gid = await _seed()
    before = await _snapshot(gid)
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "asset": {"status": "mystery", "kind": "image"},
            },
        )
    assert resp.status_code == 409
    after = await _snapshot(gid)
    assert after["status"] == before["status"]
    assert after["revision"] == before["revision"]
    assert after["document_json"] == before["document_json"]
    assert after["block_execution"] == before["block_execution"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage",
    ["planning_forms", "writing_blocks", "assembling", "failed_terminal"],
)
async def test_visual_callback_rejected_in_unrelated_stage(stage: str) -> None:
    gid = await _seed(status=stage)
    before = await _snapshot(gid)
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/a.png",
                },
            },
        )
    assert resp.status_code == 409
    after = await _snapshot(gid)
    assert after["status"] == stage
    assert after["revision"] == before["revision"]
    assert after["document_json"] == before["document_json"]


@pytest.mark.asyncio
async def test_ready_document_identical_callback_does_not_increment_revision() -> None:
    ready_asset = {
        "status": "ready",
        "kind": "image",
        "src": "https://example.test/a.png",
        "request_id": "req-fig-1",
    }
    gid = await _seed(
        status="ready",
        figures=[
            _figure(
                block_id="fig-1",
                request_id="req-fig-1",
                status="ready",
                src="https://example.test/a.png",
            )
        ],
    )
    before = await _snapshot(gid)
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={"request_id": "req-fig-1", "asset": ready_asset},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["idempotent"] is True
    assert body["status"] == "ready"
    assert body["document_revision"] == before["revision"]
    after = await _snapshot(gid)
    assert after["revision"] == before["revision"]
    assert after["status"] == "ready"


@pytest.mark.asyncio
async def test_ready_document_material_asset_replacement_rejected() -> None:
    gid = await _seed(
        status="ready",
        figures=[
            _figure(
                block_id="fig-1",
                request_id="req-fig-1",
                status="ready",
                src="https://example.test/a.png",
            )
        ],
    )
    before = await _snapshot(gid)
    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/visuals/callback",
            json={
                "request_id": "req-fig-1",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/b.png",
                },
            },
        )
    assert resp.status_code == 409
    after = await _snapshot(gid)
    assert after["revision"] == before["revision"]
    assert after["status"] == "ready"
    doc = (after["document_json"] or {}).get("lectio_document") or {}
    asset = doc["sections"][0]["blocks"][0]["content"]["asset"]
    assert asset["src"] == "https://example.test/a.png"
