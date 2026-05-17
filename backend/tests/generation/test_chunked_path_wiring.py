from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import UserModel
from core.database.session import async_session_factory
from core.entities.user import User
from v3_blueprint.planning.models import Stage1PlanFailure

TEST_USER = User(
    id="test-wiring-user",
    email="admin@lectio.app",
    name="Test",
    picture_url=None,
    has_profile=True,
    created_at="2026-05-17T00:00:00+00:00",
    updated_at="2026-05-17T00:00:00+00:00",
)

VALID_SIGNALS = {
    "topic": "Fractions",
    "subtopic": "Equivalent fractions",
    "prior_knowledge": ["equal sharing"],
    "learner_needs": [],
    "teacher_goal": "Build understanding",
    "inferred_resource_type": "worksheet",
    "confidence": "medium",
    "missing_signals": [],
}

VALID_FORM = {
    "grade_level": "Grade 5",
    "subject": "Mathematics",
    "duration_minutes": 45,
    "topic": "Equivalent fractions",
    "subtopics": ["pizza model"],
    "prior_knowledge": "Equal sharing",
    "lesson_mode": "first_exposure",
    "lesson_mode_other": "",
    "intended_outcome": "understand",
    "intended_outcome_other": "",
    "learner_level": "on_grade",
    "reading_level": "on_grade",
    "language_support": "none",
    "prior_knowledge_level": "some_background",
    "support_needs": ["visuals"],
    "learning_preferences": [],
    "free_text": "",
}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _override_user() -> User:
    return TEST_USER


async def _ensure_user() -> None:
    async with async_session_factory() as session:
        model = await session.get(UserModel, TEST_USER.id)
        if model is None:
            session.add(
                UserModel(
                    id=TEST_USER.id,
                    email=TEST_USER.email,
                    name=TEST_USER.name,
                    picture_url=TEST_USER.picture_url,
                )
            )
            await session.commit()


def _example_bp(name: str = "amara_compound_area.json"):
    from v3_blueprint.models import ProductionBlueprint

    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / name
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def _payload(*, architect_mode: str | None = None) -> dict:
    payload = {
        "signals": VALID_SIGNALS,
        "form": VALID_FORM,
        "clarification_answers": [],
    }
    if architect_mode is not None:
        payload["architect_mode"] = architect_mode
    return payload


@pytest.fixture(autouse=True)
def _reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_blueprint_standard_path_works_without_architect_mode() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    await _ensure_user()
    bp = _example_bp()

    with patch("generation.v3_studio.router.generate_production_blueprint", return_value=bp):
        async with _client() as client:
            resp = await client.post("/api/v1/v3/blueprint", json=_payload())

    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_blueprint_request_accepts_architect_mode_standard() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    await _ensure_user()
    bp = _example_bp()

    with patch("generation.v3_studio.router.generate_production_blueprint", return_value=bp):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/v3/blueprint",
                json=_payload(architect_mode="standard"),
            )

    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_blueprint_request_accepts_architect_mode_chunked() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    await _ensure_user()
    bp = _example_bp()

    with patch("generation.v3_studio.router.generate_production_blueprint", return_value=bp):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/v3/blueprint",
                json=_payload(architect_mode="chunked"),
            )

    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_architect_mode_is_passed_to_generate_production_blueprint() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    await _ensure_user()
    bp = _example_bp()
    mock_generate = AsyncMock(return_value=bp)

    with patch("generation.v3_studio.router.generate_production_blueprint", mock_generate):
        async with _client() as client:
            await client.post("/api/v1/v3/blueprint", json=_payload(architect_mode="chunked"))

    mock_generate.assert_awaited_once()
    assert mock_generate.await_args.kwargs["architect_mode"] == "chunked"
    assert mock_generate.await_args.kwargs["generation_id"] is None


@pytest.mark.asyncio
async def test_chunked_architect_mode_routes_to_stage1() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    await _ensure_user()
    bp = _example_bp()

    mock_stage1 = AsyncMock(return_value=MagicMock())
    mock_stage2 = AsyncMock(return_value=[])
    mock_assemble = MagicMock(return_value=bp)

    with (
        patch("v3_blueprint.planning.retry.run_stage1_with_retry", mock_stage1),
        patch("v3_blueprint.planning.retry.run_stage2", mock_stage2),
        patch("v3_blueprint.planning.assembler.assemble_blueprint", mock_assemble),
    ):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/v3/blueprint",
                json=_payload(architect_mode="chunked"),
            )

    assert resp.status_code == 200, resp.text
    mock_stage1.assert_awaited_once()


@pytest.mark.asyncio
async def test_stage1_plan_failure_returns_422_with_errors() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    await _ensure_user()

    with patch(
        "generation.v3_studio.router.generate_production_blueprint",
        side_effect=Stage1PlanFailure(
            errors=[
                "Section 'model': unknown slug 'bad-slug'",
                "Section 'practice': duplicate section_field 'explanation'",
            ]
        ),
    ):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/v3/blueprint",
                json=_payload(architect_mode="chunked"),
            )

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["detail"]["error"] == "stage1_plan_failure"
    assert "bad-slug" in str(body["detail"]["errors"])
    assert "duplicate section_field" in str(body["detail"]["errors"])


@pytest.mark.asyncio
async def test_standard_path_unaffected_by_chunked_changes() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    await _ensure_user()

    with patch(
        "generation.v3_studio.router.generate_production_blueprint",
        side_effect=RuntimeError("standard path exploded"),
    ):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/v3/blueprint",
                json=_payload(architect_mode="standard"),
            )

    assert resp.status_code == 500
    assert "RuntimeError" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_architect_mode_rejected() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    await _ensure_user()

    async with _client() as client:
        resp = await client.post(
            "/api/v1/v3/blueprint",
            json=_payload(architect_mode="experimental"),
        )

    assert resp.status_code == 422
