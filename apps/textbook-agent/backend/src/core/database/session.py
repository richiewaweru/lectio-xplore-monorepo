from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings


def build_engine_kwargs(database_url: str, *, db_echo: bool) -> dict[str, object]:
    kwargs: dict[str, object] = {"echo": db_echo}
    if database_url.startswith("sqlite"):
        return kwargs
    kwargs.update(
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    return kwargs


engine = create_async_engine(
    settings.database_url,
    **build_engine_kwargs(settings.database_url, db_echo=settings.db_echo),
)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session
