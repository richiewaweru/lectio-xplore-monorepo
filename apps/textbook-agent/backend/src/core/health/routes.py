from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Awaitable, Callable, Literal, Sequence

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text

from core.database.models import GenerationModel
from core.config import settings
from core.database.session import async_session_factory
from core.events import event_bus
from core.pdf_export_runtime import (
    PDFExportTelemetrySnapshot,
    ensure_pdf_temp_dir,
    pdf_export_telemetry,
)
from core.version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

__version__ = VERSION


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    timestamp: str
    version: str
    instance_id: str | None = None
    started_at: str | None = None
    pipeline_architecture: str | None = None


class DependencyStatus(BaseModel):
    name: str
    status: Literal["ok", "degraded", "unreachable"]
    latency_ms: float | None = None
    detail: str | None = None


class GenerationSummary(BaseModel):
    running: int
    pending: int
    failed_last_hour: int
    completed_last_hour: int


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    timestamp: str
    version: str
    instance_id: str | None = None
    uptime_seconds: float | None = None
    dependencies: list[DependencyStatus]
    generations: GenerationSummary | None = None
    pdf_exports: PDFExportTelemetrySnapshot | None = None


class ImageProbeResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    timestamp: str
    version: str
    dependencies: list[DependencyStatus]
    probe_image_bytes: int | None = None


ReadinessCheck = Callable[[], Awaitable[DependencyStatus]]
ImageProbeRunner = Callable[[], Awaitable[tuple[list[DependencyStatus], int | None]]]

_additional_readiness_checks: list[ReadinessCheck] = []
_image_probe_runner: ImageProbeRunner | None = None


def configure_health_extensions(
    *,
    readiness_checks: Sequence[ReadinessCheck] | None = None,
    image_probe_runner: ImageProbeRunner | None = None,
) -> None:
    global _additional_readiness_checks, _image_probe_runner
    _additional_readiness_checks = list(readiness_checks or [])
    _image_probe_runner = image_probe_runner


async def _check_database() -> DependencyStatus:
    start = perf_counter()
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - exercised via tests
        logger.error("Database health check failed", exc_info=exc)
        return DependencyStatus(
            name="postgres",
            status="unreachable",
            detail=str(exc),
        )

    latency_ms = (perf_counter() - start) * 1000
    return DependencyStatus(
        name="postgres",
        status="ok",
        latency_ms=round(latency_ms, 1),
    )


async def _check_event_bus() -> DependencyStatus:
    probe_id = "__health_probe__"
    queue = event_bus.subscribe(probe_id)
    try:
        event_bus.publish(probe_id, {"type": "health_probe"})
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        if event != {"type": "health_probe"}:
            raise RuntimeError("Unexpected event bus probe payload")
    except Exception as exc:  # pragma: no cover - exercised via tests
        logger.warning("Event bus health check failed", exc_info=exc)
        return DependencyStatus(
            name="event_bus",
            status="degraded",
            detail=str(exc),
        )
    finally:
        event_bus.unsubscribe(probe_id, queue)

    return DependencyStatus(name="event_bus", status="ok")


async def _check_playwright_runtime() -> DependencyStatus:
    browsers_path = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "")
    if browsers_path and os.path.exists(browsers_path):
        return DependencyStatus(name="playwright", status="ok")

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:  # pragma: no cover - exercised via tests
        return DependencyStatus(name="playwright", status="degraded", detail=str(exc))

    start = perf_counter()
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            await browser.close()
    except Exception as exc:  # pragma: no cover - exercised via tests
        logger.warning("Playwright health check failed", exc_info=exc)
        return DependencyStatus(name="playwright", status="degraded", detail=str(exc))

    return DependencyStatus(
        name="playwright",
        status="ok",
        latency_ms=round((perf_counter() - start) * 1000, 1),
    )


async def _check_pdf_temp_dir() -> DependencyStatus:
    start = perf_counter()
    try:
        temp_dir = ensure_pdf_temp_dir(settings.pdf_temp_dir)
        probe = temp_dir / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:  # pragma: no cover - exercised via tests
        logger.warning("PDF temp dir health check failed", exc_info=exc)
        return DependencyStatus(name="pdf_temp_dir", status="degraded", detail=str(exc))

    return DependencyStatus(
        name="pdf_temp_dir",
        status="ok",
        latency_ms=round((perf_counter() - start) * 1000, 1),
    )


