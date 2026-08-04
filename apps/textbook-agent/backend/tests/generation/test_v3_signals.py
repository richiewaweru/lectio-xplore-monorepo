from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import PromptedOutput

from app import app
from core.auth.middleware import get_current_user
from core.entities.user import User
from core.events import TraceClosedEvent, TraceRegisteredEvent
from core.llm import ModelFamily, ModelSpec
from generation.v3_studio.agents import extract_signals

TEST_USER = User(
    id="signals-test-user",
    email="signals@lectio.app",
    name="Signals Test",
    picture_url=None,
    has_profile=True,
    created_at="2026-05-18T00:00:00+00:00",
    updated_at="2026-05-18T00:00:00+00:00",
)

PAYLOAD = {
    "grade_level": "Grade 4",
    "subject": "Science",
    "duration_minutes": 50,
    "resource_type": "lesson",
    "topic": "Seeds, Pollination",
    "subtopics": [],
    "prior_knowledge": "",
    "outcome": "Students can explain how pollination helps plants make seeds.",
    "struggle": "They may confuse pollination with seed dispersal.",
    "learner_level": "on_grade",
    "reading_level": "on_grade",
    "language_support": "none",
    "prior_knowledge_level": "new_topic",
    "free_text": "",
}


def _client():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_signals_registers_and_closes_trace_for_telemetry():
    published: list[tuple[str, object]] = []

    def capture(trace_id: str, event: object) -> None:
        published.append((trace_id, event))

    fake_summary = {
        "topic": "Seeds, Pollination",
        "subtopic": "Pollination",
        "prior_knowledge": ["Parts of a flower"],
        "learner_needs": ["Keep pollination separate from seed dispersal"],
        "teacher_goal": "Teach how pollination supports seed formation.",
        "inferred_lesson_mode": "first_exposure",
        "lesson_mode_confidence": "high",
    }

    with (
        patch("generation.v3_studio.router.event_bus.publish", side_effect=capture),
        patch(
            "generation.v3_studio.router.extract_signals",
            new=AsyncMock(return_value=fake_summary),
        ),
    ):
        async with _client() as client:
            resp = await client.post("/api/v1/v3/signals", json=PAYLOAD)

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
async def test_extract_signals_uses_prompted_output_for_deepseek_models() -> None:
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_result = type("R", (), {"output": type("S", (), {"topic": "Seeds, Pollination"})()})()

    with (
        patch("generation.v3_studio.agents.Agent", FakeAgent),
        patch("generation.v3_studio.agents.get_v3_model", return_value="deepseek-model"),
        patch(
            "generation.v3_studio.agents.get_v3_spec",
            return_value=ModelSpec(
                family=ModelFamily.OPENAI_COMPATIBLE,
                model_name="deepseek-v4-flash",
                base_url="https://api.deepseek.com",
                api_key_env="DEEPSEEK_API_KEY",
            ),
        ),
        patch("generation.v3_studio.agents.get_v3_slot", return_value="fast"),
        patch("generation.v3_studio.agents.run_llm", new=AsyncMock(return_value=fake_result)),
    ):
        with pytest.raises(RuntimeError, match="unexpected output"):
            await extract_signals(type("Form", (), PAYLOAD)(), trace_id="signals-trace")

    assert isinstance(captured["output_type"], PromptedOutput)
