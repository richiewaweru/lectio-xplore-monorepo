from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app, create_app
from core.auth.middleware import get_current_user
from core.database.models import PathLessonModel, UserModel
from core.dependencies import get_async_session
from core.entities.user import User
from planning.models import PathPlan, UnitCreate
from planning.service import approve_path, create_unit, persist_path_plan


TEST_USER = User(
    id="path-route-owner",
    email="path-route@example.invalid",
    name="Path Route",
    created_at="2026-07-31T00:00:00+00:00",
    updated_at="2026-07-31T00:00:00+00:00",
)
FIXTURES = Path(__file__).resolve().parents[3] / "handoff" / "fixtures"


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


async def _override_user() -> User:
    return TEST_USER


async def _install_session(db_session_factory) -> None:
    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_session


def test_phase5_unit_and_path_routes_are_registered() -> None:
    app = create_app()
    routes = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}

    expected = {
        ("/api/v1/units", "POST"),
        ("/api/v1/units", "GET"),
        ("/api/v1/units/{unit_id}", "GET"),
        ("/api/v1/units/{unit_id}", "PATCH"),
        ("/api/v1/units/{unit_id}/path:plan", "POST"),
        ("/api/v1/units/{unit_id}/path:replan", "POST"),
        ("/api/v1/units/{unit_id}/path:approve", "POST"),
        ("/api/v1/units/{unit_id}/path", "GET"),
        ("/api/v1/units/{unit_id}/path/versions", "GET"),
        ("/api/v1/units/{unit_id}/path/versions/{version_id}", "GET"),
        ("/api/v1/units/{unit_id}/path/versions/{version_id}:restore", "POST"),
        ("/api/v1/units/{unit_id}/path/status", "GET"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}", "PATCH"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}:skip", "POST"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}:split", "POST"),
        ("/api/v1/units/{unit_id}/path/lessons:merge", "POST"),
        ("/api/v1/units/{unit_id}/path/lessons:reorder", "POST"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}:prepare", "POST"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}:regenerate", "POST"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}/status", "GET"),
    }
    assert expected <= routes


def test_path_planner_openapi_has_no_count_or_duration_input() -> None:
    schema = create_app().openapi()
    planner_schema = schema["components"]["schemas"]["PathPlannerRequest"]

    assert "lesson_count" not in planner_schema["properties"]
    assert "duration_minutes" not in planner_schema["properties"]
    assert planner_schema["additionalProperties"] is False


async def test_negative_fixture_approval_is_blocked_over_http(db_session_factory) -> None:
    plan = PathPlan.model_validate_json(
        (FIXTURES / "grade8-unreachable-destination-path.json").read_text(encoding="utf-8")
    )
    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        unit = await create_unit(
            session,
            owner_id=TEST_USER.id,
            request=UnitCreate(
                title=plan.unit or "Unreachable",
                topic=plan.unit or "Unreachable",
                subject=plan.subject or "Science",
                grade_level=plan.grade_level or "Grade 8",
                destination_objective=plan.destination_objective or "Destination",
                starting_knowledge=plan.starting_knowledge,
            ),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        unit_id = unit.id
        version_id = version.id
        path_revision = version.revision
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": version_id, "path_revision": path_revision},
        )

    assert response.status_code == 409
    assert "prerequisite" in response.json()["detail"].lower()


