"""Stage F/G style end-to-end smoke with mocked planner LLM."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import UserModel
from core.dependencies import get_async_session
from core.entities.user import User
from planning.models import ConstructorOutput, PreparedLessonResponse
from planning.validation import PathPlanningError
from tests.planning.path_helpers import sample_canonical_plan


TEST_USER = User(
    id="e2e-owner",
    email="e2e-owner@example.invalid",
    name="E2E Owner",
    created_at="2026-08-01T00:00:00+00:00",
    updated_at="2026-08-01T00:00:00+00:00",
)


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


async def test_create_plan_approve_prepare_smoke(db_session_factory, monkeypatch) -> None:
    plan = sample_canonical_plan()
    planner_calls = {"n": 0}

    async def fake_constructor(*args, **kwargs):
        return ConstructorOutput(
            title="Circulation",
            topic="circulatory system",
            destination_objective="describe how blood moves around the body",
            starting_knowledge=["the body is made of organs"],
            curriculum_context=None,
            class_notes=None,
            clarifying_question=None,
        )

    async def fake_planner(request, *, trace_id=None):
        planner_calls["n"] += 1
        assert request.topic == "circulatory system"
        assert "must_include" not in request.model_dump()
        return plan

    async def fake_prepare(session, *, unit, version, lesson, request):
        return (
            PreparedLessonResponse(
                generation_id="gen-smoke-1",
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

    monkeypatch.setattr("planning.routes.run_constructor", fake_constructor)
    monkeypatch.setattr("planning.routes.run_path_planner", fake_planner)
    monkeypatch.setattr("planning.routes.prepare_path_lesson", fake_prepare)

    async def override_user() -> User:
        return TEST_USER

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session

    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        readback = await client.post(
            "/api/v1/units/constructor/readback",
            json={
                "subject": "Science",
                "grade_level": "Grade 7",
                "raw_text": (
                    "The circulatory system. Students should describe the main parts "
                    "— heart, blood vessels and blood — and explain how blood moves "
                    "around the body."
                ),
            },
        )
        assert readback.status_code == 200
        body = readback.json()
        assert body["title"] == "Circulation"
        assert body["topic"] == "circulatory system"
        assert not body["destination_objective"].lower().startswith("by the end")

        created = await client.post(
            "/api/v1/units",
            json={
                "title": body["title"],
                "topic": body["topic"],
                "subject": "Science",
                "grade_level": "Grade 7",
                "destination_objective": body["destination_objective"],
                "starting_knowledge": body["starting_knowledge"],
                "curriculum_context": None,
                "class_notes": None,
            },
        )
        assert created.status_code == 201
        unit_id = created.json()["id"]

        planned = await client.post(
            f"/api/v1/units/{unit_id}/path:plan",
            json={
                "topic": body["topic"],
                "subject": "Science",
                "grade_level": "Grade 7",
                "destination_objective": body["destination_objective"],
                "starting_knowledge": body["starting_knowledge"],
                "curriculum_context": None,
                "class_notes": None,
            },
        )
        assert planned.status_code == 201, planned.text
        path = planned.json()
        assert planner_calls["n"] == 1
        assert path["open_assumptions"] == []
        assert path["merge_critic_results"] == []
        assert path["prerequisite_risks"] == []
        assert len(path["lessons"]) == 4
        assert path["lessons"][0]["concept_slug"].startswith("science.")

        lesson = path["lessons"][0]
        patched = await client.patch(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson['id']}",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": lesson["revision"],
                "title": "The Heart as a Pump (edited)",
            },
        )
        assert patched.status_code == 200, patched.text
        path = (await client.get(f"/api/v1/units/{unit_id}/path")).json()
        lesson = path["lessons"][0]
        assert lesson["title"] == "The Heart as a Pump (edited)"

        approved = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        assert approved.status_code == 200, approved.text
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
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()["generation_id"] == "gen-smoke-1"


async def test_recoverable_planning_failure_retries_same_unit(db_session_factory, monkeypatch) -> None:
    attempts = {"n": 0}
    good = sample_canonical_plan()

    async def flaky_planner(request, *, trace_id=None):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise PathPlanningError(["forward dependency on L9"])
        return good

    monkeypatch.setattr("planning.routes.run_path_planner", flaky_planner)

    async def override_user() -> User:
        return TEST_USER

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session

    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

        payload = {
            "topic": "circulatory system",
            "subject": "Science",
            "grade_level": "Grade 7",
            "destination_objective": "describe circulation",
            "starting_knowledge": ["organs exist"],
        }
        assert (await client.post(f"/api/v1/units/{unit_id}/path:plan", json=payload)).status_code == 422
        assert (await client.post(f"/api/v1/units/{unit_id}/path:plan", json=payload)).status_code == 422
        third = await client.post(f"/api/v1/units/{unit_id}/path:plan", json=payload)
        assert third.status_code == 201, third.text

        units = await client.get("/api/v1/units")
        assert units.status_code == 200
        assert len(units.json()) == 1
        assert units.json()[0]["id"] == unit_id
