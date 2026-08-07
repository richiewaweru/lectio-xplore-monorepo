"""PR3 optional path actions: hints, foundation insert, mark known — full critical flow."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import UserModel
from core.dependencies import get_async_session
from core.entities.user import User
from planning.models import PreparedLessonResponse
from planning.validation import adjacent_merge_hints
from tests.planning.path_helpers import overlapping_pair_plan, sample_canonical_plan


TEST_USER = User(
    id="optional-flow-owner",
    email="optional-flow@example.invalid",
    name="Optional Flow Owner",
    created_at="2026-08-01T00:00:00+00:00",
    updated_at="2026-08-01T00:00:00+00:00",
)


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


async def _seed_user(db_session_factory) -> None:
    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        await session.commit()


async def _create_unit_and_plan(client: AsyncClient) -> tuple[str, dict]:
    created = await client.post(
        "/api/v1/units",
        json={
            "title": "Circulation",
            "topic": "circulatory system",
            "subject": "Science",
            "grade_level": "Grade 7",
            "destination_objective": "describe circulation",
            "starting_knowledge": ["organs exist"],
        },
    )
    assert created.status_code == 201
    unit_id = created.json()["id"]
    planned = await client.post(
        f"/api/v1/units/{unit_id}/path:plan",
        json={
            "topic": "circulatory system",
            "subject": "Science",
            "grade_level": "Grade 7",
            "destination_objective": "describe circulation",
            "starting_knowledge": ["organs exist"],
        },
    )
    assert planned.status_code == 201, planned.text
    return unit_id, planned.json()


def _install_mocks(monkeypatch, *, plan, db_session_factory) -> None:
    async def fake_planner(request, *, trace_id=None):
        return plan

    async def fake_prepare(session, *, unit, version, lesson, request):
        return (
            PreparedLessonResponse(
                generation_id="gen-optional-1",
                path_lesson_id=lesson.id,
                objective=lesson.objective,
                objective_hash=lesson.objective_hash,
                skeleton_id="conceptual-core",
                skeleton_version=1,
                slots=["orient", "teach", "check"],
                section_roles=["orient", "teach", "check"],
                status="awaiting_review",
                reused=False,
            ),
            None,
        )

    monkeypatch.setattr("planning.routes.run_path_planner", fake_planner)
    monkeypatch.setattr("planning.routes.prepare_path_lesson", fake_prepare)

    async def override_user() -> User:
        return TEST_USER

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session


async def test_baseline_create_plan_approve_prepare(db_session_factory, monkeypatch) -> None:
    _install_mocks(monkeypatch, plan=sample_canonical_plan(), db_session_factory=db_session_factory)
    await _seed_user(db_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unit_id, path = await _create_unit_and_plan(client)
        approved = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        assert approved.status_code == 200
        path = approved.json()
        prepared = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{path['lessons'][0]['id']}:prepare",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": path["lessons"][0]["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        assert prepared.status_code == 200
        assert prepared.json()["generation_id"] == "gen-optional-1"


async def test_hints_do_not_block_approve_prepare(db_session_factory, monkeypatch) -> None:
    _install_mocks(monkeypatch, plan=overlapping_pair_plan(), db_session_factory=db_session_factory)
    await _seed_user(db_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unit_id, path = await _create_unit_and_plan(client)
        assert any(
            row.get("source") == "deterministic"
            for row in path.get("merge_critic_results") or []
        )
        approved = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        assert approved.status_code == 200
        path = approved.json()
        assert path["status"] == "approved"
        prepared = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{path['lessons'][0]['id']}:prepare",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": path["lessons"][0]["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        assert prepared.status_code == 200


async def test_hint_merge_then_prepare(db_session_factory, monkeypatch) -> None:
    _install_mocks(monkeypatch, plan=overlapping_pair_plan(), db_session_factory=db_session_factory)
    await _seed_user(db_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unit_id, path = await _create_unit_and_plan(client)
        lesson_a = path["lessons"][0]
        lesson_b = path["lessons"][1]
        merged = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons:merge",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_ids": [lesson_a["id"], lesson_b["id"]],
                "lesson_revisions": {
                    lesson_a["id"]: lesson_a["revision"],
                    lesson_b["id"]: lesson_b["revision"],
                },
                "merged": {
                    "title": "Heart structure and function",
                    "objective": "describe heart structure and pumping action",
                    "must_establish": [
                        "the heart has four chambers",
                        "the heart acts as a pump",
                    ],
                    "knowledge_type": "conceptual",
                },
            },
        )
        assert merged.status_code == 200, merged.text
        path = merged.json()["path"]
        assert len(path["lessons"]) == 2
        approved = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        assert approved.status_code == 200
        path = approved.json()
        prepared = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{path['lessons'][0]['id']}:prepare",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": path["lessons"][0]["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        assert prepared.status_code == 200


async def test_insert_foundation_then_prepare(db_session_factory, monkeypatch) -> None:
    _install_mocks(monkeypatch, plan=sample_canonical_plan(), db_session_factory=db_session_factory)
    await _seed_user(db_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unit_id, path = await _create_unit_and_plan(client)
        target = path["lessons"][1]
        inserted = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons:insert-foundation",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "before_lesson_id": target["id"],
                "lesson": {
                    "title": "Organs work together",
                    "objective": "explain that organs work together as a system",
                    "must_establish": ["organs cooperate in systems"],
                    "knowledge_type": "conceptual",
                },
            },
        )
        assert inserted.status_code == 200, inserted.text
        path = inserted.json()
        assert len(path["lessons"]) == 5
        foundation = next(
            lesson for lesson in path["lessons"] if lesson["title"] == "Organs work together"
        )
        shifted_target = next(
            lesson for lesson in path["lessons"] if lesson["title"] == target["title"]
        )
        assert foundation["id"] in shifted_target["prerequisites"]
        approved = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        assert approved.status_code == 200
        path = approved.json()
        prepared = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{path['lessons'][0]['id']}:prepare",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": path["lessons"][0]["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        assert prepared.status_code == 200


async def test_mark_starting_knowledge_then_prepare(db_session_factory, monkeypatch) -> None:
    _install_mocks(monkeypatch, plan=sample_canonical_plan(), db_session_factory=db_session_factory)
    await _seed_user(db_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unit_id, path = await _create_unit_and_plan(client)
        marked = await client.post(
            f"/api/v1/units/{unit_id}/path/starting-knowledge:mark",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "knowledge": "blood is a liquid tissue",
            },
        )
        assert marked.status_code == 200
        unit = await client.get(f"/api/v1/units/{unit_id}")
        assert "blood is a liquid tissue" in unit.json()["starting_knowledge"]
        approved = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        assert approved.status_code == 200
        path = approved.json()
        prepared = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{path['lessons'][0]['id']}:prepare",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": path["lessons"][0]["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        assert prepared.status_code == 200


async def test_insert_foundation_stale_revision_is_recoverable(
    db_session_factory, monkeypatch
) -> None:
    _install_mocks(monkeypatch, plan=sample_canonical_plan(), db_session_factory=db_session_factory)
    await _seed_user(db_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unit_id, path = await _create_unit_and_plan(client)
        target = path["lessons"][1]
        stale = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons:insert-foundation",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"] - 1,
                "before_lesson_id": target["id"],
                "lesson": {
                    "title": "Stale foundation",
                    "objective": "stale attempt",
                    "must_establish": ["stale"],
                    "knowledge_type": "factual",
                },
            },
        )
        assert stale.status_code in {409, 422}
        fresh = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons:insert-foundation",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "before_lesson_id": target["id"],
                "lesson": {
                    "title": "Organs work together",
                    "objective": "explain that organs work together as a system",
                    "must_establish": ["organs cooperate in systems"],
                    "knowledge_type": "conceptual",
                },
            },
        )
        assert fresh.status_code == 200
        approved = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={
                "path_version_id": fresh.json()["id"],
                "path_revision": fresh.json()["revision"],
            },
        )
        assert approved.status_code == 200


def test_adjacent_merge_hints_unit() -> None:
    class _Lesson:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    overlapping = adjacent_merge_hints(
        [
            _Lesson(
                id="a",
                primary_knowledge_type="conceptual",
                must_establish=[
                    "the heart has four chambers",
                    "blood flows through the heart",
                ],
                objective="identify heart chambers",
                skipped=False,
            ),
            _Lesson(
                id="b",
                primary_knowledge_type="conceptual",
                must_establish=[
                    "the heart has four chambers",
                    "the heart acts as a pump",
                ],
                objective="explain pumping action",
                skipped=False,
            ),
        ]
    )
    assert overlapping
    assert overlapping[0]["source"] == "deterministic"

    dissimilar = adjacent_merge_hints(
        [
            _Lesson(
                id="a",
                primary_knowledge_type="factual",
                must_establish=["arteries carry blood"],
                objective="name arteries",
                skipped=False,
            ),
            _Lesson(
                id="b",
                primary_knowledge_type="conceptual",
                must_establish=["veins return blood"],
                objective="explain vein function",
                skipped=False,
            ),
        ]
    )
    assert dissimilar == []