async def _get_generation_summary() -> GenerationSummary | None:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    try:
        async with async_session_factory() as session:
            running = await session.scalar(
                select(func.count()).select_from(GenerationModel).where(GenerationModel.status == "running")
            )
            pending = await session.scalar(
                select(func.count()).select_from(GenerationModel).where(GenerationModel.status == "pending")
            )
            failed = await session.scalar(
                select(func.count()).select_from(GenerationModel).where(
                    GenerationModel.status == "failed",
                    GenerationModel.completed_at >= cutoff,
                )
            )
            completed = await session.scalar(
                select(func.count()).select_from(GenerationModel).where(
                    GenerationModel.status == "completed",
                    GenerationModel.completed_at >= cutoff,
                )
            )
    except Exception as exc:  # pragma: no cover - exercised via tests
        logger.warning("Could not fetch generation summary for health check", exc_info=exc)
        return None

    return GenerationSummary(
        running=running or 0,
        pending=pending or 0,
        failed_last_hour=failed or 0,
        completed_last_hour=completed or 0,
    )


def _overall_status(dependencies: list[DependencyStatus]) -> Literal["ok", "degraded", "unavailable"]:
    if any(dep.name == "postgres" and dep.status == "unreachable" for dep in dependencies):
        return "unavailable"
    if any(dep.status != "ok" for dep in dependencies):
        return "degraded"
    return "ok"


def _dependency_rollup(
    dependencies: list[DependencyStatus],
) -> Literal["ok", "degraded", "unavailable"]:
    if any(dep.status == "unreachable" for dep in dependencies):
        return "unavailable"
    if any(dep.status != "ok" for dep in dependencies):
        return "degraded"
    return "ok"


def _readiness_status_code(status: Literal["ok", "degraded", "unavailable"]) -> int:
    return 503 if status == "unavailable" else 200


@router.get("/health", response_model=LivenessResponse)
async def health_check(request: Request) -> LivenessResponse:
    started_at = getattr(request.app.state, "started_at", None)
    return LivenessResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=__version__,
        instance_id=getattr(request.app.state, "instance_id", None),
        started_at=started_at.isoformat() if started_at else None,
        pipeline_architecture=getattr(request.app.state, "pipeline_architecture", None),
    )


async def _build_readiness_payload(request: Request) -> ReadinessResponse:
    now = datetime.now(timezone.utc)
    (
        db_status,
        event_bus_status,
        playwright_status,
        temp_dir_status,
        generation_summary,
    ) = await asyncio.gather(
        _check_database(),
        _check_event_bus(),
        _check_playwright_runtime(),
        _check_pdf_temp_dir(),
        _get_generation_summary(),
    )
    extra_statuses: list[DependencyStatus] = []
    if _additional_readiness_checks:
        extra_statuses = list(
            await asyncio.gather(*(check() for check in _additional_readiness_checks))
        )
    dependencies = [
        db_status,
        event_bus_status,
        playwright_status,
        temp_dir_status,
        *extra_statuses,
    ]
    overall = _overall_status(dependencies)
    started_at = getattr(request.app.state, "started_at", None)
    uptime_seconds = (now - started_at).total_seconds() if started_at else None

    return ReadinessResponse(
        status=overall,
        timestamp=now.isoformat(),
        version=__version__,
        instance_id=getattr(request.app.state, "instance_id", None),
        uptime_seconds=round(uptime_seconds, 1) if uptime_seconds is not None else None,
        dependencies=dependencies,
        generations=generation_summary,
        pdf_exports=pdf_export_telemetry.snapshot(),
    )


@router.get("/health/deep", response_model=ReadinessResponse)
async def deep_health_check(request: Request) -> JSONResponse:
    payload = await _build_readiness_payload(request)
    return JSONResponse(
        status_code=_readiness_status_code(payload.status),
        content=payload.model_dump(mode="json"),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(request: Request) -> JSONResponse:
    payload = await _build_readiness_payload(request)
    return JSONResponse(
        status_code=_readiness_status_code(payload.status),
        content=payload.model_dump(mode="json"),
    )


@router.post("/health/image/probe", response_model=ImageProbeResponse)
async def image_probe_check() -> JSONResponse:
    if _image_probe_runner is None:
        payload = ImageProbeResponse(
            status="degraded",
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=__version__,
            dependencies=[
                DependencyStatus(
                    name="image_probe",
                    status="degraded",
                    detail="No image probe runner configured.",
                )
            ],
        )
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))

    dependencies, probe_image_bytes = await _image_probe_runner()
    payload = ImageProbeResponse(
        status=_dependency_rollup(dependencies),
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=__version__,
        dependencies=dependencies,
        probe_image_bytes=probe_image_bytes,
    )
    return JSONResponse(
        status_code=200 if payload.status == "ok" else 503,
        content=payload.model_dump(mode="json"),
    )
