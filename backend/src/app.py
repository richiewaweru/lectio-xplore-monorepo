import asyncio
import inspect
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.rate_limit import limiter
from core.database.migrations import upgrade_database
from core.database.session import engine
from core.errors import register_error_handlers
from core.health.routes import configure_health_extensions, router as health_router
from core.logging import configure_logging
from core.middleware.request_id import RequestIdMiddleware
from core.pdf_export_runtime import cleanup_stale_pdf_exports
from core.routes.auth import router as auth_router
from core.routes.profile import router as profile_router
from core.routes.shares import router as shares_router
from builder.routes import router as builder_router
from generation.routes import router as generation_router
from learning.pack_spec_loader import initialize_pack_registry
from learning.routes import router as learning_router
from resource_specs.loader import initialize_registry as initialize_resource_registry
from telemetry import telemetry_router
from telemetry.dependencies import get_llm_call_repository
from telemetry.service import telemetry_monitor

logger = logging.getLogger("uvicorn.error")
__version__ = "0.1.0"
_PRODUCTION_LIKE_ENVS = {"production", "staging"}
_IMAGES_DIR = Path("data/images")



class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://accounts.google.com; "
            "frame-src 'none'; "
            "object-src 'none'"
        )
        if settings.app_env in _PRODUCTION_LIKE_ENVS:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


def _allowed_frontend_origins(frontend_origin: str, env: str = "development") -> list[str]:
    if not frontend_origin or frontend_origin.strip() == "*":
        if env in _PRODUCTION_LIKE_ENVS:
            raise RuntimeError(
                "FRONTEND_ORIGIN must be set to a specific domain in production. "
                "A wildcard origin ('*') is not permitted."
            )
        logger.warning(
            "CORS is open to all origins. This is only acceptable in local development."
        )
        return ["*"]

    origins = [origin.strip() for origin in frontend_origin.split(",") if origin.strip()]
    variants: list[str] = []
    for origin in origins:
        parsed = urlsplit(origin)
        hostname = parsed.hostname
        if hostname in {"localhost", "127.0.0.1"}:
            port_suffix = f":{parsed.port}" if parsed.port is not None else ""
            netloc_template = "{host}" + port_suffix
            for host in ("localhost", "127.0.0.1"):
                candidate = urlunsplit(
                    (
                        parsed.scheme,
                        netloc_template.format(host=host),
                        parsed.path,
                        parsed.query,
                        parsed.fragment,
                    )
                )
                if candidate not in variants:
                    variants.append(candidate)
            continue

        if origin not in variants:
            variants.append(origin)
    return variants


async def _resolve_override(app: FastAPI, dependency):
    provider = app.dependency_overrides.get(dependency)
    if provider is None:
        return None

    value = provider()
    if inspect.isasyncgen(value):
        try:
            return await anext(value)
        finally:
            await value.aclose()
    if inspect.isawaitable(value):
        return await value
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(
        json_logs=settings.json_logs,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    async def load_llm_call_repository():
        return await _resolve_override(app, get_llm_call_repository)

    telemetry_monitor.configure(
        llm_call_repository_factory=load_llm_call_repository,
            )
    if settings.run_migrations_on_startup:
        await asyncio.to_thread(upgrade_database)
    initialize_resource_registry()
    initialize_pack_registry()
    await telemetry_monitor.start()
    pdf_temp_cleaned = cleanup_stale_pdf_exports(
        path_value=settings.pdf_temp_dir,
        retention_seconds=settings.pdf_temp_retention_seconds,
    )
    app.state.instance_id = str(uuid4())
    app.state.started_at = datetime.now(timezone.utc)
    app.state.pipeline_architecture = "shell-pipeline-native-lectio"
    logger.info(
        "Runtime ready",
        extra={
            "instance_id": app.state.instance_id,
            "started_at": app.state.started_at.isoformat(),
            "pipeline_architecture": app.state.pipeline_architecture,
            "pdf_temp_cleaned": pdf_temp_cleaned,
        },
    )
    yield
    await telemetry_monitor.stop()
    telemetry_monitor.configure()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Textbook Generation Agent",
        version=__version__,
        description="AI-agnostic pipeline for generating personalized textbooks",
        lifespan=lifespan,
    )
    configure_health_extensions()

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    allowed_origins = _allowed_frontend_origins(
        settings.frontend_origin,
        env=settings.app_env,
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(SecurityHeadersMiddleware)

    register_error_handlers(app)

    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/images", StaticFiles(directory=str(_IMAGES_DIR)), name="images")

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(builder_router)
    app.include_router(shares_router)
    app.include_router(profile_router)
    app.include_router(learning_router)
    app.include_router(generation_router)
    app.include_router(telemetry_router)

    return app


app = create_app()



