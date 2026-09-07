"""Phase 05: immutable LearnRelease publish flow."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from infra.auth.middleware import get_current_user
from core.database.models import LearnReleaseModel, UserModel
from infra.database.session import get_async_session
from core.entities.user import User
from learn.release_routes import document_hash


def _now() -> datetime:
    return datetime.now(timezone.utc)


USER = User(
    id="release-user-a",
    email="release-a@example.com",
    name="Release A",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)


def _minimal_lesson(document_id: str = "doc-1") -> dict:
    block_id = "block-1"
    return {
        "version": 1,
        "id": document_id,
        "title": "Photosynthesis",
        "subject": "biology",
        "preset_id": "blue-classroom",
        "source": "manual",
        "sections": [
            {
                "id": "section-1",
                "template_id": "open-canvas",
                "title": "Warm-up",
                "position": 0,
                "block_ids": [block_id],
            }
        ],
        "blocks": {
            block_id: {
                "id": block_id,
                "component_id": "explanation-block",
                "position": 0,
                "content": {"body": "Plants fix carbon."},
            }
        },
        "media": {},
        "created_at": "2026-09-06T00:00:00Z",
        "updated_at": "2026-09-06T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def _install_dependency_overrides(db_session_factory):
    async def override_current_user():
        return USER

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_async_session] = override_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _seed_user(db_session_factory):
    async with db_session_factory() as session:
        session.add(UserModel(id=USER.id, email=USER.email, name=USER.name))
        await session.commit()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_publish_v1_immutable_and_v2_distinct(db_session_factory):
    async with await _client() as client:
        create = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Photosynthesis", "document": _minimal_lesson()},
        )
        assert create.status_code == 201, create.text
        lesson_id = create.json()["id"]

        pub1 = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub1.status_code == 201, pub1.text
        v1 = pub1.json()
        assert v1["release_number"] == 1
        hash1 = v1["document_hash"]
        assert hash1 == document_hash(v1["document"])

        draft = _minimal_lesson()
        draft["title"] = "Photosynthesis (edited)"
        draft["blocks"]["block-1"]["content"]["body"] = "Edited draft text"
        update = await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": "Photosynthesis (edited)", "document": draft},
        )
        assert update.status_code == 200, update.text

        get_v1 = await client.get(f"/api/v1/learn/releases/{v1['id']}")
        assert get_v1.status_code == 200
        assert get_v1.json()["document_hash"] == hash1
        assert get_v1.json()["document"]["blocks"]["block-1"]["content"]["body"] == "Plants fix carbon."

        pub2 = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub2.status_code == 201, pub2.text
        v2 = pub2.json()
        assert v2["release_number"] == 2
        assert v2["id"] != v1["id"]
        assert v2["document_hash"] != hash1
        assert v2["document"]["blocks"]["block-1"]["content"]["body"] == "Edited draft text"

        listed = await client.get(f"/api/v1/learn/lessons/{lesson_id}/releases")
        assert listed.status_code == 200
        assert [item["release_number"] for item in listed.json()] == [1, 2]

    async with db_session_factory() as session:
        rows = (
            await session.execute(
                select(LearnReleaseModel).where(LearnReleaseModel.editable_lesson_id == lesson_id)
            )
        ).scalars().all()
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_publish_rejects_missing_lesson():
    async with await _client() as client:
        resp = await client.post("/api/v1/learn/lessons/does-not-exist/releases", json={})
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_manual_publish_leaves_provenance_null():
    async with await _client() as client:
        create = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Manual", "document": _minimal_lesson("doc-manual")},
        )
        assert create.status_code == 201, create.text
        lesson_id = create.json()["id"]

        pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub.status_code == 201, pub.text
        body = pub.json()
        assert body["path_lesson_id"] is None
        assert body["path_lesson_revision"] is None
        assert body["objective_hash"] is None


@pytest.mark.asyncio
async def test_unit_path_publish_requires_and_stores_provenance(db_session_factory):
    from core.database.models import ConceptModel, PathLessonModel, PathVersionModel, UnitModel

    async with db_session_factory() as session:
        session.add(
            ConceptModel(
                id="concept-1",
                canonical_slug="photosynthesis",
                subject="biology",
                title="Photosynthesis",
                created_by=USER.id,
            )
        )
        session.add(
            UnitModel(
                id="unit-1",
                owner_id=USER.id,
                title="Unit",
                topic="Photosynthesis",
                subject="biology",
                grade_level="9",
                destination_objective="Explain carbon fixation",
            )
        )
        await session.flush()
        session.add(
            PathVersionModel(
                id="pv-1",
                unit_id="unit-1",
                version=1,
                status="active",
                source_plan_json={},
            )
        )
        await session.flush()
        session.add(
            PathLessonModel(
                id="pl-1",
                path_version_id="pv-1",
                concept_id="concept-1",
                concept_slug="photosynthesis",
                title="Leaf lesson",
                objective="Explain carbon fixation",
                objective_hash="obj-hash-abc",
                primary_knowledge_type="declarative",
                position=0,
                revision=3,
            )
        )
        await session.commit()

    async with await _client() as client:
        create = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Path lesson", "document": _minimal_lesson("doc-path")},
        )
        assert create.status_code == 201, create.text
        lesson_id = create.json()["id"]

        missing = await client.post(
            f"/api/v1/learn/lessons/{lesson_id}/releases",
            json={"path_lesson_id": "missing-pl"},
        )
        assert missing.status_code == 422

        pub = await client.post(
            f"/api/v1/learn/lessons/{lesson_id}/releases",
            json={"path_lesson_id": "pl-1"},
        )
        assert pub.status_code == 201, pub.text
        body = pub.json()
        assert body["path_lesson_id"] == "pl-1"
        assert body["path_lesson_revision"] == 3
        assert body["objective_hash"] == "obj-hash-abc"


@pytest.mark.asyncio
async def test_preview_has_no_attempt_write_surface():
    """Preview is draft-lesson shell only; attempts require a LearningInstance route."""
    from learn.runtime_routes import router as runtime_router

    attempt_paths = [
        getattr(route, "path", "")
        for route in runtime_router.routes
        if "attempt" in getattr(route, "path", "")
    ]
    assert any("/instances/{instance_id}/attempts" in p for p in attempt_paths)
    assert not any("lessons" in p and "attempt" in p for p in attempt_paths)
