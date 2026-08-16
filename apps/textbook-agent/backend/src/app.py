import asyncio
import inspect
import logging
import os
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
from core.health.routes import (
    DependencyStatus,
    configure_health_extensions,
    router as health_router,
)
from core.logging import configure_logging
from core.middleware.request_id import RequestIdMiddleware
from core.middleware.v2_audit import V2AuditMiddleware
from core.pdf_export_runtime import cleanup_stale_pdf_exports
from core.routes.auth import router as auth_router
from core.routes.capabilities import router as capabilities_router
from core.routes.profile import router as profile_router
from core.routes.prompts import router as prompts_router
from core.routes.shares import router as shares_router
from core.version import VERSION
from builder.routes import router as builder_router
from core.database.session import async_session_factory
from generation.routes import router as generation_router
from generation.skeleton_routes import router as skeleton_router
from generation.v3_studio.generation_writer import V3GenerationWriter
from learning.routes import router as learning_router
from media.diagnostics.v3_image_pipeline_diagnostic import (
    ProbeResult,
    run_gcs_probe,
    run_grok_probe,
)
from planning.routes import router as planning_router
from planning.compatibility import router as compatibility_router
from resource_specs.loader import initialize_registry as initialize_resource_registry
from telemetry import telemetry_router
from telemetry.dependencies import get_llm_call_repository
from telemetry.service import telemetry_monitor
from v3_blueprint.skeletons import initialize_skeleton_catalog

logger = logging.getLogger("uvicorn.error")
__version__ = VERSION
_PRODUCTION_LIKE_ENVS = {"production", "staging"}
_IMAGES_DIR = Path("data/images")
_IMAGE_PROBE_CACHE_TTL_SECONDS = 600
_FALLBACK_PROBE_IMAGE = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdacd\xfc"
    b"\xff\x1f\x00\x02\xeb\x01\xf5i\xd5u\xd7\x00\x00\x00\x00IEND\xaeB`\x82"
)
_image_probe_cache: tuple[float, tuple[list[DependencyStatus], int | None]] | None = None


def _csp_img_src_hosts() -> str:
    hosts = ["https://storage.googleapis.com"]
    configured_base_url = os.getenv("GCS_IMAGE_BASE_URL", "").strip()
    if configured_base_url:
        parsed = urlsplit(configured_base_url)
        if parsed.scheme and parsed.netloc:
            host = f"{parsed.scheme}://{parsed.netloc}"
            if host not in hosts:
                hosts.append(host)
    return " ".join(hosts)


def _probe_dependency(
    result: ProbeResult,
    *,
    provider: str | None,
    model: str | None,
) -> DependencyStatus:
    details = {
        key: value
        for key, value in result.details.items()
        if key not in {"final_url", "image_bytes"}
    }
    detail_parts = [
        f"provider={provider or details.get('provider') or 'unknown'}",
        f"model={model or details.get('model') or 'unknown'}",
    ]
    if result.stage:
        detail_parts.append(f"stage={result.stage}")
    if result.error:
        detail_parts.append(f"error={result.error}")
    return DependencyStatus(
        name=result.name,
        status="ok" if result.ok else "unreachable",
        detail="; ".join(detail_parts),
    )


async def _run_cached_image_probe() -> tuple[list[DependencyStatus], int | None]:
    global _image_probe_cache
    now = asyncio.get_running_loop().time()
    if _image_probe_cache is not None:
        cached_at, cached_result = _image_probe_cache
        if now - cached_at < _IMAGE_PROBE_CACHE_TTL_SECONDS:
            return cached_result

    grok_probe = await run_grok_probe()
    provider = str(grok_probe.details.get("provider") or "xai")
    model = str(grok_probe.details.get("model") or "grok-imagine-image")
    image_bytes = grok_probe.details.get("image_bytes")
    upload_bytes = image_bytes if isinstance(image_bytes, bytes) and image_bytes else _FALLBACK_PROBE_IMAGE
    upload_source = "grok_probe" if isinstance(image_bytes, bytes) and image_bytes else "embedded_fallback_png"
    gcs_probe = await run_gcs_probe(upload_bytes, upload_source)

    result = (
        [
            _probe_dependency(grok_probe, provider=provider, model=model),
            _probe_dependency(gcs_probe, provider=provider, model=model),
        ],
        len(upload_bytes) if grok_probe.ok else None,
    )
    _image_probe_cache = (now, result)
    return result



class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://accounts.google.com; "
            "connect-src 'self' https://accounts.google.com; "
            f"img-src 'self' data: {_csp_img_src_hosts()}; "
            "frame-src https://accounts.google.com; "
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
    try:
        stale_generations = await V3GenerationWriter(async_session_factory).fail_stale_running()
        if stale_generations:
            logger.warning(
                "Reconciled %d stale v3 generation(s) after restart",
                stale_generations,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Stale v3 generation sweep failed at startup")
    initialize_resource_registry()
    initialize_skeleton_catalog()
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
    if settings.xplore_native_worker_enabled:
        from planning.whole_lesson.worker import start_native_worker

        await start_native_worker()
    yield
    if settings.xplore_native_worker_enabled:
        from planning.whole_lesson.worker import stop_native_worker

        await stop_native_worker(drain_seconds=5.0)
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
    configure_health_extensions(image_probe_runner=_run_cached_image_probe)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    allowed_origins = _allowed_frontend_origins(
        settings.frontend_origin,
        env=settings.app_env,
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(V2AuditMiddleware)
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
    app.include_router(capabilities_router)
    app.include_router(builder_router)
    app.include_router(shares_router)
    app.include_router(profile_router)
    app.include_router(prompts_router)
    app.include_router(learning_router)
    app.include_router(generation_router)
    app.include_router(skeleton_router)
    app.include_router(planning_router)
    app.include_router(compatibility_router)
    app.include_router(telemetry_router)

    return app


app = create_app()
