from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import GenerationModel
from generation.ports.document_repository import DocumentRepository
from pipeline.api import PipelineDocument


class SqlDocumentRepository(DocumentRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _locator_for(generation_id: str) -> str:
        return f"generation:{generation_id}:document"

    @staticmethod
    def _generation_id_from_locator(locator: str) -> str | None:
        prefix = "generation:"
        suffix = ":document"
        if locator.startswith(prefix) and locator.endswith(suffix):
            return locator[len(prefix) : -len(suffix)]
        return None

    async def save_document(self, document: PipelineDocument) -> str:
        async with self._session_factory() as session:
            stmt = select(GenerationModel).where(GenerationModel.id == document.generation_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                raise FileNotFoundError(document.generation_id)

            locator = document.generation_id
            model.document_path = None
            model.document_json = document.model_dump(mode="json", exclude_none=True)
            await session.commit()
            return locator

    async def load_document(self, path: str) -> PipelineDocument:
        payload = await self._load_document_payload(path)
        if payload is None:
            raise FileNotFoundError(path)
        return PipelineDocument.model_validate(payload)

    async def _load_document_payload(self, locator: str) -> dict | None:
        generation_id = self._generation_id_from_locator(locator) or locator
        async with self._session_factory() as session:
            stmt = select(GenerationModel.document_json).where(GenerationModel.id == generation_id)
            result = await session.execute(stmt)
            row = result.first()
            if row is not None and row[0]:
                payload = row[0]
                if isinstance(payload, str):
                    return PipelineDocument.model_validate_json(payload).model_dump(
                        mode="json",
                        exclude_none=True,
                    )
                return payload
        return None
