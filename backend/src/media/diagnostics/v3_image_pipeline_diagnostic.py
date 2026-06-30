from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import traceback
from dataclasses import dataclass, field
from typing import Any

from core.config import _ENV_FILE, settings
from media.providers.registry import get_image_client, load_image_provider_spec
from media.storage import image_store as image_store_module
from media.storage.image_store import GCSImageStore
from v3_execution.executors.visual_executor import VisualStageError, execute_visual
from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem

_FALLBACK_TEST_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnVddcAAAAASUVORK5CYII="
)


@dataclass
class ProbeResult:
    name: str
    ok: bool
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    stage: str | None = None
    traceback_text: str | None = None


@dataclass
class DiagnosticReport:
    env_file: str
    app_env: str
    image_provider: dict[str, Any]
    gcs_bucket_name: str
    gcs_service_account_present: bool
    results: list[ProbeResult]


def build_probe_work_order() -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="diag-v3-image",
        resource_type="lesson",
        dependency="blueprint_only",
        visual=VisualPlanItem(
            id="vis-diagnostic-1",
            attaches_to="diagnostic_section",
            component_id="diagram-block",
            mode="diagram",
            purpose="Create a minimal labeled educational diagram for pipeline diagnostics.",
            must_show=[
                "high-contrast simple line art",
                "one title label",
                "one central shape",
            ],
            must_not_show=[
                "photo-realistic textures",
                "dense background detail",
            ],
            labels_required=["Diagnostic"],
            print_requirements=[
                "high contrast",
                "single frame",
                "readable black-and-white labels",
            ],
        ),
        source_of_truth=[],
    )


def _probe_prompt() -> str:
    return (
        "Generate a simple black-and-white educational diagram labeled "
        "'Diagnostic'. Use one centered shape and one short label."
    )


def _format_exception(exc: Exception) -> tuple[str, str, str | None, str]:
    if isinstance(exc, VisualStageError):
        return (
            exc.to_error_message(),
            exc.original_exception_type,
            exc.stage,
            exc.traceback_text,
        )
    return (
        str(exc),
        type(exc).__name__,
        None,
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )


def _choose_upload_bytes(grok_probe: ProbeResult) -> tuple[bytes, str]:
    image_bytes = grok_probe.details.get("image_bytes")
    if isinstance(image_bytes, bytes) and image_bytes:
        return image_bytes, "grok_probe"
    return _FALLBACK_TEST_IMAGE, "embedded_fallback_png"


@contextlib.contextmanager
def force_production_image_store() -> Any:
    original_app_env = image_store_module.settings.app_env
    image_store_module.settings.app_env = "production"
    try:
        yield
    finally:
        image_store_module.settings.app_env = original_app_env


async def run_grok_probe() -> ProbeResult:
    try:
        spec = load_image_provider_spec()
        client = get_image_client()
        image = await client.generate_image(prompt=_probe_prompt())
        return ProbeResult(
            name="grok_imagine_only",
            ok=True,
            details={
                "provider": spec.provider,
                "model": spec.model_name,
                "byte_count": len(image.bytes),
                "mime_type": image.mime_type,
                "format": image.format,
                "image_bytes": image.bytes,
            },
        )
    except Exception as exc:  # noqa: BLE001
        error, error_type, stage, tb = _format_exception(exc)
        return ProbeResult(
            name="grok_imagine_only",
            ok=False,
            error=error,
            error_type=error_type,
            stage=stage,
            traceback_text=tb,
        )


async def run_gcs_probe(image_bytes: bytes, source: str) -> ProbeResult:
    try:
        try:
            store = GCSImageStore(bucket_name=settings.gcs_bucket_name)
            url = await store.store_image(
                image_bytes,
                generation_id="diagnostic-generation",
                section_id="diagnostic-section",
                filename="diagnostic-image.png",
                format="png",
            )
        except Exception as exc:  # noqa: BLE001
            raise VisualStageError.from_exception(stage="gcs_upload", exc=exc) from exc
        return ProbeResult(
            name="v3_gcs_upload_only",
            ok=True,
            details={
                "store_class": type(store).__name__,
                "bucket_name": store.bucket_name,
                "credential_source": store.credential_source,
                "credentials_resolved": store.credentials_resolved,
                "base_url": store.base_url,
                "upload_source": source,
                "byte_count": len(image_bytes),
                "final_url": url,
            },
        )
    except Exception as exc:  # noqa: BLE001
        error, error_type, stage, tb = _format_exception(exc)
        return ProbeResult(
            name="v3_gcs_upload_only",
            ok=False,
            details={
                "bucket_name": settings.gcs_bucket_name,
                "upload_source": source,
                "byte_count": len(image_bytes),
            },
            error=error,
            error_type=error_type,
            stage=stage,
            traceback_text=tb,
        )