async def test_unprepared_lesson_status_is_explicit_over_http(db_session_factory) -> None:
    plan = PathPlan.model_validate_json(
        (FIXTURES / "grade4-photosynthesis-path.json").read_text(encoding="utf-8")
    )
    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        unit = await create_unit(
            session,
            owner_id=TEST_USER.id,
            request=UnitCreate(
                title=plan.unit or "Photosynthesis",
                topic=plan.unit or "Photosynthesis",
                subject=plan.subject or "Science",
                grade_level=plan.grade_level or "Grade 4",
                destination_objective=plan.destination_objective or "Destination",
                starting_knowledge=plan.starting_knowledge,
            ),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        await approve_path(session, version)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None
        lesson_id = lesson.id
        objective_hash = lesson.objective_hash
        unit_id = unit.id
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/status"
        )

    assert response.status_code == 200
    assert response.json() == {
        "path_lesson_id": lesson_id,
        "lesson_revision": 1,
        "generation_id": None,
        "generation_status": "unprepared",
        "workflow_stage": "unprepared",
        "objective_hash": objective_hash,
        "stale": False,
        "can_prepare": True,
        "can_regenerate": False,
    }


async def test_path_edit_revokes_approval_before_preparation(db_session_factory) -> None:
    plan = PathPlan.model_validate_json(
        (FIXTURES / "grade4-photosynthesis-path.json").read_text(encoding="utf-8")
    )
    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        unit = await create_unit(
            session,
            owner_id=TEST_USER.id,
            request=UnitCreate(
                title=plan.unit or "Photosynthesis",
                topic=plan.unit or "Photosynthesis",
                subject=plan.subject or "Science",
                grade_level=plan.grade_level or "Grade 4",
                destination_objective=plan.destination_objective or "Destination",
                starting_knowledge=plan.starting_knowledge,
            ),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        await approve_path(session, version)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None
        unit_id = unit.id
        lesson_id = lesson.id
        version_id = version.id
        path_revision = version.revision
        lesson_revision = lesson.revision
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        patched = await client.patch(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision,
                "lesson_revision": lesson_revision,
                "objective": "Identify what plants need before making food.",
            },
        )
        blocked = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}:prepare",
            json={
                "path_version_id": patched.json()["path_version_id"],
                "path_revision": patched.json()["path_revision"],
                "lesson_revision": patched.json()["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )

    assert patched.status_code == 200
    assert blocked.status_code == 409
    assert "approved" in blocked.json()["detail"].lower()


async def test_history_restore_status_and_stale_edit_are_explicit(db_session_factory) -> None:
    plan = PathPlan.model_validate_json(
        (FIXTURES / "grade4-photosynthesis-path.json").read_text(encoding="utf-8")
    )
    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        unit = await create_unit(
            session,
            owner_id=TEST_USER.id,
            request=UnitCreate(
                title=plan.unit or "Photosynthesis",
                topic=plan.unit or "Photosynthesis",
                subject=plan.subject or "Science",
                grade_level=plan.grade_level or "Grade 4",
                destination_objective=plan.destination_objective or "Destination",
                starting_knowledge=plan.starting_knowledge,
            ),
        )
        first = await persist_path_plan(session, unit=unit, plan=plan)
        second = await persist_path_plan(session, unit=unit, plan=plan, prior_version=first)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == second.id)
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None
        unit_id = unit.id
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        history = await client.get(f"/api/v1/units/{unit_id}/path/versions")
        aggregate = await client.get(f"/api/v1/units/{unit_id}/path/status")
        stale = await client.patch(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson.id}",
            json={
                "path_version_id": second.id,
                "path_revision": second.revision + 1,
                "lesson_revision": lesson.revision,
                "title": "Stale overwrite",
            },
        )
        restored = await client.post(
            f"/api/v1/units/{unit_id}/path/versions/{first.id}:restore",
            json={
                "path_version_id": second.id,
                "path_revision": second.revision,
                "reason": "Undo the replan",
            },
        )

    assert history.status_code == 200
    assert [item["status"] for item in history.json()] == ["draft", "superseded"]
    assert aggregate.status_code == 200
    assert (
        aggregate.json()["counts"]["unprepared"]
        + aggregate.json()["counts"]["warning"]
        == len(plan.lessons)
    )
    assert stale.status_code == 409
    assert "refresh" in stale.json()["detail"].lower()
    assert restored.status_code == 200
    assert restored.json()["version"] == 3
    assert restored.json()["status"] == "draft"
