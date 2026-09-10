"""R04-G02 — publish v1, Builder edit, publish v2; v1 immutable (REGRESSION_SCENARIOS §8)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from learn.publishing.release_routes import document_hash
from tests.remaining_fixes.r04_fixtures import (
    build_envelope_closed_production_document,
    install_api_overrides,
    publish_lesson,
    r04_client,
    seed_r04_user,
)


@pytest.fixture
def _api(db_session_factory):
    install_api_overrides(db_session_factory)
    yield
    from app import app

    app.dependency_overrides.clear()


@pytest.fixture
async def _seed(db_session_factory):
    await seed_r04_user(db_session_factory)


@pytest.mark.asyncio
async def test_r04_g02_publish_v1_builder_edit_v2_immutable(db_session_factory, _api, _seed) -> None:
    """Envelope-authored document; real publish + Builder PUT + second publish; fresh DB reads."""
    from core.database.models import LearnReleaseModel

    document = build_envelope_closed_production_document(title="R04 publish gate")
    original_body = None
    for block in document["blocks"].values():
        content = block.get("content") if isinstance(block, dict) else None
        if isinstance(content, dict) and content.get("body"):
            original_body = str(content["body"])
            break
    ix_prompt_before = None
    for block in document["blocks"].values():
        contract = block.get("learn_interaction") if isinstance(block, dict) else None
        if isinstance(contract, dict):
            ix_prompt_before = str(contract.get("prompt") or "")
            break

    async with await r04_client() as client:
        lesson_id, release_v1_id = await publish_lesson(client, document, title="R04-G02")
        v1_get = await client.get(f"/api/v1/learn/releases/{release_v1_id}")
        assert v1_get.status_code == 200, v1_get.text
        v1_body = v1_get.json()
        hash_v1 = v1_body["document_hash"]
        assert hash_v1 == document_hash(v1_body["document"])

        draft = dict(v1_body["document"])
        draft["title"] = "R04 publish gate (edited)"
        for block in draft["blocks"].values():
            contract = block.get("learn_interaction")
            if isinstance(contract, dict):
                contract["prompt"] = "Edited student prompt after Builder save."
            content = block.get("content")
            if isinstance(content, dict) and "body" in content:
                content["body"] = "Edited explanation body via Builder."
        upd = await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": draft["title"], "document": draft},
        )
        assert upd.status_code == 200, upd.text

        v1_after_edit = await client.get(f"/api/v1/learn/releases/{release_v1_id}")
        assert v1_after_edit.status_code == 200
        assert v1_after_edit.json()["document_hash"] == hash_v1
        if ix_prompt_before:
            assert v1_after_edit.json()["document"]["blocks"]
            # Published v1 snapshot keeps pre-edit interaction prompt.
            published_prompts = [
                b.get("learn_interaction", {}).get("prompt")
                for b in v1_after_edit.json()["document"]["blocks"].values()
                if isinstance(b.get("learn_interaction"), dict)
            ]
            if published_prompts:
                assert "Edited student prompt" not in str(published_prompts)

        pub2 = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub2.status_code == 201, pub2.text
        v2 = pub2.json()
        assert v2["release_number"] == 2
        assert v2["document_hash"] != hash_v1
        assert v2["document"]["title"] == "R04 publish gate (edited)"
        edited_ix = [
            b.get("learn_interaction", {}).get("prompt")
            for b in v2["document"]["blocks"].values()
            if isinstance(b.get("learn_interaction"), dict)
        ]
        if edited_ix:
            assert any("Edited student prompt" in str(p) for p in edited_ix)

    async with db_session_factory() as session:
        rows = (
            await session.execute(
                select(LearnReleaseModel).where(LearnReleaseModel.editable_lesson_id == lesson_id)
            )
        ).scalars().all()
        by_number = {r.release_number: r for r in rows}
        assert by_number[1].document_hash == hash_v1
        assert by_number[2].document_hash == v2["document_hash"]
        assert by_number[1].document_hash != by_number[2].document_hash


@pytest.mark.asyncio
async def test_r04_g02_builder_malformed_edit_rejected(db_session_factory, _api, _seed) -> None:
    """Builder PUT rejects malformed interaction config (policy-cleanup G21)."""
    document = build_envelope_closed_production_document()
    async with await r04_client() as client:
        created = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "R04 malformed", "document": document},
        )
        assert created.status_code == 201, created.text
        lesson_id = created.json()["id"]
        bad = dict(document)
        for block in bad["blocks"].values():
            contract = block.get("learn_interaction")
            if isinstance(contract, dict) and contract.get("kind") == "sequence":
                contract["config"] = {"order": []}
                break
        upd = await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": "R04 malformed", "document": bad},
        )
        assert upd.status_code == 422, upd.text
        # Draft remains valid; publish of unchanged draft still succeeds.
        pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub.status_code == 201, pub.text
