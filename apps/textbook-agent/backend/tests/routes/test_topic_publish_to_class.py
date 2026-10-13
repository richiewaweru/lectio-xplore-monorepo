"""Doc 38 3.4: publish a unit's topic path to a class."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from core.database.models import (
    ConceptModel,
    EditableLessonModel,
    GenerationModel,
    LearnReleaseModel,
    NativeRealizationModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from core.entities.user import User
from infra.auth.middleware import get_current_user, get_optional_user
from infra.database.session import get_async_session
from learn.runtime_models import LearningInstanceModel

BASE = "/api/v1"


def _now() -> datetime:
    return datetime.now(UTC)


def _user(uid: str) -> User:
    return User(
        id=uid,
        email=f"{uid}@example.invalid",
        name=uid,
        picture_url=None,
        has_profile=True,
        created_at=_now(),
        updated_at=_now(),
    )


TEACHER = _user("tp-teacher")
OTHER = _user("tp-other")
_current = {"user": TEACHER}


def _doc(doc_id: str, body: str = "Plants fix carbon.") -> dict:
    return {
        "version": 1,
        "id": doc_id,
        "title": "Lesson",
        "subject": "biology",
        "preset_id": "blue-classroom",
        "source": "manual",
        "sections": [
            {
                "id": "s1",
                "template_id": "open-canvas",
                "title": "Warm-up",
                "position": 0,
                "block_ids": ["b1"],
            }
        ],
        "blocks": {
            "b1": {
                "id": "b1",
                "component_id": "explanation-block",
                "position": 0,
                "content": {"body": body},
            }
        },
        "media": {},
        "created_at": "2026-09-06T00:00:00Z",
        "updated_at": "2026-09-06T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def _overrides(db_session_factory):
    _current["user"] = TEACHER

    async def override_user():
        return _current["user"]

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_optional_user] = override_user
    app.dependency_overrides[get_async_session] = override_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _users(db_session_factory):
    async with db_session_factory() as session:
        for u in (TEACHER, OTHER):
            session.add(UserModel(id=u.id, email=u.email, name=u.name))
        await session.commit()


@pytest.fixture
async def unit(db_session_factory):
    """Unit with 3 path lessons: pl-1, pl-2 generated (ready learn), pl-3 not."""
    async with db_session_factory() as session:
        session.add(
            ConceptModel(
                id="c1", canonical_slug="tp-c1", subject="biology", title="C", created_by=TEACHER.id
            )
        )
        session.add(
            UnitModel(
                id="tp-unit",
                owner_id=TEACHER.id,
                title="Photosynthesis",
                topic="Photosynthesis",
                subject="biology",
                grade_level="9",
                destination_objective="Explain photosynthesis",
                active_path_version_id="tp-pv",
            )
        )
        await session.flush()
        session.add(
            PathVersionModel(id="tp-pv", unit_id="tp-unit", version=1, status="active", source_plan_json={})
        )
        await session.flush()
        for i in (1, 2, 3):
            session.add(
                PathLessonModel(
                    id=f"pl-{i}",
                    path_version_id="tp-pv",
                    concept_id="c1",
                    concept_slug="tp-c1",
                    title=f"Lesson {i}",
                    objective=f"Objective {i}",
                    objective_hash=f"hash-{i}",
                    primary_knowledge_type="declarative",
                    position=i,
                    revision=1,
                )
            )
        await session.flush()
        for i in (1, 2):
            gen_id = f"gen-{i}"
            session.add(
                GenerationModel(
                    id=gen_id,
                    user_id=TEACHER.id,
                    subject="biology",
                    requested_template_id="t",
                    requested_preset_id="p",
                )
            )
            session.add(
                EditableLessonModel(
                    id=f"el-{i}",
                    user_id=TEACHER.id,
                    source_generation_id=gen_id,
                    source_type="native_learn",
                    title=f"Lesson {i}",
                    document_json=_doc(f"doc-{i}", body=f"Body {i}"),
                )
            )
            session.add(
                NativeRealizationModel(
                    id=f"nr-{i}",
                    path_lesson_id=f"pl-{i}",
                    path="learn",
                    teaching_plan_id="tpl",
                    teaching_plan_revision=1,
                    teaching_plan_hash="h",
                    native_policy_version="1",
                    native_policy_hash="h",
                    package_contract_version="1",
                    package_contract_hash="h",
                    status="ready",
                    output_id=gen_id,
                )
            )
        await session.commit()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _make_class(client: AsyncClient) -> dict:
    created = await client.post(f"{BASE}/learn/classes", json={"name": "Demo"})
    assert created.status_code in (200, 201), created.text
    return created.json()


async def _join(client: AsyncClient, code: str, name: str = "Visitor") -> dict:
    res = await client.post(
        f"{BASE}/learn/classes/join", json={"invite_code": code, "display_name": name}
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _instances(db_session_factory, learner_id: str) -> list[LearningInstanceModel]:
    async with db_session_factory() as session:
        rows = await session.scalars(
            select(LearningInstanceModel).where(LearningInstanceModel.learner_id == learner_id)
        )
        return list(rows.all())


@pytest.mark.asyncio
async def test_publishes_all_generated_and_shows_not_generated(db_session_factory, unit):
    async with await _client() as client:
        cls = await _make_class(client)
        cands = await client.get(
            f"{BASE}/units/tp-unit/publish-candidates", params={"class_id": cls["id"]}
        )
        assert cands.status_code == 200, cands.text
        lessons = cands.json()["lessons"]
        assert [(x["position"], x["generated"], x["status"]) for x in lessons] == [
            (1, True, "ready_to_publish"),
            (2, True, "ready_to_publish"),
            (3, False, "not_generated"),
        ]

        res = await client.post(
            f"{BASE}/units/tp-unit/publish-to-class",
            json={"class_id": cls["id"], "path_lesson_ids": ["pl-1", "pl-2", "pl-3"]},
        )
        assert res.status_code == 200, res.text
        results = {r["path_lesson_id"]: r for r in res.json()["results"]}
        assert results["pl-1"]["status"] == "published"
        assert results["pl-1"]["release_created"] and results["pl-1"]["assignment_created"]
        assert results["pl-2"]["status"] == "published"
        assert results["pl-3"]["status"] == "not_generated"
        assert results["pl-3"]["release_id"] is None

        async with db_session_factory() as session:
            releases = (await session.scalars(select(LearnReleaseModel))).all()
        assert {r.path_lesson_id for r in releases} == {"pl-1", "pl-2"}

        after = await client.get(
            f"{BASE}/units/tp-unit/publish-candidates", params={"class_id": cls["id"]}
        )
        statuses = [x["status"] for x in after.json()["lessons"]]
        assert statuses == ["published", "published", "not_generated"]


@pytest.mark.asyncio
async def test_late_publish_reaches_already_joined_learner(db_session_factory, unit):
    async with await _client() as client:
        cls = await _make_class(client)
        joined = await _join(client, cls["invite_code"])
        assert await _instances(db_session_factory, joined["learner_id"]) == []

        first = await client.post(
            f"{BASE}/units/tp-unit/publish-to-class",
            json={"class_id": cls["id"], "path_lesson_ids": ["pl-1"]},
        )
        assert first.status_code == 200, first.text
        assert len(await _instances(db_session_factory, joined["learner_id"])) == 1

        second = await client.post(
            f"{BASE}/units/tp-unit/publish-to-class",
            json={"class_id": cls["id"], "path_lesson_ids": ["pl-2"]},
        )
        assert second.json()["results"][0]["status"] == "published"
        assert len(await _instances(db_session_factory, joined["learner_id"])) == 2

        # A visitor who joins afterwards gets both through rolling distribution.
        later = await _join(client, cls["invite_code"], "Later")
        assert len(await _instances(db_session_factory, later["learner_id"])) == 2


@pytest.mark.asyncio
async def test_rerun_is_idempotent(db_session_factory, unit):
    async with await _client() as client:
        cls = await _make_class(client)
        body = {"class_id": cls["id"], "path_lesson_ids": ["pl-1", "pl-2"]}
        first = await client.post(f"{BASE}/units/tp-unit/publish-to-class", json=body)
        second = await client.post(f"{BASE}/units/tp-unit/publish-to-class", json=body)
        assert second.status_code == 200, second.text
        by_first = {r["path_lesson_id"]: r for r in first.json()["results"]}
        for r in second.json()["results"]:
            assert r["status"] == "already_published"
            assert not r["release_created"] and not r["assignment_created"]
            assert r["release_id"] == by_first[r["path_lesson_id"]]["release_id"]
            assert r["assignment_id"] == by_first[r["path_lesson_id"]]["assignment_id"]


@pytest.mark.asyncio
async def test_edited_lesson_gets_new_release_and_assignment(db_session_factory, unit):
    async with await _client() as client:
        cls = await _make_class(client)
        body = {"class_id": cls["id"], "path_lesson_ids": ["pl-1"]}
        first = (await client.post(f"{BASE}/units/tp-unit/publish-to-class", json=body)).json()
        async with db_session_factory() as session:
            lesson = await session.get(EditableLessonModel, "el-1")
            lesson.document_json = _doc("doc-1", body="Edited")
            await session.commit()
        cands = await client.get(
            f"{BASE}/units/tp-unit/publish-candidates", params={"class_id": cls["id"]}
        )
        assert cands.json()["lessons"][0]["has_unpublished_changes"] is True
        second = (await client.post(f"{BASE}/units/tp-unit/publish-to-class", json=body)).json()
        r1, r2 = first["results"][0], second["results"][0]
        assert r2["release_id"] != r1["release_id"] and r2["release_number"] == 2
        assert r2["release_created"] and r2["assignment_created"]


@pytest.mark.asyncio
async def test_non_owner_cannot_publish_or_list(db_session_factory, unit):
    async with await _client() as client:
        cls = await _make_class(client)
        _current["user"] = OTHER
        listed = await client.get(f"{BASE}/units/tp-unit/publish-candidates")
        assert listed.status_code == 404
        res = await client.post(
            f"{BASE}/units/tp-unit/publish-to-class",
            json={"class_id": cls["id"], "path_lesson_ids": ["pl-1"]},
        )
        assert res.status_code == 404

        # Owner of the unit but not of the class.
        _current["user"] = TEACHER
        async with db_session_factory() as session:
            session.add(
                UnitModel(
                    id="other-unit",
                    owner_id=OTHER.id,
                    title="x",
                    topic="x",
                    subject="b",
                    grade_level="9",
                    destination_objective="x",
                )
            )
            await session.commit()
        _current["user"] = OTHER
        res = await client.post(
            f"{BASE}/units/other-unit/publish-to-class",
            json={"class_id": cls["id"], "path_lesson_ids": ["pl-1"]},
        )
        assert res.status_code == 404  # class belongs to TEACHER


@pytest.mark.asyncio
async def test_path_lesson_outside_unit_rejected(db_session_factory, unit):
    async with await _client() as client:
        cls = await _make_class(client)
        res = await client.post(
            f"{BASE}/units/tp-unit/publish-to-class",
            json={"class_id": cls["id"], "path_lesson_ids": ["pl-1", "nope"]},
        )
        assert res.status_code == 422
        async with db_session_factory() as session:
            assert (await session.scalars(select(LearnReleaseModel))).all() == []


@pytest.mark.asyncio
async def test_assignments_endpoint_rejects_unlinked_release_when_required(
    db_session_factory, unit
):
    async with await _client() as client:
        cls = await _make_class(client)
        created = await client.post(
            f"{BASE}/builder/lessons", json={"title": "Manual", "document": _doc("manual")}
        )
        lesson_id = created.json()["id"]
        rel = await client.post(f"{BASE}/learn/lessons/{lesson_id}/releases", json={})
        assert rel.json()["path_lesson_id"] is None
        payload = {"learn_release_id": rel.json()["id"], "title": "Manual", "class_id": cls["id"]}

        rejected = await client.post(
            f"{BASE}/learn/assignments", json={**payload, "require_path_lesson_id": True}
        )
        assert rejected.status_code == 422
        assert rejected.json()["detail"]["code"] == "RELEASE_NOT_LINKED_TO_PATH_LESSON"

        # Existing behaviour for other callers is unchanged.
        legacy = await client.post(f"{BASE}/learn/assignments", json=payload)
        assert legacy.status_code == 200, legacy.text


@pytest.mark.asyncio
async def test_identical_unlinked_release_is_not_reused_silently(db_session_factory, unit):
    """An identical-content release without a topic link cannot be relinked."""
    async with await _client() as client:
        cls = await _make_class(client)
        pub = await client.post(f"{BASE}/learn/lessons/el-1/releases", json={})
        assert pub.status_code == 201, pub.text
        assert pub.json()["path_lesson_id"] is None
        res = await client.post(
            f"{BASE}/units/tp-unit/publish-to-class",
            json={"class_id": cls["id"], "path_lesson_ids": ["pl-1"]},
        )
        item = res.json()["results"][0]
        assert item["status"] == "failed"
        assert item["assignment_id"] is None
