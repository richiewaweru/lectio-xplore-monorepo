from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from pipeline.reporting import GenerationReport
from telemetry.ports.generation_report_repository import GenerationReportRepository

logger = logging.getLogger(__name__)

_REPLACE_BACKOFF_SECONDS = (0.25, 0.5, 1.0)


class FileGenerationReportRepository(GenerationReportRepository):
    def __init__(self, output_dir: str) -> None:
        self._root = Path(output_dir)

    def _path_for(self, generation_id: str) -> Path:
        return self._root / f"{generation_id}.json"

    async def save_report(self, report: GenerationReport) -> str:
        path = self._path_for(report.generation_id)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        payload = report.model_dump(mode="json", exclude_none=True)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await self.cleanup_tmp(report.generation_id)
        await asyncio.to_thread(
            tmp_path.write_text,
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        for attempt, delay in enumerate((0.0, *_REPLACE_BACKOFF_SECONDS), start=1):
            if delay:
                await asyncio.sleep(delay)
            try:
                await asyncio.to_thread(tmp_path.replace, path)
                break
            except OSError:
                logger.warning(
                    "Report atomic replace failed generation=%s attempt=%s path=%s",
                    report.generation_id,
                    attempt,
                    path,
                    exc_info=True,
                )
                if attempt == len(_REPLACE_BACKOFF_SECONDS) + 1:
                    logger.error(
                        "Report atomic replace permanently failed generation=%s path=%s",
                        report.generation_id,
                        path,
                    )
                    raise
        return str(path.resolve())

    async def load_report(self, generation_id: str) -> GenerationReport:
        path = self._path_for(generation_id)
        if not path.exists():
            raise FileNotFoundError(str(path))
        raw = await asyncio.to_thread(path.read_text, encoding="utf-8")
        return GenerationReport.model_validate_json(raw)

    async def cleanup_tmp(self, generation_id: str) -> None:
        path = self._path_for(generation_id)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            if await asyncio.to_thread(tmp_path.exists):
                await asyncio.to_thread(tmp_path.unlink)
        except OSError:
            logger.warning(
                "Failed to clean stale report temp file generation=%s path=%s",
                generation_id,
                tmp_path,
                exc_info=True,
            )
