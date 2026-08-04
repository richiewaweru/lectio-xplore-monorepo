from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import GenerationModel, LearningPackModel

TERMINAL_GENERATION_STATUSES = {"completed", "partial", "failed"}


class LearningPackRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, pack: LearningPackModel) -> LearningPackModel:
        async with self._session_factory() as session:
            session.add(pack)
            await session.commit()
            await session.refresh(pack)
            return pack

    async def find_by_id(self, pack_id: str) -> LearningPackModel | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(LearningPackModel).where(LearningPackModel.id == pack_id)
            )
            return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str, limit: int = 20) -> list[LearningPackModel]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(LearningPackModel)
                .where(LearningPackModel.user_id == user_id)
                .order_by(LearningPackModel.created_at.desc(), LearningPackModel.id.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def count_active_by_user(self, user_id: str) -> int:
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count(LearningPackModel.id)).where(
                    LearningPackModel.user_id == user_id,
                    LearningPackModel.status.in_(("pending", "running")),
                )
            )
            return int(result.scalar_one())

    async def update_status(
        self,
        pack_id: str,
        *,
        status: str | None = None,
        completed_count: int | None = None,
        current_resource_label: str | None = None,
        current_phase: str | None = None,
        error: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(LearningPackModel).where(LearningPackModel.id == pack_id)
            )
            model = result.scalar_one()
            if status is not None:
                model.status = status
            if completed_count is not None:
                model.completed_count = completed_count
            model.current_resource_label = current_resource_label
            model.current_phase = current_phase
            if error is not None:
                model.error = error
            if status in {"complete", "failed"}:
                model.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()

    async def generations_for_pack(self, pack_id: str) -> list[GenerationModel]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(GenerationModel)
                .where(GenerationModel.pack_id == pack_id)
                .order_by(GenerationModel.created_at, GenerationModel.id)
            )
            return list(result.scalars().all())
