from __future__ import annotations

import pytest

from media.diagnostics.v3_image_pipeline_diagnostic import (
    DiagnosticReport,
    ProbeResult,
    build_probe_work_order,
    format_report,
    force_production_image_store,
    run_gcs_probe,
)
from media.storage import image_store as image_store_module


def test_build_probe_work_order_creates_minimal_visual_request() -> None:
    order = build_probe_work_order()

    assert order.work_order_id == "diag-v3-image"
    assert order.visual.id == "vis-diagnostic-1"
    assert order.visual.mode == "diagram"
    assert order.visual.attaches_to == "diagnostic_section"
    assert "Diagnostic" in order.visual.labels_required


def test_force_production_image_store_temporarily_overrides_app_env() -> None:
    original_app_env = image_store_module.settings.app_env
    image_store_module.settings.app_env = "development"

    try:
        with force_production_image_store():
            assert image_store_module.settings.app_env == "production"
        assert image_store_module.settings.app_env == "development"
    finally:
        image_store_module.settings.app_env = original_app_env


def test_format_report_renders_pass_fail_and_error_details() -> None:
    report = DiagnosticReport(
        env_file="C:/tmp/.env",
        app_env="development",
        image_provider={
            "provider": "xai",
            "model": "grok-imagine-image",
            "base_url": "https://api.x.ai/v1",
            "api_key_env": "XAI_API_KEY",
        },
        gcs_bucket_name="lectio-bucket-1",
        gcs_service_account_present=True,
        results=[
            ProbeResult(
                name="grok_imagine_only",
                ok=True,
                details={"byte_count": 128, "format": "jpeg"},
            ),
            ProbeResult(
                name="v3_gcs_upload_only",
                ok=False,
                details={"bucket_name": "lectio-bucket-1"},
                error="gcs_upload failed (RuntimeError): auth error",
                error_type="RuntimeError",
                stage="gcs_upload",
                traceback_text="Traceback line 1\nTraceback line 2\n",
            ),
        ],
    )

    rendered = format_report(report)

    assert "[PASS] grok_imagine_only" in rendered
    assert "[FAIL] v3_gcs_upload_only" in rendered
    assert "stage=gcs_upload" in rendered
    assert "error_type=RuntimeError" in rendered
    assert "Traceback line 1" in rendered


@pytest.mark.asyncio
async def test_run_gcs_probe_labels_constructor_failure_as_gcs_upload(monkeypatch) -> None:
    class StubStore:
        def __init__(self, bucket_name: str) -> None:
            _ = bucket_name
            raise RuntimeError("missing credentials")

    monkeypatch.setattr(
        "media.diagnostics.v3_image_pipeline_diagnostic.GCSImageStore",
        StubStore,
    )

    result = await run_gcs_probe(b"png-bytes", "embedded_fallback_png")

    assert result.ok is False
    assert result.stage == "gcs_upload"
    assert result.error_type == "RuntimeError"
    assert result.error == "gcs_upload failed (RuntimeError): missing credentials"
