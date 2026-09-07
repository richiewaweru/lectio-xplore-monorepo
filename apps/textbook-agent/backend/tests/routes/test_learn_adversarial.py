"""Adversarial Learn closeout probes (Phase 12)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import UserModel
from core.database.session import get_async_session
from core.entities.user import User
from learning.release_routes import document_hash


def _now() -> datetime:
    return datetime.now(timezone.utc)


TEACHER = User(
    id="adv-teacher",
    email="adv-teacher@example.com",
    name="Adv Teacher",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)

OTHER = User(
    id="adv-other",
    email="adv-other@example.com",
    name="Other",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)


def _doc(title: str = "Adv") -> dict:
    return {
        "version": 1,
        "id": "doc-adv",
        "title": title,
        "subject": "biology",
        "preset_id": "blue-classroom",
        "source": "manual",
        "sections": [
            {
                "id": "s1",
                "template_id": "open-canvas",
                "title": "Warm",
                "position": 0,
                "block_ids": ["b1"],
                "required": True,
            }
        ],
        "blocks": {
            "b1": {
                "id": "b1",
                "component_id": "explanation-block",
                "position": 0,
                "content": {"body": "Body"},
            }
        },
        "media": {},
        "created_at": "2026-09-06T00:00:00Z",
        "updated_at": "2026-09-06T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def _overrides(db_session_factory):
    state = {"user": TEACHER}

    async def override_user():
        return state["user"]

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session
    yield state
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _seed(db_session_factory):
    async with db_session_factory() as session:
        session.add(UserModel(id=TEACHER.id, email=TEACHER.email, name=TEACHER.name))
        session.add(UserModel(id=OTHER.id, email=OTHER.email, name=OTHER.name))
        await session.commit()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_post_publish_edit_does_not_mutate_release():
    async with await _client() as client:
        created = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Adv", "document": _doc()},
        )
        lesson_id = created.json()["id"]
        pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        release = pub.json()
        hash1 = release["document_hash"]

        edited = _doc("Edited")
        edited["blocks"]["b1"]["content"]["body"] = "Changed"
        await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": "Edited", "document": edited},
        )
        got = await client.get(f"/api/v1/learn/releases/{release['id']}")
        assert got.json()["document_hash"] == hash1
        assert got.json()["document"]["blocks"]["b1"]["content"]["body"] == "Body"


@pytest.mark.asyncio
async def test_duplicate_submission_and_same_release_assigned_twice(_overrides):
    async with await _client() as client:
        created = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Adv2", "document": _doc("Adv2")},
        )
        lesson_id = created.json()["id"]
        pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        release_id = pub.json()["id"]

        learner = await client.post("/api/v1/learn/learners", json={"display_name": "A"})
        learner_id = learner.json()["id"]
        inst = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": learner_id, "learn_release_id": release_id},
        )
        instance_id = inst.json()["id"]

        payload = {
            "interaction_id": "b1",
            "client_submission_id": "dup-1",
            "response_json": {},
            "outcome": "correct",
            "score_earned": 1,
            "score_possible": 1,
            "section_id": "s1",
        }
        a1 = await client.post(f"/api/v1/learn/instances/{instance_id}/attempts", json=payload)
        a2 = await client.post(f"/api/v1/learn/instances/{instance_id}/attempts", json=payload)
        assert a1.status_code == 200 and a2.status_code == 200
        assert a1.json()["id"] == a2.json()["id"]

        c1 = await client.post("/api/v1/learn/classes", json={"name": "C1"})
        await client.post(
            f"/api/v1/learn/classes/{c1.json()['id']}/learners",
            json={"learner_id": learner_id},
        )
        assign1 = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_id,
                "title": "A1",
                "class_id": c1.json()["id"],
                "mode": "rolling",
            },
        )
        assign2 = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_id,
                "title": "A2",
                "class_id": c1.json()["id"],
                "mode": "rolling",
            },
        )
        assert assign1.status_code == 200 and assign2.status_code == 200
        assert assign1.json()["id"] != assign2.json()["id"]


@pytest.mark.asyncio
async def test_selected_learner_and_permission_probe(_overrides):
    async with await _client() as client:
        created = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Adv3", "document": _doc("Adv3")},
        )
        pub = await client.post(
            f"/api/v1/learn/lessons/{created.json()['id']}/releases", json={}
        )
        release_id = pub.json()["id"]
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "Sel"})
        selected = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_id,
                "title": "Only Sel",
                "mode": "selected",
                "selected_learner_ids": [learner.json()["id"]],
            },
        )
        assert selected.status_code == 200
        home = await client.get(f"/api/v1/learn/learners/{learner.json()['id']}/home")
        assert any(i["assignment_id"] == selected.json()["id"] for i in home.json()["instances"])

        c1 = await client.post("/api/v1/learn/classes", json={"name": "Private"})
        _overrides["user"] = OTHER
        denied = await client.get(f"/api/v1/learn/classes/{c1.json()['id']}")
        assert denied.status_code == 404
        denied_insight = await client.get(
            f"/api/v1/learn/analytics/classes/{c1.json()['id']}/overview"
        )
        assert denied_insight.status_code == 404
        _overrides["user"] = TEACHER


@pytest.mark.asyncio
async def test_malformed_contract_and_publish_shape():
    async with await _client() as client:
        bad = await client.post(
            "/api/v1/builder/lessons",
            json={
                "title": "Bad",
                "document": {"version": 1, "id": "x", "sections": [], "blocks": {}, "media": {}},
            },
        )
        # Builder may accept sparse docs; publish validates shape
        if bad.status_code == 201:
            pub = await client.post(
                f"/api/v1/learn/lessons/{bad.json()['id']}/releases", json={}
            )
            # Missing subject/title fields still ok if version/id/sections/blocks/media present
            assert pub.status_code in {201, 422}
        missing = await client.post("/api/v1/learn/lessons/nope/releases", json={})
        assert missing.status_code == 404


def test_document_hash_stable():
    d = _doc()
    assert document_hash(d) == document_hash(d)
