from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.dependencies import get_async_session
from core.entities.user import User

EDITABLE_PROMPT_ID = "section-writer"
LOCKED_PROMPT_ID = "quiz-items"


def _now() -> datetime:
    return datetime.now(timezone.utc)


TEST_USER = User(
    id="prompt-route-user",
    email="prompt-route@example.com",
    name="Prompt Route Teacher",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)


async def _override_user() -> User:
    return TEST_USER


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _install_session_override(db_session_factory):
    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_async_session] = override_session
    yield


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_list_prompts_includes_manifest_entries_with_modified_flag():
    async with await _client() as client:
        response = await client.get("/api/v1/prompts")

    assert response.status_code == 200
    payload = {item["id"]: item for item in response.json()}
    assert EDITABLE_PROMPT_ID in payload
    assert LOCKED_PROMPT_ID in payload
    assert payload[EDITABLE_PROMPT_ID]["editable"] is True
    assert payload[EDITABLE_PROMPT_ID]["modified"] is False
    assert payload[LOCKED_PROMPT_ID]["editable"] is False


async def test_get_prompt_returns_default_text_and_version():
    async with await _client() as client:
        response = await client.get(f"/api/v1/prompts/{EDITABLE_PROMPT_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == EDITABLE_PROMPT_ID
    assert body["modified"] is False
    assert body["editable"] is True
    assert isinstance(body["text"], str) and body["text"]
    assert isinstance(body["version"], int)


async def test_get_unknown_prompt_returns_404():
    async with await _client() as client:
        response = await client.get("/api/v1/prompts/not-a-real-prompt")

    assert response.status_code == 404


async def test_put_then_delete_round_trips_overlay():
    async with await _client() as client:
        default_response = await client.get(f"/api/v1/prompts/{EDITABLE_PROMPT_ID}")
        default_text = default_response.json()["text"]

        put_response = await client.put(
            f"/api/v1/prompts/{EDITABLE_PROMPT_ID}",
            json={"text": "My custom teacher instructions."},
        )
        assert put_response.status_code == 200
        put_body = put_response.json()
        assert put_body["text"] == "My custom teacher instructions."
        assert put_body["modified"] is True

        get_after_put = await client.get(f"/api/v1/prompts/{EDITABLE_PROMPT_ID}")
        assert get_after_put.json()["text"] == "My custom teacher instructions."
        assert get_after_put.json()["modified"] is True

        delete_response = await client.delete(f"/api/v1/prompts/{EDITABLE_PROMPT_ID}")
        assert delete_response.status_code == 200
        deleted_body = delete_response.json()
        assert deleted_body["modified"] is False
        assert deleted_body["text"] == default_text

        get_after_delete = await client.get(f"/api/v1/prompts/{EDITABLE_PROMPT_ID}")
        assert get_after_delete.json()["modified"] is False
        assert get_after_delete.json()["text"] == default_text


async def test_put_on_locked_prompt_is_rejected():
    async with await _client() as client:
        response = await client.put(
            f"/api/v1/prompts/{LOCKED_PROMPT_ID}",
            json={"text": "trying to override a locked prompt"},
        )

    assert 400 <= response.status_code < 500
    get_response_body = None
    async with await _client() as client:
        get_response = await client.get(f"/api/v1/prompts/{LOCKED_PROMPT_ID}")
        get_response_body = get_response.json()
    assert get_response_body["modified"] is False


async def test_put_on_unknown_prompt_returns_404():
    async with await _client() as client:
        response = await client.put(
            "/api/v1/prompts/not-a-real-prompt",
            json={"text": "anything"},
        )

    assert response.status_code == 404
