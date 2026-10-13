"""Return code: friendly learner codes, public resume, and same-device join."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import func, select
from tests.routes.test_learn_anonymous_learner import (
    _client,
    _first_instance,
    _h,
    _join,
    _overrides,  # noqa: F401 - fixture
    _seed,  # noqa: F401 - autouse fixture
    _teacher_setup,
)

from infra.rate_limit import limiter
from learn.runtime_models import LearnerIdentityModel

_CODE_RE = re.compile(r"^[A-Z]{3,6}-[A-HJ-NP-Z2-9]{4}$")


@pytest.fixture
def state(_overrides):  # noqa: F811 - reuse the imported fixture by name
    return _overrides


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


async def _learner_count(db_session_factory) -> int:
    async with db_session_factory() as session:
        return await session.scalar(select(func.count()).select_from(LearnerIdentityModel))


@pytest.mark.asyncio
async def test_join_returns_friendly_code(state):
    async with _client() as client:
        ctx = await _teacher_setup(client, state)
        a = await _join(client, ctx["invite"], "Ann")
        b = await _join(client, ctx["invite"], "Ben")
        assert _CODE_RE.match(a["code"]), a["code"]
        assert _CODE_RE.match(b["code"]), b["code"]
        assert a["code"] != b["code"]


@pytest.mark.asyncio
async def test_resume_mints_new_session_and_keeps_old(state):
    async with _client() as client:
        ctx = await _teacher_setup(client, state)
        joined = await _join(client, ctx["invite"], "Ann")
        res = await client.post(
            "/api/v1/learn/learners/resume", json={"code": joined["code"].lower()}
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["learner_id"] == joined["learner_id"]
        assert body["display_name"] == "Ann"
        assert body["token"] != joined["token"]
        assert body["session_id"] != joined["session_id"]
        for token in (body["token"], joined["token"]):
            home = await client.get(
                f"/api/v1/learn/learners/{joined['learner_id']}/home", headers=_h(token)
            )
            assert home.status_code == 200, home.text


@pytest.mark.asyncio
async def test_resume_normalises_spaces_and_whitespace(state):
    async with _client() as client:
        ctx = await _teacher_setup(client, state)
        joined = await _join(client, ctx["invite"], "Ann")
        spaced = "  " + joined["code"].replace("-", " ").lower() + " "
        res = await client.post("/api/v1/learn/learners/resume", json={"code": spaced})
        assert res.status_code == 200, res.text
        assert res.json()["learner_id"] == joined["learner_id"]


@pytest.mark.asyncio
async def test_resume_wrong_code_is_generic_404(state):
    async with _client() as client:
        await _teacher_setup(client, state)
        res = await client.post("/api/v1/learn/learners/resume", json={"code": "NOPE-AAAA"})
        assert res.status_code == 404
        assert res.json() == {"detail": "That code was not found"}


@pytest.mark.asyncio
async def test_resume_rate_limited_after_repeated_guesses(state):
    async with _client() as client:
        await _teacher_setup(client, state)
        statuses = []
        for i in range(12):
            res = await client.post(
                "/api/v1/learn/learners/resume", json={"code": f"GUESS-{i:04d}"}
            )
            statuses.append(res.status_code)
        assert statuses[:10] == [404] * 10
        assert 429 in statuses[10:]


@pytest.mark.asyncio
async def test_legacy_hex_code_resumes(state, db_session_factory):
    async with _client() as client:
        ctx = await _teacher_setup(client, state)
        joined = await _join(client, ctx["invite"], "Ann")
        async with db_session_factory() as session:
            learner = await session.get(LearnerIdentityModel, joined["learner_id"])
            learner.invite_code = "a1b2c3d4"
            await session.commit()
        for sent in ("a1b2c3d4", "A1B2C3D4"):
            res = await client.post("/api/v1/learn/learners/resume", json={"code": sent})
            assert res.status_code == 200, res.text
            assert res.json()["learner_id"] == joined["learner_id"]


@pytest.mark.asyncio
async def test_join_existing_creates_no_second_learner(state, db_session_factory):
    async with _client() as client:
        ctx = await _teacher_setup(client, state)
        joined = await _join(client, ctx["invite"], "Ann")
        before = await _learner_count(db_session_factory)
        res = await client.post(
            "/api/v1/learn/classes/join-existing",
            json={"invite_code": ctx["invite"]},
            headers=_h(joined["token"]),
        )
        assert res.status_code == 200, res.text
        assert res.json()["class_id"] == joined["class_id"]
        assert res.json()["learner_id"] == joined["learner_id"]
        assert await _learner_count(db_session_factory) == before
        item = await _first_instance(client, joined)
        assert item["assignment_id"] == ctx["assignment_id"]


@pytest.mark.asyncio
async def test_join_existing_requires_session_and_valid_invite(state):
    async with _client() as client:
        ctx = await _teacher_setup(client, state)
        joined = await _join(client, ctx["invite"], "Ann")
        no_session = await client.post(
            "/api/v1/learn/classes/join-existing", json={"invite_code": ctx["invite"]}
        )
        assert no_session.status_code == 401
        bad_invite = await client.post(
            "/api/v1/learn/classes/join-existing",
            json={"invite_code": "nope"},
            headers=_h(joined["token"]),
        )
        assert bad_invite.status_code == 404
