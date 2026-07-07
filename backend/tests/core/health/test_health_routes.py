from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import create_app
from core.database.models import GenerationModel, UserModel
from core.health import routes as health_routes
from core.health.routes import DependencyStatus, GenerationSummary


def _dependency_by_name(payload: dict, name: str) -> dict:
    return next(dep for dep in payload["dependencies"] if dep["name"] == name)


class TestHealthRoutes:
    def test_liveness_always_200(self):
        with TestClient(create_app()) as client:
            response = client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["timestamp"]
        assert payload["instance_id"]
        assert payload["started_at"]
        assert payload["pipeline_architecture"] == "shell-pipeline-native-lectio"

    def test_health_endpoints_require_no_auth(self):
        with TestClient(create_app()) as client:
            for path in ("/health", "/health/deep", "/health/ready"):
                response = client.get(path)
                assert response.status_code != 401, f"{path} returned 401"

    def test_liveness_keeps_security_headers(self):
        with TestClient(create_app()) as client:
            response = client.get("/health")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        csp = response.headers["Content-Security-Policy"]
        assert "img-src 'self' data:" in csp
        assert "https://storage.googleapis.com" in csp

    def test_deep_and_ready_share_health_shape_when_healthy(self, monkeypatch):
        app = create_app()

        async def fake_database() -> DependencyStatus:
            return DependencyStatus(name="postgres", status="ok", latency_ms=4.2)

        async def fake_event_bus() -> DependencyStatus:
            return DependencyStatus(name="event_bus", status="ok")

        async def fake_summary() -> GenerationSummary:
            return GenerationSummary(
                running=2,
                pending=1,
                failed_last_hour=3,
                completed_last_hour=5,
            )

        async def fake_playwright() -> DependencyStatus:
            return DependencyStatus(name="playwright", status="ok", latency_ms=6.2)

        async def fake_temp_dir() -> DependencyStatus:
            return DependencyStatus(name="pdf_temp_dir", status="ok", latency_ms=1.1)

        async def fake_gemini_image() -> DependencyStatus:
            return DependencyStatus(name="gemini_image", status="ok", latency_ms=5.5, detail="model=test")

        async def fake_image_store() -> DependencyStatus:
            return DependencyStatus(name="image_store", status="ok", latency_ms=3.3, detail="local")

        monkeypatch.setattr(health_routes, "_check_database", fake_database)
        monkeypatch.setattr(health_routes, "_check_event_bus", fake_event_bus)
        monkeypatch.setattr(health_routes, "_check_playwright_runtime", fake_playwright)
        monkeypatch.setattr(health_routes, "_check_pdf_temp_dir", fake_temp_dir)
        monkeypatch.setattr(health_routes, "_get_generation_summary", fake_summary)
        health_routes.configure_health_extensions(
            readiness_checks=[fake_gemini_image, fake_image_store],
        )

        with TestClient(app) as client:
            deep_response = client.get("/health/deep")
            ready_response = client.get("/health/ready")

        assert deep_response.status_code == 200
        assert ready_response.status_code == 200
        deep_payload = deep_response.json()
        ready_payload = ready_response.json()
        assert deep_payload["status"] == "ok"
        assert ready_payload["status"] == "ok"
        assert deep_payload["version"] == ready_payload["version"]
        assert deep_payload["instance_id"] == ready_payload["instance_id"]
        assert deep_payload["dependencies"] == ready_payload["dependencies"]
        assert deep_payload["generations"] == ready_payload["generations"]
        assert _dependency_by_name(deep_payload, "gemini_image")["status"] == "ok"
        assert _dependency_by_name(deep_payload, "image_store")["status"] == "ok"
        assert "pdf_exports" in deep_payload
        assert "timestamp" in deep_payload
        assert "timestamp" in ready_payload

    def test_readiness_returns_503_when_database_unreachable(self, monkeypatch):
        async def fake_database() -> DependencyStatus:
            return DependencyStatus(name="postgres", status="unreachable", detail="Connection refused")

        async def fake_event_bus() -> DependencyStatus:
            return DependencyStatus(name="event_bus", status="ok")

        async def fake_summary() -> GenerationSummary:
            return GenerationSummary(
                running=0,
                pending=0,
                failed_last_hour=0,
                completed_last_hour=0,
            )

        async def fake_playwright() -> DependencyStatus:
            return DependencyStatus(name="playwright", status="ok")

        async def fake_temp_dir() -> DependencyStatus:
            return DependencyStatus(name="pdf_temp_dir", status="ok")

        async def fake_gemini_image() -> DependencyStatus:
            return DependencyStatus(name="gemini_image", status="ok", detail="model=test")

        async def fake_image_store() -> DependencyStatus:
            return DependencyStatus(name="image_store", status="ok", detail="local")

        monkeypatch.setattr(health_routes, "_check_database", fake_database)
        monkeypatch.setattr(health_routes, "_check_event_bus", fake_event_bus)
        monkeypatch.setattr(health_routes, "_check_playwright_runtime", fake_playwright)
        monkeypatch.setattr(health_routes, "_check_pdf_temp_dir", fake_temp_dir)
        monkeypatch.setattr(health_routes, "_get_generation_summary", fake_summary)
        health_routes.configure_health_extensions(
            readiness_checks=[fake_gemini_image, fake_image_store],
        )

        with TestClient(create_app()) as client:
            response = client.get("/health/ready")

        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "unavailable"
        postgres = _dependency_by_name(payload, "postgres")
        assert postgres["status"] == "unreachable"
        assert postgres["detail"] == "Connection refused"

    def test_readiness_returns_200_when_event_bus_is_degraded(self, monkeypatch):
        async def fake_database() -> DependencyStatus:
            return DependencyStatus(name="postgres", status="ok", latency_ms=2.4)

        async def fake_event_bus() -> DependencyStatus:
            return DependencyStatus(name="event_bus", status="degraded", detail="probe timeout")

        async def fake_summary() -> GenerationSummary:
            return GenerationSummary(
                running=1,
                pending=2,
                failed_last_hour=0,
                completed_last_hour=4,
            )

        async def fake_playwright() -> DependencyStatus:
            return DependencyStatus(name="playwright", status="degraded", detail="missing browser")

        async def fake_temp_dir() -> DependencyStatus:
            return DependencyStatus(name="pdf_temp_dir", status="ok")

        async def fake_gemini_image() -> DependencyStatus:
            return DependencyStatus(name="gemini_image", status="ok", detail="model=test")

        async def fake_image_store() -> DependencyStatus:
            return DependencyStatus(name="image_store", status="ok", detail="local")

        monkeypatch.setattr(health_routes, "_check_database", fake_database)
        monkeypatch.setattr(health_routes, "_check_event_bus", fake_event_bus)
        monkeypatch.setattr(health_routes, "_check_playwright_runtime", fake_playwright)
        monkeypatch.setattr(health_routes, "_check_pdf_temp_dir", fake_temp_dir)
        monkeypatch.setattr(health_routes, "_get_generation_summary", fake_summary)
        health_routes.configure_health_extensions(
            readiness_checks=[fake_gemini_image, fake_image_store],
        )

        with TestClient(create_app()) as client:
            response = client.get("/health/ready")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "degraded"
        event_bus = _dependency_by_name(payload, "event_bus")
        assert event_bus["status"] == "degraded"
        assert event_bus["detail"] == "probe timeout"
        playwright = _dependency_by_name(payload, "playwright")
        assert playwright["status"] == "degraded"

    def test_readiness_returns_degraded_when_image_dependencies_are_not_ready(self, monkeypatch):
        app = create_app()

        async def fake_database() -> DependencyStatus:
            return DependencyStatus(name="postgres", status="ok", latency_ms=2.4)

        async def fake_event_bus() -> DependencyStatus:
            return DependencyStatus(name="event_bus", status="ok")

        async def fake_summary() -> GenerationSummary:
            return GenerationSummary(
                running=1,
                pending=0,
                failed_last_hour=0,
                completed_last_hour=2,
            )

        async def fake_playwright() -> DependencyStatus:
            return DependencyStatus(name="playwright", status="ok")

        async def fake_temp_dir() -> DependencyStatus:
            return DependencyStatus(name="pdf_temp_dir", status="ok")

        async def fake_gemini_image() -> DependencyStatus:
            return DependencyStatus(
                name="gemini_image",
                status="degraded",
                detail="Missing GOOGLE_CLOUD_NANO_API_KEY.",
            )

        async def fake_image_store() -> DependencyStatus:
            return DependencyStatus(
                name="image_store",
                status="degraded",
                detail="GCS bucket is not accessible",
            )

        monkeypatch.setattr(health_routes, "_check_database", fake_database)
        monkeypatch.setattr(health_routes, "_check_event_bus", fake_event_bus)
        monkeypatch.setattr(health_routes, "_check_playwright_runtime", fake_playwright)
        monkeypatch.setattr(health_routes, "_check_pdf_temp_dir", fake_temp_dir)
        monkeypatch.setattr(health_routes, "_get_generation_summary", fake_summary)
        health_routes.configure_health_extensions(
            readiness_checks=[fake_gemini_image, fake_image_store],
        )

        with TestClient(app) as client:
            response = client.get("/health/ready")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "degraded"
        assert _dependency_by_name(payload, "gemini_image")["status"] == "degraded"
        assert _dependency_by_name(payload, "image_store")["status"] == "degraded"

    def test_readiness_includes_generation_summary(self, monkeypatch):
        async def fake_database() -> DependencyStatus:
            return DependencyStatus(name="postgres", status="ok", latency_ms=1.0)

        async def fake_event_bus() -> DependencyStatus:
            return DependencyStatus(name="event_bus", status="ok")

        async def fake_summary() -> GenerationSummary:
            return GenerationSummary(
                running=3,
                pending=4,
                failed_last_hour=1,
                completed_last_hour=6,
            )

        async def fake_playwright() -> DependencyStatus:
            return DependencyStatus(name="playwright", status="ok")

        async def fake_temp_dir() -> DependencyStatus:
            return DependencyStatus(name="pdf_temp_dir", status="ok")

        async def fake_gemini_image() -> DependencyStatus:
            return DependencyStatus(name="gemini_image", status="ok", detail="model=test")

        async def fake_image_store() -> DependencyStatus:
            return DependencyStatus(name="image_store", status="ok", detail="local")

        monkeypatch.setattr(health_routes, "_check_database", fake_database)
        monkeypatch.setattr(health_routes, "_check_event_bus", fake_event_bus)
        monkeypatch.setattr(health_routes, "_check_playwright_runtime", fake_playwright)
        monkeypatch.setattr(health_routes, "_check_pdf_temp_dir", fake_temp_dir)
        monkeypatch.setattr(health_routes, "_get_generation_summary", fake_summary)
        health_routes.configure_health_extensions(
            readiness_checks=[fake_gemini_image, fake_image_store],
        )

        with TestClient(create_app()) as client:
            response = client.get("/health/deep")

        assert response.status_code == 200
        payload = response.json()
        assert payload["generations"] == {
            "running": 3,
            "pending": 4,
            "failed_last_hour": 1,
            "completed_last_hour": 6,
        }
        assert payload["pdf_exports"]["total_exports"] >= 0

    def test_image_probe_returns_200_when_probe_succeeds(self):
        app = create_app()

        async def fake_runner():
            return (
                [
                    DependencyStatus(name="gemini_image_probe", status="ok", detail="model=test"),
                    DependencyStatus(name="image_store_probe", status="ok", detail="local"),
                ],
                4096,
            )

        health_routes.configure_health_extensions(
            image_probe_runner=fake_runner,
        )

        with TestClient(app) as client:
            response = client.post("/health/image/probe")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["probe_image_bytes"] == 4096

    def test_image_probe_returns_503_when_probe_fails(self):
        app = create_app()

        async def fake_runner():
            return (
                [
                    DependencyStatus(
                        name="gemini_image_probe",
                        status="unreachable",
                        detail="TimeoutError: probe timed out",
                    ),
                    DependencyStatus(
                        name="image_store_probe",
                        status="ok",
                        detail="local",
                    ),
                ],
                None,
            )

        health_routes.configure_health_extensions(
            image_probe_runner=fake_runner,
        )

        with TestClient(app) as client:
            response = client.post("/health/image/probe")

        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "unavailable"
        assert _dependency_by_name(payload, "gemini_image_probe")["status"] == "unreachable"

    async def test_generation_summary_counts_rows_from_database(self, db_session):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add(
            UserModel(
                id="user-1",
                email="health@example.com",
                name="Health User",
            )
        )
        db_session.add_all(
            [
                GenerationModel(
                    id="health-running",
                    user_id="user-1",
                    subject="math",
                    context="",
                    status="running",
                    requested_template_id="guided-concept-path",
                    requested_preset_id="blue-classroom",
                    created_at=now,
                ),
                GenerationModel(
                    id="health-pending",
                    user_id="user-1",
                    subject="math",
                    context="",
                    status="pending",
                    requested_template_id="guided-concept-path",
                    requested_preset_id="blue-classroom",
                    created_at=now,
                ),
                GenerationModel(
                    id="health-failed-recent",
                    user_id="user-1",
                    subject="math",
                    context="",
                    status="failed",
                    requested_template_id="guided-concept-path",
                    requested_preset_id="blue-classroom",
                    created_at=now - timedelta(minutes=30),
                    completed_at=now - timedelta(minutes=10),
                ),
                GenerationModel(
                    id="health-completed-recent",
                    user_id="user-1",
                    subject="math",
                    context="",
                    status="completed",
                    requested_template_id="guided-concept-path",
                    requested_preset_id="blue-classroom",
                    created_at=now - timedelta(minutes=40),
                    completed_at=now - timedelta(minutes=5),
                ),
                GenerationModel(
                    id="health-failed-old",
                    user_id="user-1",
                    subject="math",
                    context="",
                    status="failed",
                    requested_template_id="guided-concept-path",
                    requested_preset_id="blue-classroom",
                    created_at=now - timedelta(hours=3),
                    completed_at=now - timedelta(hours=2),
                ),
            ]
        )
        await db_session.commit()

        @asynccontextmanager
        async def fake_session_factory():
            yield db_session

        original_session_factory = health_routes.async_session_factory
        health_routes.async_session_factory = fake_session_factory
        try:
            summary = await health_routes._get_generation_summary()
        finally:
            health_routes.async_session_factory = original_session_factory

        assert summary is not None
        assert summary.running == 1
        assert summary.pending == 1
        assert summary.failed_last_hour == 1
        assert summary.completed_last_hour == 1
