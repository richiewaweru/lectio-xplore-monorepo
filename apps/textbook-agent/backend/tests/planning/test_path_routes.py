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
    routes = {
        (path, method.upper())
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }

    expected = {
        ("/api/v1/units", "POST"),
        ("/api/v1/units", "GET"),
        ("/api/v1/units/{unit_id}", "GET"),
        ("/api/v1/units/{unit_id}", "PATCH"),
        ("/api/v1/units/{unit_id}/path:plan", "POST"),
        ("/api/v1/units/{unit_id}/path:replan", "POST"),
        ("/api/v1/units/{unit_id}/path:approve", "POST"),
        ("/api/v1/units/{unit_id}/path/assumptions/resolve", "POST"),
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
        ("/api/v1/units/{unit_id}/schedule", "GET"),
        ("/api/v1/units/{unit_id}/schedule", "PUT"),
        ("/api/v1/units/{unit_id}/schedule:suggest", "POST"),
        ("/api/v1/units/{unit_id}/groups", "GET"),
        ("/api/v1/units/{unit_id}/groups", "PUT"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape", "GET"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}/actual", "GET"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}/actual", "POST"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}/marks", "POST"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}/marks-summary", "GET"),
        ("/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape/deviations", "POST"),
        (
            "/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape/deviations/{deviation_id}:approve",
            "POST",
        ),
        (
            "/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape/deviations/{deviation_id}:reject",
            "POST",
        ),
        ("/api/v1/units/{unit_id}/compose:preview", "POST"),
        ("/api/v1/units/{unit_id}/compose", "POST"),
        ("/api/v1/units/{unit_id}/compositions", "GET"),
        ("/api/v1/units/{unit_id}/compositions/{composition_id}", "GET"),
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


async def test_schedule_and_groups_reject_cross_user_access(db_session_factory) -> None:
    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        session.add(
            UserModel(
                id="path-route-other",
                email="path-route-other@example.invalid",
                name="Other",
            )
        )
        unit = await create_unit(
            session,
            owner_id="path-route-other",
            request=UnitCreate(
                title="Other unit",
                topic="Other topic",
                subject="Science",
                grade_level="Grade 4",
                destination_objective="Explain an outcome owned by another user.",
                starting_knowledge=[],
            ),
        )
        unit_id = unit.id
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        schedule = await client.get(f"/api/v1/units/{unit_id}/schedule")
        groups = await client.get(f"/api/v1/units/{unit_id}/groups")
        shape = await client.get(f"/api/v1/units/{unit_id}/path/lessons/not-owned/shape")

    assert schedule.status_code == 404
    assert groups.status_code == 404
    assert shape.status_code == 404


async def test_shape_deviation_requires_explicit_approval_over_http(db_session_factory) -> None:
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
            .where(
                PathLessonModel.path_version_id == version.id,
                PathLessonModel.primary_knowledge_type == "conceptual",
            )
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None
        unit_id = unit.id
        version_id = version.id
        path_revision = version.revision
        lesson_id = lesson.id
        lesson_revision = lesson.revision
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        conflict = await client.get(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape",
            params={"lesson_mode": "first_exposure", "misconception_count": 2},
        )
        requested = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape/deviations",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision,
                "lesson_revision": lesson_revision,
                "lesson_mode": "first_exposure",
                "operation": "remove",
                "target_slot": "orient",
                "replacement_slot": None,
                "reason": "The class already completed this orientation activity.",
            },
        )
        deviation_id = requested.json()["id"]
        pending = await client.get(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape",
            params={"lesson_mode": "first_exposure", "misconception_count": 2},
        )
        approved = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape/deviations/{deviation_id}:approve",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision,
                "lesson_revision": lesson_revision,
            },
        )
        resolved = await client.get(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/shape",
            params={"lesson_mode": "first_exposure", "misconception_count": 2},
        )

    assert conflict.status_code == 200
    assert conflict.json()["can_prepare"] is False
    assert requested.status_code == 200
    assert requested.json()["status"] == "pending_teacher"
    assert pending.json()["can_prepare"] is False
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["lesson_revision"] == lesson_revision + 1
    assert resolved.json()["can_prepare"] is True


async def test_schedule_and_groups_round_trip_over_http(db_session_factory) -> None:
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
        unit_id = unit.id
        version_id = version.id
        path_revision = version.revision
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suggested = await client.post(
            f"/api/v1/units/{unit_id}/schedule:suggest",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision,
                "period_count": 2,
                "minutes_per_period": 60,
            },
        )
        assert suggested.status_code == 200
        saved = await client.put(
            f"/api/v1/units/{unit_id}/schedule",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision,
                "schedule_revision": suggested.json()["schedule_revision"],
                "periods": [
                    {
                        "title": period["title"],
                        "lesson_ids": period["lesson_ids"],
                        "planned_minutes": period["planned_minutes"],
                        "teacher_note": period["teacher_note"],
                    }
                    for period in suggested.json()["periods"]
                ],
            },
        )
        loaded = await client.get(f"/api/v1/units/{unit_id}/schedule")
        groups = await client.put(
            f"/api/v1/units/{unit_id}/groups",
            json={
                "groups_revision": 1,
                "groups": [
                    {
                        "label": "Support",
                        "profile": "support",
                        "description": "More modelling and guided practice.",
                        "voice": {
                            "register_name": "simple",
                            "tone": "encouraging",
                            "notation": None,
                        },
                    },
                    {
                        "label": "Core",
                        "profile": "core",
                        "description": "The main class route.",
                        "voice": {
                            "register_name": "balanced",
                            "tone": "neutral",
                            "notation": None,
                        },
                    },
                ],
            },
        )
        stale_groups = await client.put(
            f"/api/v1/units/{unit_id}/groups",
            json={"groups_revision": 1, "groups": []},
        )

    assert saved.status_code == 200
    assert saved.json()["schedule_revision"] == 2
    assert loaded.json() == saved.json()
    assert groups.status_code == 200
    assert [group["profile"] for group in groups.json()["groups"]] == ["support", "core"]
    assert groups.json()["groups"][0]["toggle_profile"]["support_level"] == "high"
    assert stale_groups.status_code == 409
    assert "refresh" in stale_groups.json()["detail"].lower()