async def run_full_v3_probe() -> ProbeResult:
    order = build_probe_work_order()
    emitted_events: list[dict[str, Any]] = []
    try:
        with force_production_image_store():
            async def emit(event_type: str, payload: dict[str, Any]) -> None:
                emitted_events.append({"event_type": event_type, "payload": payload})

            blocks = await execute_visual(
                order,
                emit,
                trace_id="diagnostic-trace",
                generation_id="diagnostic-generation",
            )

        block_summaries = [
            {
                "visual_id": block.visual_id,
                "status": block.status,
                "mode": block.mode,
                "image_url": block.image_url,
                "error_message": block.error_message,
            }
            for block in blocks
        ]
        failed = next((block for block in blocks if block.status == "failed"), None)
        if failed is not None:
            return ProbeResult(
                name="full_v3_visual_function",
                ok=False,
                details={
                    "store_app_env": "production",
                    "events": emitted_events,
                    "blocks": block_summaries,
                },
                error=failed.error_message or "visual generation failed",
                error_type="GeneratedVisualBlockFailure",
                stage="failed_block_error_message",
            )
        return ProbeResult(
            name="full_v3_visual_function",
            ok=True,
            details={
                "store_app_env": "production",
                "events": emitted_events,
                "blocks": block_summaries,
            },
        )
    except Exception as exc:  # noqa: BLE001
        error, error_type, stage, tb = _format_exception(exc)
        return ProbeResult(
            name="full_v3_visual_function",
            ok=False,
            details={
                "store_app_env": "production",
                "events": emitted_events,
            },
            error=error,
            error_type=error_type,
            stage=stage,
            traceback_text=tb,
        )


async def run_diagnostic() -> DiagnosticReport:
    grok_probe = await run_grok_probe()
    upload_bytes, upload_source = _choose_upload_bytes(grok_probe)
    gcs_probe = await run_gcs_probe(upload_bytes, upload_source)
    full_probe = await run_full_v3_probe()
    provider_summary: dict[str, Any]
    try:
        spec = load_image_provider_spec()
        provider_summary = {
            "provider": spec.provider,
            "model": spec.model_name,
            "base_url": spec.base_url,
            "api_key_env": spec.api_key_env,
        }
    except Exception:
        provider_summary = {
            "provider": "unresolved",
            "model": None,
            "base_url": None,
            "api_key_env": None,
        }
    return DiagnosticReport(
        env_file=os.getenv("V3_IMAGE_DIAGNOSTIC_ENV_FILE", str(_ENV_FILE)),
        app_env=settings.app_env,
        image_provider=provider_summary,
        gcs_bucket_name=settings.gcs_bucket_name,
        gcs_service_account_present=bool(os.getenv("GCS_SERVICE_ACCOUNT_JSON", "").strip()),
        results=[grok_probe, gcs_probe, full_probe],
    )


def format_report(report: DiagnosticReport) -> str:
    lines = [
        "V3 image pipeline diagnostic",
        f"env_file={report.env_file}",
        f"app_env={report.app_env}",
        (
            "image_provider="
            f"{json.dumps(report.image_provider, sort_keys=True, default=str)}"
        ),
        f"gcs_bucket_name={report.gcs_bucket_name}",
        f"gcs_service_account_present={report.gcs_service_account_present}",
        "",
    ]
    for result in report.results:
        status = "PASS" if result.ok else "FAIL"
        lines.append(f"[{status}] {result.name}")
        for key, value in result.details.items():
            if key == "image_bytes":
                continue
            lines.append(f"  {key}={json.dumps(value, sort_keys=True, default=str)}")
        if result.error is not None:
            lines.append(f"  error_type={result.error_type}")
            lines.append(f"  stage={result.stage}")
            lines.append(f"  error={result.error}")
        if result.traceback_text:
            lines.append("  traceback:")
            for line in result.traceback_text.rstrip().splitlines():
                lines.append(f"    {line}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "DiagnosticReport",
    "ProbeResult",
    "build_probe_work_order",
    "format_report",
    "force_production_image_store",
    "run_diagnostic",
]
