from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import PromptedOutput

from app import app
from core.auth.middleware import get_current_user
from core.entities.user import User
from core.events import TraceClosedEvent, TraceRegisteredEvent
from core.llm import ModelFamily, ModelSpec
from generation.v3_studio.dtos import V3ProposeIntentResponse
from v3_execution.llm_helpers import StructuredCallContext

TEST_USER = User(
    id="propose-intent-test-user", email="test@lectio.app", name="Test", picture_url=None,
    has_profile=True, created_at="2026-05-18T00:00:00+00:00", updated_at="2026-05-18T00:00:00+00:00",
)

PAYLOAD = {
    "grade_level": "Grade 6", "subject": "Mathematics", "resource_type": "lesson",
    "duration_minutes": 50, "learner_level": "on_grade", "reading_level": "below_grade",
    "language_support": "some_ell", "prior_knowledge_level": "new_topic",
    "topic": "Finding the area of irregular shapes", "subtopics": ["Decompose into rectangles"],
}


def _client() -> AsyncClient:
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _drafts() -> V3ProposeIntentResponse:
    return V3ProposeIntentResponse(
        outcome_draft="By the end, students can split irregular shapes into rectangles and add their areas.",
        struggle_draft="Students may miss a rectangle when splitting a shape. Short directions and labelled pieces help this class check each part.",
        prior_knowledge_draft="Find the area of a rectangle\nAdd whole numbers",
    )


@pytest.mark.asyncio
async def test_propose_intent_returns_three_teacher_editable_drafts() -> None:
    with patch("generation.v3_studio.router.run_llm", new=AsyncMock(return_value=SimpleNamespace(output=_drafts()))):
        async with _client() as client:
            response = await client.post("/api/v1/v3/propose-intent", json=PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert all(body[key] for key in ("outcome_draft", "struggle_draft", "prior_knowledge_draft"))
    assert body["outcome_draft"].startswith("By the end")


@pytest.mark.asyncio
async def test_propose_intent_scopes_empty_subtopics_to_topic() -> None:
    captured: dict[str, object] = {}

    async def fake_run_llm(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return SimpleNamespace(output=_drafts())

    with patch("generation.v3_studio.router.run_llm", new=fake_run_llm):
        async with _client() as client:
            response = await client.post("/api/v1/v3/propose-intent", json={**PAYLOAD, "subtopics": []})

    assert response.status_code == 200
    assert "(none — use topic as scope)" in str(captured["user_prompt"])
    assert PAYLOAD["topic"] in str(captured["user_prompt"])


@pytest.mark.asyncio
async def test_propose_intent_registers_and_closes_trace() -> None:
    published: list[tuple[str, object]] = []
    with (
        patch("generation.v3_studio.router.event_bus.publish", side_effect=lambda trace_id, event: published.append((trace_id, event))),
        patch("generation.v3_studio.router.run_llm", new=AsyncMock(return_value=SimpleNamespace(output=_drafts()))),
    ):
        async with _client() as client:
            response = await client.post("/api/v1/v3/propose-intent", json=PAYLOAD)

    assert response.status_code == 200
    assert isinstance(published[0][1], TraceRegisteredEvent)
    assert isinstance(published[1][1], TraceClosedEvent)
    assert published[0][0] == published[1][0]


@pytest.mark.asyncio
async def test_propose_intent_requires_auth() -> None:
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/v3/propose-intent", json=PAYLOAD)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_propose_intent_uses_prompted_output_for_deepseek() -> None:
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    with (
        patch("generation.v3_studio.router.Agent", FakeAgent),
        patch(
            "generation.v3_studio.router.prepare_structured_agent",
            return_value=(
                "deepseek-model",
                PromptedOutput(V3ProposeIntentResponse, template="{schema}"),
                StructuredCallContext(
                    structured_mode="prompted_json",
                    schema_source_kind="pydantic",
                    schema_fingerprint="abc",
                    strict_fallback=True,
                ),
                ModelSpec(
                    family=ModelFamily.OPENAI_COMPATIBLE,
                    model_name="deepseek-v4-pro",
                    base_url="https://api.deepseek.com",
                    api_key_env="DEEPSEEK_API_KEY",
                ),
                None,
            ),
        ),
        patch("generation.v3_studio.router.run_llm", new=AsyncMock(return_value=SimpleNamespace(output=_drafts()))),
    ):
        async with _client() as client:
            response = await client.post("/api/v1/v3/propose-intent", json=PAYLOAD)

    assert response.status_code == 200
    assert isinstance(captured["output_type"], PromptedOutput)


@pytest.mark.asyncio
async def test_propose_intent_prompt_conditions_on_class_shape() -> None:
    captured: dict[str, object] = {}

    async def fake_run_llm(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return SimpleNamespace(output=_drafts())

    with patch("generation.v3_studio.router.run_llm", new=fake_run_llm):
        async with _client() as client:
            response = await client.post("/api/v1/v3/propose-intent", json=PAYLOAD)

    assert response.status_code == 200
    prompt = str(captured["user_prompt"])
    assert "Reading level: below_grade" in prompt
    assert "Language support: some_ell" in prompt
