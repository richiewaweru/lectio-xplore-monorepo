from __future__ import annotations

import pytest


import app as app_module


def test_cors_wildcard_raises_in_production() -> None:
    with pytest.raises(RuntimeError, match="FRONTEND_ORIGIN"):
        app_module._allowed_frontend_origins("*", env="production")


def test_cors_wildcard_allowed_in_development(monkeypatch) -> None:
    seen: list[str] = []

    def capture_warning(message: str, *args) -> None:
        seen.append(message % args if args else message)

    monkeypatch.setattr(app_module.logger, "warning", capture_warning)

    origins = app_module._allowed_frontend_origins("*", env="development")

    assert origins == ["*"]
    assert any("CORS is open" in message for message in seen)


def test_cors_multiple_origins_parsed() -> None:
    origins = app_module._allowed_frontend_origins(
        "https://app.vercel.app, https://preview.vercel.app",
        env="production",
    )

    assert origins == [
        "https://app.vercel.app",
        "https://preview.vercel.app",
    ]


def test_cors_localhost_origin_expands_to_local_variants() -> None:
    origins = app_module._allowed_frontend_origins(
        "http://localhost:5173",
        env="development",
    )

    assert origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_images_static_route_is_mounted() -> None:
    image_routes = [
        route for route in app_module.app.routes
        if getattr(route, "path", None) == "/images"
    ]

    assert image_routes, "Expected /images static mount to be registered"
    assert getattr(image_routes[0], "name", None) == "images"


