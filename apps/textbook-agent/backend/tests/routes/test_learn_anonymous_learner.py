"""Anonymous (no-account) learner path: join by invite code, then use only X-Learner-Session.

Teacher JWT dependencies are NOT faked while acting as a student. A switchable override is
used only for teacher setup calls; once ``state["user"]`` is None, ``get_optional_user``
returns None and ``get_current_user`` raises 401, like the real dependencies.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app import app
from core.database.models import UserModel
from infra.auth.middleware import get_current_user, get_optional_user
from infra.database.session import get_async_session
from tests.routes.test_learn_runtime import OTHER, TEACHER, _doc


@pytest.fixture(autouse=True)
def _overrides(db_session_factory):
    state: dict = {"user": TEACHER}

    async def optional_user():
        return state["user"]

    async def required_user():
        if state["user"] is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return state["user"]

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = required_user
    app.dependency_overrides[get_optional_user] = optional_user
    app.dependency_overrides[get_async_session] = override_session
    yield state
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _seed(db_session_factory):
    async with db_session_factory() as session:
        session.add(UserModel(id=TEACHER.id, email=TEACHER.email, name=TEACHER.name))
        session.add(UserModel(id=OTHER.id, email=OTHER.email, name=OTHER.name))
        await session.commit()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _h(token: str) -> dict[str, str]:
    return {"X-Learner-Session": token}


async def _teacher_setup(client: AsyncClient, state: dict) -> dict:
    """Teacher publishes two releases, creates a class and a rolling assignment for one."""
    state["user"] = TEACHER
    release_ids = []
    for title in ("Runtime lesson", "Unassigned lesson"):
        created = await client.post(
            "/api/v1/builder/lessons", json={"title": title, "document": _doc()}
        )
        assert created.status_code == 201, created.text
        pub = await client.post(f"/api/v1/learn/lessons/{created.json()['id']}/releases", json={})
        assert pub.status_code == 201, pub.text
        release_ids.append(pub.json()["id"])
    release_id, unassigned_release_id = release_ids
    klass = await client.post("/api/v1/learn/classes", json={"name": "Period 1"})
    assert klass.status_code == 200, klass.text
    assignment = await client.post(
        "/api/v1/learn/assignments",
        json={
            "learn_release_id": release_id,
            "title": "HW1",
            "class_id": klass.json()["id"],
            "mode": "rolling",
        },
    )
    assert assignment.status_code == 200, assignment.text
    state["user"] = None  # from here on: no teacher at all
    return {
        "release_id": release_id,
        "invite": klass.json()["invite_code"],
        "assignment_id": assignment.json()["id"],
        "unassigned_release_id": unassigned_release_id,
    }


async def _join(client: AsyncClient, invite: str, name: str) -> dict:
    res = await client.post(
        "/api/v1/learn/classes/join", json={"invite_code": invite, "display_name": name}
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _first_instance(client: AsyncClient, joined: dict) -> dict:
    home = await client.get(
        f"/api/v1/learn/learners/{joined['learner_id']}/home", headers=_h(joined["token"])
    )
    assert home.status_code == 200, home.text
    todo = home.json()["buckets"]["due_soon"]
    assert len(todo) == 1
    return todo[0]


_ATTEMPT = {
    "interaction_id": "ix-rt-sequence",
    "client_submission_id": "anon-1",
    "response_json": {"order": ["a", "b", "c"]},
}


@pytest.mark.asyncio
async def test_anonymous_student_full_lesson_flow(_overrides):
    async with _client() as client:
        ctx = await _teacher_setup(client, _overrides)
        joined = await _join(client, ctx["invite"], "Ann")
        token = joined["token"]
        item = await _first_instance(client, joined)
        assert item["assignment_id"] == ctx["assignment_id"]
        instance_id = item["id"]

        inst = await client.get(f"/api/v1/learn/instances/{instance_id}", headers=_h(token))
        assert inst.status_code == 200, inst.text

        rel = await client.get(f"/api/v1/learn/releases/{ctx['release_id']}", headers=_h(token))
        assert rel.status_code == 200, rel.text
        assert rel.json()["id"] == ctx["release_id"]

        resume = await client.post(
            f"/api/v1/learn/instances/{instance_id}/resume",
            json={"section_id": "s1", "mark_visited": False},
            headers=_h(token),
        )
        assert resume.status_code == 200, resume.text

        passive = await client.post(
            f"/api/v1/learn/instances/{instance_id}/sections/complete",
            json={"section_id": "s1"},
            headers=_h(token),
        )
        assert passive.status_code == 200, passive.text
        assert "s1" in passive.json()["completed_section_ids"]

        attempt = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json=_ATTEMPT,
            headers=_h(token),
        )
        assert attempt.status_code == 200, attempt.text

        done = await client.post(
            f"/api/v1/learn/instances/{instance_id}/complete", headers=_h(token)
        )
        assert done.status_code == 200, done.text
        assert done.json()["status"] == "completed"

        # Starting an assigned release is allowed for the learner's own id.
        start = await client.post(
            "/api/v1/learn/instances",
            json={
                "learner_id": joined["learner_id"],
                "learn_release_id": ctx["release_id"],
                "assignment_id": ctx["assignment_id"],
            },
            headers=_h(token),
        )
        assert start.status_code == 200, start.text


@pytest.mark.asyncio
async def test_no_token_and_no_jwt_is_401_everywhere(_overrides):
    async with _client() as client:
        ctx = await _teacher_setup(client, _overrides)
        joined = await _join(client, ctx["invite"], "Ann")
        iid = (await _first_instance(client, joined))["id"]
        calls = [
            ("get", f"/api/v1/learn/instances/{iid}", None),
            ("get", f"/api/v1/learn/releases/{ctx['release_id']}", None),
            ("post", f"/api/v1/learn/instances/{iid}/complete", None),
            ("post", f"/api/v1/learn/instances/{iid}/resume", {"section_id": "s1"}),
            ("post", f"/api/v1/learn/instances/{iid}/sections/complete", {"section_id": "s1"}),
            ("post", f"/api/v1/learn/instances/{iid}/attempts", _ATTEMPT),
            (
                "post",
                "/api/v1/learn/instances",
                {"learner_id": joined["learner_id"], "learn_release_id": ctx["release_id"]},
            ),
            # Teacher-only routes stay closed.
            ("get", "/api/v1/learn/classes", None),
            ("post", f"/api/v1/learn/instances/{iid}/rebuild-progress", None),
        ]
        for method, url, body in calls:
            res = await (client.get(url) if method == "get" else client.post(url, json=body))
            assert res.status_code == 401, (url, res.status_code, res.text)


@pytest.mark.asyncio
async def test_learner_cannot_touch_another_learners_instance(_overrides):
    async with _client() as client:
        ctx = await _teacher_setup(client, _overrides)
        a = await _join(client, ctx["invite"], "Ann")
        b = await _join(client, ctx["invite"], "Ben")
        b_instance = (await _first_instance(client, b))["id"]
        hdr = _h(a["token"])
        calls = [
            ("get", f"/api/v1/learn/instances/{b_instance}", None),
            ("post", f"/api/v1/learn/instances/{b_instance}/complete", None),
            ("post", f"/api/v1/learn/instances/{b_instance}/resume", {"section_id": "s1"}),
            (
                "post",
                f"/api/v1/learn/instances/{b_instance}/sections/complete",
                {"section_id": "s1"},
            ),
            ("post", f"/api/v1/learn/instances/{b_instance}/attempts", _ATTEMPT),
        ]
        for method, url, body in calls:
            res = await (
                client.get(url, headers=hdr)
                if method == "get"
                else client.post(url, json=body, headers=hdr)
            )
            assert res.status_code == 403, (url, res.status_code, res.text)
        start = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": b["learner_id"], "learn_release_id": ctx["release_id"]},
            headers=hdr,
        )
        assert start.status_code == 403


@pytest.mark.asyncio
async def test_invalid_learner_token_is_401(_overrides):
    async with _client() as client:
        ctx = await _teacher_setup(client, _overrides)
        joined = await _join(client, ctx["invite"], "Ann")
        iid = (await _first_instance(client, joined))["id"]
        res = await client.get(f"/api/v1/learn/instances/{iid}", headers=_h("not-a-token"))
        assert res.status_code == 401
        res = await client.get(
            f"/api/v1/learn/releases/{ctx['release_id']}", headers=_h("not-a-token")
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_learner_cannot_read_release_without_instance_or_start_unassigned(_overrides):
    async with _client() as client:
        ctx = await _teacher_setup(client, _overrides)
        joined = await _join(client, ctx["invite"], "Ann")
        token = joined["token"]
        unassigned = ctx["unassigned_release_id"]
        assert unassigned != ctx["release_id"]

        rel = await client.get(f"/api/v1/learn/releases/{unassigned}", headers=_h(token))
        assert rel.status_code == 404
        missing = await client.get("/api/v1/learn/releases/does-not-exist", headers=_h(token))
        assert missing.status_code == 404

        start = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": joined["learner_id"], "learn_release_id": unassigned},
            headers=_h(token),
        )
        assert start.status_code == 403


@pytest.mark.asyncio
async def test_teacher_jwt_paths_still_work(_overrides):
    async with _client() as client:
        ctx = await _teacher_setup(client, _overrides)
        joined = await _join(client, ctx["invite"], "Ann")
        iid = (await _first_instance(client, joined))["id"]
        _overrides["user"] = TEACHER
        assert (await client.get(f"/api/v1/learn/instances/{iid}")).status_code == 200
        assert (await client.get(f"/api/v1/learn/releases/{ctx['release_id']}")).status_code == 200
        _overrides["user"] = OTHER  # not the owner: cannot read the release
        assert (await client.get(f"/api/v1/learn/releases/{ctx['release_id']}")).status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_post_sessions_is_401(_overrides):
    _overrides["user"] = None
    async with _client() as client:
        res = await client.post("/api/v1/learn/sessions", json={"learner_id": "x"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_post_sessions_requires_teacher_ownership(_overrides):
    async with _client() as client:
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "Ada"})
        learner_id = learner.json()["id"]
        ok = await client.post("/api/v1/learn/sessions", json={"learner_id": learner_id})
        assert ok.status_code == 200, ok.text
        _overrides["user"] = OTHER
        denied = await client.post("/api/v1/learn/sessions", json={"learner_id": learner_id})
        assert denied.status_code == 404
