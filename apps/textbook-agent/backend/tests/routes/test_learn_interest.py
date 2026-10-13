"""Interest capture: public POST, honeypot, rate limit, teacher-only list."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from tests.routes.test_learn_anonymous_learner import (
    _client,
    _h,
    _join,
    _overrides,  # noqa: F401 - fixture
    _seed,  # noqa: F401 - autouse fixture
    _teacher_setup,
)
from tests.routes.test_learn_runtime import TEACHER

from infra.database.models import InterestMessageModel
from infra.rate_limit import limiter

URL = "/api/v1/learn/interest"


@pytest.fixture
def state(_overrides):  # noqa: F811 - reuse the imported fixture by name
    return _overrides


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


async def _count(db_session_factory) -> int:
    async with db_session_factory() as session:
        return await session.scalar(select(func.count()).select_from(InterestMessageModel))


@pytest.mark.asyncio
async def test_saves_with_email_only(state, db_session_factory):
    state["user"] = None
    async with _client() as client:
        res = await client.post(
            URL, json={"message": "Fractions please", "email": "a@b.co", "source": "home"}
        )
        assert res.status_code == 200, res.text
    async with db_session_factory() as session:
        row = await session.scalar(select(InterestMessageModel))
    assert row.email == "a@b.co"
    assert row.phone is None
    assert row.learner_id is None
    assert row.source == "home"


@pytest.mark.asyncio
async def test_saves_with_phone_only(state, db_session_factory):
    state["user"] = None
    async with _client() as client:
        res = await client.post(
            URL, json={"message": "Hi", "phone": "+254 700 123 456", "source": "topic"}
        )
        assert res.status_code == 200, res.text
    assert await _count(db_session_factory) == 1


@pytest.mark.asyncio
async def test_rejects_neither_contact(state, db_session_factory):
    async with _client() as client:
        res = await client.post(URL, json={"message": "Hi"})
        assert res.status_code == 422
    assert await _count(db_session_factory) == 0


@pytest.mark.asyncio
async def test_rejects_bad_email_and_phone(state):
    async with _client() as client:
        assert (await client.post(URL, json={"message": "Hi", "email": "nope"})).status_code == 422
        assert (await client.post(URL, json={"message": "Hi", "phone": "12"})).status_code == 422


@pytest.mark.asyncio
async def test_rejects_empty_message(state, db_session_factory):
    async with _client() as client:
        for msg in ("", "   \n "):
            res = await client.post(URL, json={"message": msg, "email": "a@b.co"})
            assert res.status_code == 422
    assert await _count(db_session_factory) == 0


@pytest.mark.asyncio
async def test_honeypot_returns_ok_without_saving(state, db_session_factory):
    async with _client() as client:
        res = await client.post(
            URL, json={"message": "spam", "email": "a@b.co", "website": "http://spam"}
        )
        assert res.status_code == 200
    assert await _count(db_session_factory) == 0


@pytest.mark.asyncio
async def test_learner_session_adds_attribution(state, db_session_factory):
    async with _client() as client:
        ctx = await _teacher_setup(client, state)
        joined = await _join(client, ctx["invite"], "Ann")
        res = await client.post(
            URL, json={"message": "Hi", "email": "a@b.co"}, headers=_h(joined["token"])
        )
        assert res.status_code == 200, res.text
    async with db_session_factory() as session:
        row = await session.scalar(select(InterestMessageModel))
    assert row.learner_id == joined["learner_id"]
    assert row.display_name == "Ann"


@pytest.mark.asyncio
async def test_post_rate_limited(state):
    async with _client() as client:
        statuses = [
            (await client.post(URL, json={"message": f"m{i}", "email": "a@b.co"})).status_code
            for i in range(7)
        ]
    assert statuses[:5] == [200] * 5
    assert 429 in statuses[5:]


@pytest.mark.asyncio
async def test_teacher_list_returns_rows_newest_first(state):
    async with _client() as client:
        for msg in ("first", "second"):
            res = await client.post(URL, json={"message": msg, "email": "a@b.co"})
            assert res.status_code == 200
        state["user"] = TEACHER
        res = await client.get(URL)
        assert res.status_code == 200, res.text
        rows = res.json()
        assert [r["message"] for r in rows] == ["second", "first"]
        assert rows[0]["email"] == "a@b.co"
        limited = await client.get(URL, params={"limit": 1, "offset": 1})
        assert [r["message"] for r in limited.json()] == ["first"]


@pytest.mark.asyncio
async def test_anonymous_list_is_401(state):
    state["user"] = None
    async with _client() as client:
        res = await client.get(URL)
        assert res.status_code == 401
