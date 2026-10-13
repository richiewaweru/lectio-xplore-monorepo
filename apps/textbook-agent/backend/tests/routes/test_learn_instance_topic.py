"""Doc 38 3.6: GET /learn/instances/{id} carries a `topic` object for linked releases."""

from __future__ import annotations

import pytest

from tests.routes.test_learn_topics import (  # noqa: F401  (autouse fixtures + helpers)
    _client,
    _h,
    _join,
    _overrides,
    _publish,
    _seed,
    _setup,
    _topics,
)


async def _instance(client, joined, instance_id):
    res = await client.get(
        f"/api/v1/learn/instances/{instance_id}", headers=_h(joined["token"])
    )
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_linked_instance_has_topic_with_ready_and_pending_next(
    _overrides, db_session_factory
):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory)  # 4 ready + 1 pending
        joined = await _join(client, ctx["invite"])
        lessons = (await _topics(client, joined))["topics"][0]["lessons"]

        first = await _instance(client, joined, lessons[0]["instance_id"])
        assert first["topic"] == {
            "unit_id": "unit-1",
            "title": "Photosynthesis",
            "lesson_position": 1,
            "lessons_total": 5,
            "next_lesson": {
                "state": "ready",
                "title": "Path lesson 2",
                "instance_id": lessons[1]["instance_id"],
            },
        }

        fourth = await _instance(client, joined, lessons[3]["instance_id"])
        assert fourth["topic"]["lesson_position"] == 4
        assert fourth["topic"]["next_lesson"] == {
            "state": "pending",
            "title": "Path lesson 5",
            "instance_id": None,
        }


@pytest.mark.asyncio
async def test_last_lesson_has_no_next_and_unlinked_has_no_topic(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory, linked=5)
        joined = await _join(client, ctx["invite"])
        body = await _topics(client, joined)
        last = body["topics"][0]["lessons"][4]
        data = await _instance(client, joined, last["instance_id"])
        assert data["topic"]["lesson_position"] == 5
        assert data["topic"]["next_lesson"] == {
            "state": None,
            "title": None,
            "instance_id": None,
        }

        other = await _instance(client, joined, body["other_lessons"][0]["instance_id"])
        assert other["topic"] is None
