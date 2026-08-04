from __future__ import annotations

from generation.pdf_export.telemetry import PDFExportTelemetry


def test_pdf_export_telemetry_tracks_stage_and_export_stats() -> None:
    telemetry = PDFExportTelemetry()

    telemetry.record_stage("content_rendering", duration_ms=1200, status="completed")
    telemetry.record_stage("content_rendering", duration_ms=900, status="failed")
    telemetry.record_export(duration_ms=2800, status="completed")
    telemetry.record_export(duration_ms=3200, status="failed")

    snapshot = telemetry.snapshot()

    assert snapshot.total_exports == 2
    assert snapshot.successful_exports == 1
    assert snapshot.failed_exports == 1
    assert snapshot.last_export_duration_ms == 3200
    assert snapshot.average_export_duration_ms == 3000.0
    assert snapshot.stage_stats["content_rendering"] == {
        "runs": 2,
        "failures": 1,
        "last_duration_ms": 900,
        "average_duration_ms": 1050.0,
    }
