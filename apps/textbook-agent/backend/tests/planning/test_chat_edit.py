from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import UserModel
from core.dependencies import get_async_session
from core.entities.user import User
from planning.models import PathPlan, UnitCreate
from planning.service import create_unit, persist_path_plan


TEST_USER = User(
    id="chat-edit-owner",
    email="chat-edit-owner@example.invalid",
    name="Chat Edit Owner",
    created_at="2026-08-01T00:00:00+00:00",
    updated_at="2026-08-01T00:00:00+00:00",
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


def _plan(name: str) -> PathPlan:
    return PathPlan.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


async def _seed_unit(db_session_factory, *, fixture_name: str) -> tuple[str, str, int, PathPlan]:
    plan = _plan(fixture_name)
    async with db_session_factory() as session:
        session.add(UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name))
        unit = await create_unit(
            session,
            owner_id=TEST_USER.id,
            request=UnitCreate(
                title=plan.unit or "Unit",
                topic=plan.unit or "Topic",
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
    return unit_id, version_id, path_revision, plan


async def test_chat_edit_persists_draft_but_still_blocks_approval_when_unreachable(
    db_session_factory, monkeypatch
) -> None:
    """The edit endpoint only runs validate_path_plan; approve_path's stricter
    assert_approvable check must still block an edit that leaves a gap."""
    unit_id, version_id, path_revision, plan = await _seed_unit(
        db_session_factory, fixture_name="grade4-photosynthesis-path.json"
    )

    risky_plan = plan.model_copy(deep=True)
    risky_plan.completeness = risky_plan.completeness.model_copy(
        update={"reaches_destination": False, "note": "chat edit left a gap"}
    )

    called_with: dict[str, object] = {}

    async def fake_edit(current_plan, message, *, unit_context=None, trace_id=None):
        called_with["message"] = message
        called_with["current_plan"] = current_plan
        return risky_plan

    monkeypatch.setattr("planning.routes.run_plan_chat_edit", fake_edit)

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/units/{unit_id}/path:edit-chat",
            json={
                "message": "Drop the last lesson",
                "path_version_id": version_id,
                "path_revision": path_revision,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["validation_messages"] == []
        assert body["path"]["id"] != version_id
        new_version_id = body["path"]["id"]
        new_revision = body["path"]["revision"]

        approve_response = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": new_version_id, "path_revision": new_revision},
        )

    assert called_with["message"] == "Drop the last lesson"
    assert isinstance(called_with["current_plan"], PathPlan)
    assert approve_response.status_code == 409


async def test_chat_edit_runs_validate_path_plan_and_reports_plain_message_without_persisting(
    db_session_factory, monkeypatch
) -> None:
    unit_id, version_id, path_revision, plan = await _seed_unit(
        db_session_factory, fixture_name="grade4-photosynthesis-path.json"
    )

    broken_plan = plan.model_copy(deep=True)
    first_slug = broken_plan.lessons[0].concept_candidate.slug
    broken_plan.modules[0].lessons[1].concept_candidate.slug = first_slug

    async def fake_edit(current_plan, message, *, unit_context=None, trace_id=None):
        return broken_plan

    monkeypatch.setattr("planning.routes.run_plan_chat_edit", fake_edit)

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/units/{unit_id}/path:edit-chat",
            json={
                "message": "merge the first two lessons badly",
                "path_version_id": version_id,
                "path_revision": path_revision,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["validation_messages"], "expected a plain-sentence validation message"
    assert all(
        message.strip() and message[0].isupper() for message in body["validation_messages"]
    )
    # Nothing was persisted: the path payload still points at the original version.
    assert body["path"]["id"] == version_id


async def test_chat_edit_rejects_stale_path_revision(db_session_factory, monkeypatch) -> None:
    unit_id, version_id, path_revision, _plan = await _seed_unit(
        db_session_factory, fixture_name="grade4-photosynthesis-path.json"
    )

    async def fake_edit(current_plan, message, *, unit_context=None, trace_id=None):
        raise AssertionError("the LLM must not be called for a stale mutation")

    monkeypatch.setattr("planning.routes.run_plan_chat_edit", fake_edit)

    app.dependency_overrides[get_current_user] = _override_user
    await _install_session(db_session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/units/{unit_id}/path:edit-chat",
            json={
                "message": "anything",
                "path_version_id": version_id,
                "path_revision": path_revision + 1,
            },
        )

    assert response.status_code == 409
