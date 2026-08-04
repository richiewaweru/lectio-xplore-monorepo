from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.capabilities import xplore_v2_enabled_for
from core.config import settings
from core.entities.user import User


TEST_USER = User(
    id="beta-user",
    email="beta@example.invalid",
    name="Beta User",
    created_at="2026-08-01T00:00:00+00:00",
    updated_at="2026-08-01T00:00:00+00:00",
)


async def _current_user() -> User:
    return TEST_USER


def test_capability_supports_global_and_principal_scoped_rollout(monkeypatch) -> None:
    monkeypatch.setattr(settings, "xplore_v2_enabled", True)
    monkeypatch.setattr(settings, "xplore_v2_beta_users", "")
    assert xplore_v2_enabled_for(TEST_USER) is True

    monkeypatch.setattr(settings, "xplore_v2_beta_users", "other-user, BETA@EXAMPLE.INVALID")
    assert xplore_v2_enabled_for(TEST_USER) is True

    monkeypatch.setattr(settings, "xplore_v2_beta_users", "other-user")
    assert xplore_v2_enabled_for(TEST_USER) is False

    monkeypatch.setattr(settings, "xplore_v2_enabled", False)
    monkeypatch.setattr(settings, "xplore_v2_beta_users", TEST_USER.id)
    assert xplore_v2_enabled_for(TEST_USER) is False


async def test_rollback_hides_v2_without_disabling_legacy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "xplore_v2_enabled", False)
    monkeypatch.setattr(settings, "xplore_v2_beta_users", "")
    app.dependency_overrides[get_current_user] = _current_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            capabilities = await client.get("/api/v1/capabilities")
            units = await client.get("/api/v1/units")
            legacy = await client.get("/api/v1/packs")
    finally:
        app.dependency_overrides.clear()

    assert capabilities.status_code == 200
    assert capabilities.json() == {"xplore_v2": False}
    assert units.status_code == 404
    assert legacy.status_code == 200

