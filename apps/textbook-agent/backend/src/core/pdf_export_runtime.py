from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from pydantic import BaseModel


def pdf_temp_dir(path_value: str) -> Path:
    return Path(path_value).resolve()


def ensure_pdf_temp_dir(path_value: str) -> Path:
    path = pdf_temp_dir(path_value)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_stale_pdf_exports(*, path_value: str, retention_seconds: int) -> int:
    temp_dir = pdf_temp_dir(path_value)
    if not temp_dir.exists():
        return 0

    cutoff = datetime.now(timezone.utc).timestamp() - retention_seconds
    removed = 0
    for path in temp_dir.iterdir():
        try:
            if not path.is_file():
                continue
            if path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


@dataclass(slots=True)
class PDFExportStageStats:
    runs: int = 0
    failures: int = 0
    total_duration_ms: int = 0
    last_duration_ms: int | None = None

    @property
    def average_duration_ms(self) -> float | None:
        if self.runs == 0:
            return None
        return round(self.total_duration_ms / self.runs, 1)


class PDFExportTelemetrySnapshot(BaseModel):
    total_exports: int
    successful_exports: int
    failed_exports: int
    last_export_duration_ms: int | None
    average_export_duration_ms: float | None
    stage_stats: dict[str, dict[str, int | float | None]]


@dataclass(slots=True)
class PDFExportTelemetry:
    total_exports: int = 0
    successful_exports: int = 0
    failed_exports: int = 0
    total_duration_ms: int = 0
    last_export_duration_ms: int | None = None
    stages: dict[str, PDFExportStageStats] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def record_stage(self, stage: str, *, duration_ms: int, status: str) -> None:
        with self._lock:
            stats = self.stages.setdefault(stage, PDFExportStageStats())
            stats.runs += 1
            stats.total_duration_ms += duration_ms
            stats.last_duration_ms = duration_ms
            if status != "completed":
                stats.failures += 1

    def record_export(self, *, duration_ms: int, status: str) -> None:
        with self._lock:
            self.total_exports += 1
            self.total_duration_ms += duration_ms
            self.last_export_duration_ms = duration_ms
            if status == "completed":
                self.successful_exports += 1
            else:
                self.failed_exports += 1

    def snapshot(self) -> PDFExportTelemetrySnapshot:
        with self._lock:
            average = (
                round(self.total_duration_ms / self.total_exports, 1)
                if self.total_exports
                else None
            )
            return PDFExportTelemetrySnapshot(
                total_exports=self.total_exports,
                successful_exports=self.successful_exports,
                failed_exports=self.failed_exports,
                last_export_duration_ms=self.last_export_duration_ms,
                average_export_duration_ms=average,
                stage_stats={
                    stage: {
                        "runs": stats.runs,
                        "failures": stats.failures,
                        "last_duration_ms": stats.last_duration_ms,
                        "average_duration_ms": stats.average_duration_ms,
                    }
                    for stage, stats in self.stages.items()
                },
            )


pdf_export_telemetry = PDFExportTelemetry()
pdf_render_semaphore = asyncio.Semaphore(
    max(1, int(os.getenv("PDF_EXPORT_MAX_CONCURRENT_RENDERS", "1")))
)
