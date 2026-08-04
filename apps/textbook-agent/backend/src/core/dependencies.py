from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.jwt_handler import JWTHandler
from core.config import Settings
from core.database.session import async_session_factory
from core.ports.student_profile_repository import StudentProfileRepository
from core.ports.user_repository import UserRepository
from core.repositories.sql_student_profile_repo import SqlStudentProfileRepository
from core.repositories.sql_user_repo import SqlUserRepository
from core.storage.gcs_image_store import GCSImageStore


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_jwt_handler() -> JWTHandler:
    settings = get_settings()
    return JWTHandler(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_access_token_expire_minutes,
    )


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_user_repository() -> AsyncGenerator[UserRepository, None]:
    async with async_session_factory() as session:
        yield SqlUserRepository(session)


async def get_student_profile_repository() -> AsyncGenerator[StudentProfileRepository, None]:
    async with async_session_factory() as session:
        yield SqlStudentProfileRepository(session)


_gcs_store: GCSImageStore | None = None


def get_gcs_image_store() -> GCSImageStore:
    global _gcs_store
    if _gcs_store is None:
        _gcs_store = GCSImageStore()
    return _gcs_store
