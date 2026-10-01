from __future__ import annotations

from types import SimpleNamespace

import pytest

import app as app_module


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("workers_enabled", [True, False])
async def test_lifespan_registers_and_stops_shared_document_worker(
    monkeypatch, workers_enabled
) -> None:
    events: list[str] = []
    monkeypatch.setattr(app_module.settings, "xplore_native_worker_enabled", workers_enabled)
    monkeypatch.setattr(app_module.settings, "run_migrations_on_startup", False)
    monkeypatch.setattr(app_module, "configure_logging", lambda **_kwargs: None)
    monkeypatch.setattr(app_module, "initialize_resource_registry", lambda: None)
    monkeypatch.setattr(app_module, "initialize_skeleton_catalog", lambda: None)
    monkeypatch.setattr(app_module, "cleanup_stale_pdf_exports", lambda **_kwargs: 0)
    monkeypatch.setattr(app_module, "async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr(
        app_module, "engine", SimpleNamespace(dispose=_event(events, "engine_dispose"))
    )
    monkeypatch.setattr(app_module.telemetry_monitor, "configure", lambda **_kwargs: None)
    monkeypatch.setattr(app_module.telemetry_monitor, "start", _async_result(None))
    monkeypatch.setattr(app_module.telemetry_monitor, "stop", _async_result(None))

    import application.unit_lesson.realization_worker as realization_worker
    import application.unit_lesson.preparation_worker as preparation_worker
    import document.shared_lesson.worker as shared_worker

    class PreparationWorkerStub:
        def __init__(self, factory):
            assert factory is not None

        async def start(self):
            events.append("preparation_start")

        async def stop(self):
            events.append("preparation_stop")
            raise RuntimeError("simulated stop failure")

    monkeypatch.setattr(preparation_worker, "PreparationWorker", PreparationWorkerStub)

    class SharedWorker:
        def __init__(self, factory):
            assert factory is not None

        async def start(self):
            events.append("shared_start")

        async def stop(self):
            events.append("shared_stop")

    monkeypatch.setattr(shared_worker, "SharedDocumentWorker", SharedWorker)

    class RealizationWorkerStub:
        def __init__(self, factory):
            assert factory is not None

        async def start(self):
            events.append("realization_start")

        async def stop(self):
            events.append("realization_stop")

    monkeypatch.setattr(realization_worker, "RealizationWorker", RealizationWorkerStub)

    async with app_module.lifespan(app_module.FastAPI()):
        events.append("yield")

    assert ("shared_start" in events) is workers_enabled
    assert ("shared_stop" in events) is workers_enabled
    assert ("realization_start" in events) is workers_enabled
    assert ("realization_stop" in events) is workers_enabled
    assert ("preparation_start" in events) is workers_enabled
    assert ("preparation_stop" in events) is workers_enabled
    if workers_enabled:
        assert events.index("shared_stop") > events.index("yield")
        assert events.index("shared_stop") < events.index("engine_dispose")
    else:
        assert events == ["yield", "engine_dispose"]


def _event(events: list[str], event: str):
    async def record(**_kwargs):
        events.append(event)

    return record


def _async_result(value):
    async def result(*_args, **_kwargs):
        return value

    return result


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


