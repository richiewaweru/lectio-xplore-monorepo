from collections.abc import AsyncGenerator
from functools import lru_cache

from core.dependencies import (
    get_jwt_handler,
    get_settings,
    get_student_profile_repository,
    get_user_repository,
)
from core.database.session import async_session_factory
from core.ports.generation_engine import GenerationEngine
from generation.ports.document_repository import DocumentRepository
from generation.ports.generation_repository import GenerationRepository
from generation.repositories.sql_document_repo import SqlDocumentRepository
from generation.repositories.sql_generation_repo import SqlGenerationRepository
from telemetry.dependencies import get_report_repository


async def get_generation_repository() -> AsyncGenerator[GenerationRepository, None]:
    yield SqlGenerationRepository(async_session_factory)


async def get_document_repository() -> AsyncGenerator[DocumentRepository, None]:
    yield SqlDocumentRepository(async_session_factory)


@lru_cache
def get_generation_engine() -> GenerationEngine:
    from pipeline.adapter import PipelineGenerationEngine

    return PipelineGenerationEngine()


__all__ = [
    "get_document_repository",
    "get_generation_engine",
    "get_generation_repository",
    "get_jwt_handler",
    "get_report_repository",
    "get_settings",
    "get_student_profile_repository",
    "get_user_repository",
]