async def test_lesson_actual_round_trip_is_revision_guarded_over_http(db_session_factory) -> None:
    plan = PathPlan.model_validate_json(
        (FIXTURES / "grade4-photosynthesis-path.json").read_text(encoding="utf-8")
    )
    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        unit = await create_unit(
            session,
            owner_id=TEST_USER.id,
            request=UnitCreate(
                title=plan.unit or "Photosynthesis", topic=plan.unit or "Photosynthesis",
                subject=plan.subject or "Science", grade_level=plan.grade_level or "Grade 4",
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
        ids = (unit.id, version.id, version.revision, lesson.id, lesson.revision)
        await session.commit()

    unit_id, version_id, path_revision, lesson_id, lesson_revision = ids
    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    payload = {
        "path_version_id": version_id, "path_revision": path_revision,
        "lesson_revision": lesson_revision, "actual_revision": 0,
        "status": "partial", "pace": "slower",
        "established_concepts": ["Leaves use light."],
        "unresolved_misconceptions": ["soil-food"],
        "anchor_used": "Leaf sample", "teacher_note": "Revisit next lesson.",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        saved = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/actual", json=payload
        )
        loaded = await client.get(f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/actual")
        stale = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/actual", json=payload
        )

    assert saved.status_code == 200
    assert saved.json()["revision"] == 1
    assert loaded.json() == saved.json()
    assert stale.status_code == 409
    assert "expected 1" in stale.json()["detail"]


async def test_open_assumption_resolve_known_and_stale_revision(db_session_factory) -> None:
    plan = PathPlan.model_validate_json(
        (FIXTURES / "grade4-photosynthesis-path.json").read_text(encoding="utf-8")
    )
    claimed = "multiply any two fractions"
    plan.lessons[0].external_prerequisites = [claimed]
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
        unit_id = unit.id
        version_id = version.id
        path_revision = version.revision
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        path = await client.get(f"/api/v1/units/{unit_id}/path")
        assert path.status_code == 200
        assert path.json()["open_assumptions"] == [
            {"claimed": claimed, "needed_by": plan.lessons[0].concept_candidate.slug}
        ]

        stale = await client.post(
            f"/api/v1/units/{unit_id}/path/assumptions/resolve",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision - 1 if path_revision > 1 else 999,
                "claimed": claimed,
                "decision": "known",
            },
        )
        assert stale.status_code == 409

        resolved = await client.post(
            f"/api/v1/units/{unit_id}/path/assumptions/resolve",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision,
                "claimed": claimed,
                "decision": "known",
            },
        )
        assert resolved.status_code == 200
        body = resolved.json()
        assert body["open_assumptions"] == []
        assert body["revision"] == path_revision + 1

        unit_response = await client.get(f"/api/v1/units/{unit_id}")
        assert claimed in unit_response.json()["starting_knowledge"]


async def test_open_assumption_resolve_teach_over_http(db_session_factory) -> None:
    plan = PathPlan.model_validate_json(
        (FIXTURES / "grade4-photosynthesis-path.json").read_text(encoding="utf-8")
    )
    claimed = "multiply any two fractions"
    plan.lessons[0].external_prerequisites = [claimed]
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
        unit_id = unit.id
        version_id = version.id
        path_revision = version.revision
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resolved = await client.post(
            f"/api/v1/units/{unit_id}/path/assumptions/resolve",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision,
                "claimed": claimed,
                "decision": "teach",
            },
        )
        assert resolved.status_code == 200
        body = resolved.json()
        assert body["open_assumptions"] == []
        assert body["reaches_destination"] is False
        assert body["prerequisite_risks"] == [
            {
                "missing": claimed,
                "needed_by": plan.lessons[0].concept_candidate.slug,
                "note": "teacher declined",
            }
        ]


async def test_open_assumption_resolve_bogus_claim_is_422(db_session_factory) -> None:
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
        unit_id = unit.id
        version_id = version.id
        path_revision = version.revision
        await session.commit()

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/units/{unit_id}/path/assumptions/resolve",
            json={
                "path_version_id": version_id,
                "path_revision": path_revision,
                "claimed": "never claimed by any lesson",
                "decision": "known",
            },
        )
        assert response.status_code == 422
        assert "not an open assumption" in response.json()["detail"]
