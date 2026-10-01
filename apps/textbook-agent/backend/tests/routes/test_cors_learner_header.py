from __future__ import annotations

from fastapi.testclient import TestClient

import app as app_module


def test_preflight_allows_x_learner_session_header() -> None:
    origin = app_module._allowed_frontend_origins(
        app_module.settings.frontend_origin,
        env=app_module.settings.app_env,
    )[0]
    if origin == "*":
        origin = "http://localhost:5173"

    client = TestClient(app_module.app)
    response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-learner-session",
        },
    )

    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "x-learner-session" in allowed
