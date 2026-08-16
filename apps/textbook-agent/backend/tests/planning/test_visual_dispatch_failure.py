"""Durable visual-dispatch failures + visuals-only retry."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from core.entities.user import User
from generation.page_objects.document_assembly import (
    canonical_document_sha256,
    persist_document_json,
    reload_document,
)
from planning.whole_lesson.native_status import project_native_status
from planning.whole_lesson.repository import PageDocumentRepository, empty_page_document_state
from planning.whole_lesson.states import execution_key
from planning.whole_lesson.visual_dispatch import (
    collect_pending_figure_dispatches,
    dispatch_and_patch_from_repo,
)


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
async def test_visual_completion_reloads_current_revision_before_ready() -> None:
    gid = await _seed_awaiting_visuals()
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        state = await repo.load_page_generation_state()
        before_revision = int(state.get("document_revision") or 0)
        result = await repo.apply_visual_completion(
            request_id="req-fig-1",
            supplied_block_id="fig-1",
            asset={
                "status": "ready",
                "kind": "image",
                "src": "https://example.test/leaf.png",
            },
        )
        assert result.status == "ready"
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "ready"
        state = await repo.load_page_generation_state()
        execution = state["execution"]
        document = reload_document(generation.document_json or {})
        digest = canonical_document_sha256(document)
        assert int(state["document_revision"]) == before_revision + 1
        assert execution["document_sha256"] == digest
        assert execution["reloaded_sha256"] == digest
        assert execution["reload_verified"] is True
        assert any(event.get("type") == "visual_document_ready" for event in state["events"])


@pytest.mark.asyncio
async def test_flagged_quality_is_durable_retryable_without_ready_proof() -> None:
    gid = await _seed_awaiting_visuals()

    async def fake_execute(order, emit, **kwargs):
        _ = order, emit, kwargs
        return [
            type(
                "B",
                (),
                {
                    "status": "flagged_quality",
                    "fallback_image_url": None,
                    "image_url": "https://example.test/flagged-leaf.png",
                    "html_content": None,
                    "qc_reasons": ["label is faint"],
                    "qc_correction_hint": "increase label contrast",
                },
            )()
        ]

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        await repo.persist_visual_dispatch_failure(
            message="prior provider failure",
            failed_request_ids=["req-fig-1"],
        )
        result = await dispatch_and_patch_from_repo(
            session=session,
            generation_id=gid,
            execute_visual_fn=fake_execute,
        )

        assert result["failed"] == 1
        assert result["failures"]
        assert result["results"][0]["asset_status"] == "failed"
        state = await repo.load_page_generation_state()
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_visuals"
        assert generation.error is not None
        assert (state.get("execution") or {}).get("last_error", {}).get("retryable") is True

        figure = state["block_execution"][execution_key("explain", "fig-1")]
        assert figure["status"] == "failed_recoverable"
        assert figure["content"]["asset"]["status"] == "failed"
        assert figure["visual_qc"] == {
            "status": "flagged_quality",
            "reasons": ["label is faint"],
            "correction_hint": "increase label contrast",
        }
        assert "visual_qc" not in figure["content"]["asset"]
        assert collect_pending_figure_dispatches(
            generation_id=gid,
            block_execution=state["block_execution"],
        )

        native = project_native_status(
            gid,
            {
                "page_document_v2": state,
                "native_whole_lesson": True,
                "stage": "awaiting_visuals",
            },
            generation.document_json,
            generation_status=generation.status,
        )
        assert native is not None
        assert native["next_action"] == "retry_visuals"
        assert native["error_detail"]["retryable"] is True


@pytest.mark.asyncio
async def test_visual_failure_invalidates_prior_reload_proof() -> None:
    gid = await _seed_awaiting_visuals()
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)

        def _proof(_generation, state):
            execution = state["execution"]
            execution["document_sha256"] = "old"
            execution["reloaded_sha256"] = "old"
            execution["reload_verified"] = True

        await repo.mutate_state(mutation=_proof)
        await repo.persist_visual_dispatch_failure(
            message="provider unavailable",
            failed_request_ids=["req-fig-1"],
        )
        state = await repo.load_page_generation_state()
        execution = state["execution"]
        assert execution["document_sha256"] is None
        assert execution["reloaded_sha256"] is None
        assert execution["reload_verified"] is False


@pytest.mark.asyncio
async def test_visual_retry_reverifies_hash_for_new_revision() -> None:
    gid = await _seed_awaiting_visuals()
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        await repo.persist_visual_dispatch_failure(
            message="first provider failure",
            failed_request_ids=["req-fig-1"],
        )
        failed_state = await repo.load_page_generation_state()
        failed_revision = int(failed_state["document_revision"])
        result = await repo.apply_visual_completion(
            request_id="req-fig-1",
            supplied_block_id="fig-1",
            asset={
                "status": "ready",
                "kind": "image",
                "src": "https://example.test/retry.png",
            },
        )
        assert result.status == "ready"
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        state = await repo.load_page_generation_state()
        document = reload_document(generation.document_json or {})
        digest = canonical_document_sha256(document)
        assert int(state["document_revision"]) == failed_revision + 1
        assert state["execution"]["document_sha256"] == digest
        assert state["execution"]["reloaded_sha256"] == digest
        assert state["execution"]["reload_verified"] is True


@pytest.mark.asyncio
async def test_ready_flagged_visual_reopens_only_visual_checkpoint() -> None:
    gid = await _seed_awaiting_visuals()
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)

        def _mark_ready_flagged(_generation, state):
            state["block_execution"][execution_key("explain", "fig-1")]["status"] = "ready"
            state["block_execution"][execution_key("explain", "fig-1")]["visual_qc"] = {
                "status": "flagged_quality",
                "reasons": ["garbled label"],
            }
            state["block_execution"][execution_key("explain", "fig-1")]["content"]["asset"] = {
                "status": "ready",
                "request_id": "req-fig-1",
                "src": "https://example.test/flagged.png",
            }

        await repo.mutate_state(mutation=_mark_ready_flagged)
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        generation.status = "ready"
        await session.commit()
        reopened = await repo.reopen_flagged_visuals()
        assert reopened["status"] == "awaiting_visuals"
        state = await repo.load_page_generation_state()
        assert state["block_execution"][execution_key("explain", "prose-1")]["status"] == "ready"
        assert state["block_execution"][execution_key("explain", "fig-1")]["status"] == "failed_recoverable"
        assert state["execution"]["reload_verified"] is False


@pytest.mark.asyncio
async def test_successful_qc_replacement_archives_history_and_clears_active_warning() -> None:
    gid = await _seed_awaiting_visuals()
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        flagged = await repo.apply_visual_completion(
            request_id="req-fig-1",
            supplied_block_id="fig-1",
            asset={"status": "failed", "kind": "image"},
            visual_qc={
                "status": "flagged_quality",
                "reasons": ["garbled labels"],
                "correction_hint": "Use large labels.",
            },
        )
        assert flagged.status == "awaiting_visuals"
        ready = await repo.apply_visual_completion(
            request_id="req-fig-1",
            supplied_block_id="fig-1",
            asset={
                "status": "ready",
                "kind": "image",
                "src": "https://example.test/repaired.png",
            },
        )
        assert ready.status == "ready"
        state = await repo.load_page_generation_state()
        figure = state["block_execution"][execution_key("explain", "fig-1")]
        assert "visual_qc" not in figure
        assert figure["visual_qc_history"][-1]["correction_hint"] == "Use large labels."
        assert (state["execution"] or {}).get("last_error") is None


@pytest.mark.asyncio
async def test_idempotent_ready_callback_can_finalize_stale_visual_checkpoint() -> None:
    gid = await _seed_awaiting_visuals()
    asset = {
        "status": "ready",
        "kind": "image",
        "src": "https://example.test/idempotent.png",
    }
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        first = await repo.apply_visual_completion(
            request_id="req-fig-1", supplied_block_id="fig-1", asset=asset
        )
        assert first.status == "ready"

        # Simulate a restart after the asset patch but before the final
        # transition was durably observed by the caller.
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        generation.status = "awaiting_visuals"
        await session.commit()

        second = await repo.apply_visual_completion(
            request_id="req-fig-1", supplied_block_id="fig-1", asset=asset
        )
        assert second.status == "ready"


@pytest.mark.asyncio
async def test_visual_completion_recovers_missing_document_request_id_after_restart() -> None:
    gid = await _seed_awaiting_visuals()
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        document = reload_document(generation.document_json or {})
        document["sections"][0]["blocks"][1]["content"]["asset"]["src"] = None
        document["sections"][0]["blocks"][1]["content"]["asset"].pop("request_id", None)
        generation.document_json = persist_document_json(generation.document_json, document)
        await session.commit()
        repo = PageDocumentRepository(session, gid)
        result = await repo.apply_visual_completion(
            request_id="req-fig-1",
            supplied_block_id="fig-1",
            asset={"status": "ready", "kind": "image", "src": "https://example.test/restarted.png"},
        )
        assert result.status == "ready"
        persisted = reload_document(generation.document_json or {})
        asset = persisted["sections"][0]["blocks"][1]["content"]["asset"]
        assert asset["request_id"] == "req-fig-1"


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


async def _seed_flagged_topology() -> str:
    gid = await _seed_awaiting_visuals()
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)

        def _flag(_generation, state):
            figure = state["block_execution"][execution_key("explain", "fig-1")]
            figure["status"] = "failed_recoverable"
            figure["visual_qc"] = {"status": "flagged_quality", "reasons": ["faint label"]}
            figure["content"]["asset"] = {
                "status": "failed",
                "request_id": "req-fig-1",
                "internal_asset_key": "internal/leaf.png",
                "topology_recovery": True,
            }
            execution = state["execution"]
            execution["document_sha256"] = "stale"
            execution["reloaded_sha256"] = "stale"
            execution["reload_verified"] = True

        await repo.mutate_state(mutation=_flag)
    return gid


@pytest.mark.asyncio
async def test_flagged_topology_recovery_keeps_hashes_invalid_and_upstream_unchanged() -> None:
    from planning.whole_lesson.visual_topology_recovery import TopologyRecoveryError

    gid = await _seed_flagged_topology()

    async def provider(*_args, **_kwargs):
        raise AssertionError("image provider must not run for topology recovery")

    async def recovery(**_kwargs):
        raise TopologyRecoveryError("TOPOLOGY_QC_FLAGGED", "flagged raster")

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        result = await dispatch_and_patch_from_repo(
            session=session,
            generation_id=gid,
            execute_visual_fn=provider,
            topology_recovery_fn=recovery,
        )
        assert result["failed"] == 1
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_visuals"
        state = await repo.load_page_generation_state()
        execution = state["execution"]
        assert execution["document_sha256"] is None
        assert execution["reloaded_sha256"] is None
        assert execution["reload_verified"] is False
        prose = state["block_execution"][execution_key("explain", "prose-1")]
        assert prose["status"] == "ready"
        assert prose["content"]["paragraphs"] == ["Ready text stays."]
        figure = state["block_execution"][execution_key("explain", "fig-1")]
        assert figure["status"] == "failed_recoverable"


@pytest.mark.asyncio
async def test_accepted_topology_recovery_increments_revision_and_equal_hashes() -> None:
    gid = await _seed_flagged_topology()

    async def provider(*_args, **_kwargs):
        raise AssertionError("image provider must not run for topology recovery")

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        before = await repo.load_page_generation_state()
        before_revision = int(before["document_revision"])

        async def recovery(**_kwargs):
            completion = await repo.apply_visual_completion(
                request_id="req-fig-1",
                supplied_block_id="fig-1",
                asset={
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/topology.png",
                },
                visual_qc={"status": "accepted", "reasons": []},
            )
            return {
                "status": completion.status,
                "document_revision": completion.document_revision,
            }

        result = await dispatch_and_patch_from_repo(
            session=session,
            generation_id=gid,
            execute_visual_fn=provider,
            topology_recovery_fn=recovery,
        )
        assert result["topology_recovery"][0]["status"] == "ready"
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "ready"
        state = await repo.load_page_generation_state()
        document = reload_document(generation.document_json or {})
        digest = canonical_document_sha256(document)
        assert int(state["document_revision"]) == before_revision + 1
        assert state["execution"]["document_sha256"] == digest
        assert state["execution"]["reloaded_sha256"] == digest
        assert state["execution"]["reload_verified"] is True
