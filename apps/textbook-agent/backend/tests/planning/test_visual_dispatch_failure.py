"""Durable visual-dispatch failures + visuals-only retry."""

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
from generation.page_objects.document_assembly import persist_document_json, reload_document
from planning.whole_lesson.native_status import project_native_status
from planning.whole_lesson.repository import PageDocumentRepository, empty_page_document_state
from planning.whole_lesson.states import execution_key
from planning.whole_lesson.visual_dispatch import collect_pending_figure_dispatches


TEST_USER = User(
    id="visual-fail-owner",
    email="visual-fail@example.invalid",
    name="Visual Fail",
    created_at="2026-07-31T00:00:00+00:00",
    updated_at="2026-07-31T00:00:00+00:00",
)


async def _override_user() -> User:
    return TEST_USER


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _document() -> dict[str, Any]:
    return {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": "doc-visual-fail",
        "title": "Plants",
        "language": "en",
        "metadata": {"catalogue_version": "1.1.0", "resource_type": "lesson"},
        "sections": [
            {
                "id": "explain",
                "title": "Explain",
                "blocks": [
                    {
                        "id": "prose-1",
                        "object": "prose",
                        "intent": "explain",
                        "position": 0,
                        "content": {"paragraphs": ["Ready text stays."]},
                        "layout": {"placement": "main"},
                    },
                    {
                        "id": "fig-1",
                        "object": "figure",
                        "intent": "explain",
                        "position": 1,
                        "content": {
                            "alt_text": "Leaf",
                            "caption": "Leaf",
                            "asset": {
                                "status": "pending",
                                "request_id": "req-fig-1",
                                "kind": "image",
                            },
                        },
                        "layout": {"placement": "main"},
                    },
                ],
            }
        ],
    }


async def _seed_awaiting_visuals() -> str:
    gid = str(uuid.uuid4())
    state = empty_page_document_state()
    state["form_plan"] = {
        "sections": [
            {
                "slot_id": "explain",
                "forms": [
                    {"block_id": "prose-1", "object": "prose"},
                    {"block_id": "fig-1", "object": "figure"},
                ],
            }
        ]
    }
    state["block_execution"] = {
        execution_key("explain", "prose-1"): {
            "status": "ready",
            "block_id": "prose-1",
            "object": "prose",
            "content": {"paragraphs": ["Ready text stays."]},
        },
        execution_key("explain", "fig-1"): {
            "status": "visual_pending",
            "block_id": "fig-1",
            "object": "figure",
            "request_id": "req-fig-1",
            "content": {
                "alt_text": "Leaf",
                "asset": {"status": "pending", "request_id": "req-fig-1"},
            },
        },
    }
    doc = _document()
    async with async_session_factory() as session:
        if await session.get(UserModel, TEST_USER.id) is None:
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
                status="awaiting_visuals",
                document_json=persist_document_json({}, doc),
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "awaiting_visuals",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()
    return gid


def test_collect_includes_failed_recoverable_outcomes() -> None:
    pending = collect_pending_figure_dispatches(
        generation_id="gen-1",
        block_execution={
            "explain:fig-1:everyone": {
                "object": "figure",
                "status": "failed_recoverable",
                "block_id": "fig-1",
                "request_id": "req-1",
                "content": {
                    "alt_text": "Leaf",
                    "asset": {"status": "failed", "request_id": "req-1"},
                },
            }
        },
    )
    assert len(pending) == 1
    assert pending[0][1] == "req-1"


@pytest.mark.asyncio
async def test_visual_dispatch_exception_durable_and_retryable() -> None:
    gid = await _seed_awaiting_visuals()
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        await repo.persist_visual_dispatch_failure(
            exc=RuntimeError("dispatcher exploded"),
            failed_request_ids=["req-fig-1"],
        )
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_visuals"
        state = await repo.load_page_generation_state()
        last_error = state["execution"]["last_error"]
        assert last_error["retryable"] is True
        assert last_error["stage"] == "awaiting_visuals"
        fig = state["block_execution"][execution_key("explain", "fig-1")]
        assert fig["status"] == "failed_recoverable"
        assert fig["content"]["asset"]["status"] == "failed"
        doc = reload_document(generation.document_json or {})
        prose = doc["sections"][0]["blocks"][0]
        assert prose["content"]["paragraphs"] == ["Ready text stays."]
        native = project_native_status(
            gid,
            {"page_document_v2": state, "native_whole_lesson": True, "stage": "awaiting_visuals"},
            generation.document_json,
            generation_status="awaiting_visuals",
        )
        assert native is not None
        assert native["next_action"] == "retry_visuals"
        assert native["error_detail"]["retryable"] is True


@pytest.mark.asyncio
async def test_visuals_retry_only_redispatches_and_skips_ready_blocks() -> None:
    gid = await _seed_awaiting_visuals()
    app.dependency_overrides[get_current_user] = _override_user
    calls: list[str] = []

    async def fake_execute(order, emit, **kwargs):
        calls.append(order.work_order_id)
        return [
            type(
                "B",
                (),
                {
                    "status": "ready",
                    "fallback_image_url": "https://example.test/leaf.png",
                    "html_content": None,
                },
            )()
        ]

    try:
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            await repo.persist_visual_dispatch_failure(
                message="prior failure",
                failed_request_ids=["req-fig-1"],
            )
        with patch(
            "planning.whole_lesson.visual_dispatch.execute_visual",
            new=fake_execute,
        ):
            async with _client() as client:
                response = await client.post(
                    f"/api/v1/v3/generations/{gid}/visuals/retry"
                )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "ready"
        assert calls == ["native-visual:req-fig-1"]
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            assert generation.status == "ready"
            state = await PageDocumentRepository(session, gid).load_page_generation_state()
            # Ready prose block was never rewritten as a failed outcome.
            prose = state["block_execution"][execution_key("explain", "prose-1")]
            assert prose["status"] == "ready"
            assert prose["content"]["paragraphs"] == ["Ready text stays."]
            fig = state["block_execution"][execution_key("explain", "fig-1")]
            assert fig["status"] == "ready"
            assert (state.get("execution") or {}).get("last_error") is None
    finally:
        app.dependency_overrides.pop(get_current_user, None)
