from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import GenerationModel
from generation.entities.generation import Generation
from generation.ports.generation_repository import GenerationRepository


class SqlGenerationRepository(GenerationRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, generation: Generation) -> Generation:
        async with self._session_factory() as session:
            model = GenerationModel(
                id=generation.id,
                user_id=generation.user_id,
                subject=generation.subject,
                context=generation.context,
                mode=generation.mode.value,
                status=generation.status,
                document_path=generation.document_path,
                error=generation.error,
                error_type=generation.error_type,
                error_code=generation.error_code,
                requested_template_id=generation.requested_template_id,
                resolved_template_id=generation.resolved_template_id,
                requested_preset_id=generation.requested_preset_id,
                resolved_preset_id=generation.resolved_preset_id,
                section_count=generation.section_count,
                quality_passed=generation.quality_passed,
                generation_time_seconds=generation.generation_time_seconds,
                planning_spec_json=generation.planning_spec_json,
                created_at=self._db_datetime(generation.created_at),
                completed_at=self._db_datetime(generation.completed_at),
                last_heartbeat=self._db_datetime(generation.last_heartbeat),
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_entity(model)

    async def update_status(
        self,
        generation_id: str,
        status: str,
        document_path: str | None = None,
        error: str | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        resolved_template_id: str | None = None,
        resolved_preset_id: str | None = None,
        quality_passed: bool | None = None,
        generation_time_seconds: float | None = None,
    ) -> None:
        async with self._session_factory() as session:
            stmt = select(GenerationModel).where(GenerationModel.id == generation_id)
            result = await session.execute(stmt)
            model = result.scalar_one()
            model.status = status
            if document_path is not None:
                model.document_path = document_path
            if error is not None:
                model.error = error
            if error_type is not None:
                model.error_type = error_type
            if error_code is not None:
                model.error_code = error_code
            if resolved_template_id is not None:
                model.resolved_template_id = resolved_template_id
            if resolved_preset_id is not None:
                model.resolved_preset_id = resolved_preset_id
            if quality_passed is not None:
                model.quality_passed = quality_passed
            if generation_time_seconds is not None:
                model.generation_time_seconds = generation_time_seconds
            if status in ("completed", "failed", "partial"):
                model.completed_at = self._db_datetime(datetime.now(timezone.utc))
            await session.commit()

    async def find_by_id(self, generation_id: str) -> Generation | None:
        async with self._session_factory() as session:
            stmt = select(GenerationModel).where(GenerationModel.id == generation_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return self._to_entity(row) if row else None

    async def list_by_user(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[Generation]:
        async with self._session_factory() as session:
            stmt = (
                select(GenerationModel)
                .where(GenerationModel.user_id == user_id)
                .order_by(GenerationModel.created_at.desc(), GenerationModel.id.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_entity(row) for row in rows]

    async def count_active_by_user(self, user_id: str) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count(GenerationModel.id)).where(
                GenerationModel.user_id == user_id,
                GenerationModel.status.in_(("pending", "running")),
            )
            result = await session.execute(stmt)
            return int(result.scalar_one())

    async def update_heartbeat(
        self,
        generation_id: str,
        heartbeat_at: datetime | None = None,
    ) -> None:
        async with self._session_factory() as session:
            stmt = select(GenerationModel).where(GenerationModel.id == generation_id)
            result = await session.execute(stmt)
            model = result.scalar_one()
            model.last_heartbeat = self._db_datetime(
                heartbeat_at or datetime.now(timezone.utc)
            )
            await session.commit()

    @staticmethod
    def _to_entity(model: GenerationModel) -> Generation:
        return Generation(
            id=model.id,
            user_id=model.user_id,
            subject=model.subject,
            context=model.context or "",
            mode=model.mode or "balanced",
            status=model.status,
            document_path=model.document_path,
            error=model.error,
            error_type=model.error_type,
            error_code=model.error_code,
            requested_template_id=model.requested_template_id,
            resolved_template_id=model.resolved_template_id,
            requested_preset_id=model.requested_preset_id,
            resolved_preset_id=model.resolved_preset_id,
            section_count=model.section_count,
            quality_passed=model.quality_passed,
            generation_time_seconds=model.generation_time_seconds,
            planning_spec_json=model.planning_spec_json,
            created_at=model.created_at,
            completed_at=model.completed_at,
            last_heartbeat=model.last_heartbeat,
        )

    @staticmethod
    def _db_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

