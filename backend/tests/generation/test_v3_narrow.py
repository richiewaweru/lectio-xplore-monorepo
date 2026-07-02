from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from app import app
from core.events import TraceClosedEvent, TraceRegisteredEvent
from core.auth.middleware import get_current_user
from core.entities.user import User
from generation.v3_studio.router import V3SubtopicCandidate

TEST_USER = User(
    id="narrow-test-user", email="test@lectio.app", name="Test",
    picture_url=None, has_profile=True,
    created_at="2026-05-18T00:00:00+00:00",
    updated_at="2026-05-18T00:00:00+00:00",
)

PAYLOAD = {
    "topic": "Reproduction in plants",
    "grade_level": "Grade 6",
    "subject": "Biology",
}


def _client():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _mock_candidates():
    return [
        V3SubtopicCandidate(id="seed-dispersal", title="Seed dispersal",
            description="How plants spread seeds."),
        V3SubtopicCandidate(id="pollination", title="Pollination",
            description="Role of insects in fertilisation."),
        V3SubtopicCandidate(id="flower-structure", title="Flower structure",
            description="Parts of a flower and their functions."),
    ]


@pytest.mark.asyncio
async def test_narrow_returns_candidates():
    with patch("generation.v3_studio.router.run_llm",
        new=AsyncMock(return_value=type("R", (), {
            "output": type("E", (), {"candidates": _mock_candidates()})()
        })())):
        async with _client() as client:
            resp = await client.post("/api/v1/v3/narrow", json=PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["candidates"]) == 3
    assert body["candidates"][0]["title"] == "Seed dispersal"
    assert body["candidates"][0]["id"] == "seed-dispersal"


@pytest.mark.asyncio
async def test_narrow_requires_auth():
    app.dependency_overrides.clear()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/v3/narrow", json=PAYLOAD)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_narrow_returns_empty_on_llm_failure():
    with patch("generation.v3_studio.router.run_llm",
        new=AsyncMock(side_effect=RuntimeError("LLM down"))):
        async with _client() as client:
            resp = await client.post("/api/v1/v3/narrow", json=PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["candidates"] == []


@pytest.mark.asyncio
async def test_narrow_registers_and_closes_trace_for_telemetry():
    published: list[tuple[str, object]] = []

    def capture(trace_id: str, event: object) -> None:
        published.append((trace_id, event))

    with (
        patch("generation.v3_studio.router.event_bus.publish", side_effect=capture),
        patch(
            "generation.v3_studio.router.run_llm",
            new=AsyncMock(
                return_value=type(
                    "R",
                    (),
                    {"output": type("E", (), {"candidates": _mock_candidates()})()},
                )()
            ),
        ),
    ):
        async with _client() as client:
            resp = await client.post("/api/v1/v3/narrow", json=PAYLOAD)

    assert resp.status_code == 200
    assert len(published) == 2
    trace_id, registered = published[0]
    closed_trace_id, closed = published[1]
    assert trace_id == closed_trace_id
    assert isinstance(registered, TraceRegisteredEvent)
    assert registered.user_id == TEST_USER.id
    assert registered.source == "planning"
    assert isinstance(closed, TraceClosedEvent)
    assert closed.source == "planning"


@pytest.mark.asyncio
async def test_narrow_rejects_missing_topic():
    async with _client() as client:
        resp = await client.post("/api/v1/v3/narrow",
            json={"grade_level": "Grade 6", "subject": "Biology"})
    assert resp.status_code == 422
