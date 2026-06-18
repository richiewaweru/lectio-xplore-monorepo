from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import GenerationModel
from pipeline.reporting import GenerationReport
from telemetry.ports.generation_report_repository import GenerationReportRepository


class SqlGenerationReportRepository(GenerationReportRepository):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        legacy_output_dir: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._legacy_output_dir = Path(legacy_output_dir) if legacy_output_dir else None

    @staticmethod
    def _locator_for(generation_id: str) -> str:
        return f"generation:{generation_id}:report"

    async def save_report(self, report: GenerationReport) -> str:
        async with self._session_factory() as session:
            stmt = select(GenerationModel).where(GenerationModel.id == report.generation_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                raise FileNotFoundError(report.generation_id)

            model.report_json = report.model_dump(mode="json", exclude_none=True)
            await session.commit()
            return self._locator_for(report.generation_id)

    async def load_report(self, generation_id: str) -> GenerationReport:
        async with self._session_factory() as session:
            stmt = select(GenerationModel.report_json).where(GenerationModel.id == generation_id)
            result = await session.execute(stmt)
            row = result.first()
            if row is not None and row[0]:
                payload = row[0]
                if isinstance(payload, str):
                    return GenerationReport.model_validate_json(payload)
                return GenerationReport.model_validate(payload)

        if self._legacy_output_dir is not None:
            legacy_path = self._legacy_output_dir / f"{generation_id}.json"
            if legacy_path.exists():
                return GenerationReport.model_validate_json(
                    legacy_path.read_text(encoding="utf-8")
                )

        raise FileNotFoundError(generation_id)

    async def cleanup_tmp(self, generation_id: str) -> None:
        _ = generation_id
