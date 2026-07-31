from __future__ import annotations

import asyncio
import os
import secrets
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


_TEST_DB_DIR = Path(tempfile.gettempdir()) / "textbook-agent-pytest"
_TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
_TEST_DB_PATH = _TEST_DB_DIR / "app-runtime.db"
_BACKEND_ROOT = Path(__file__).resolve().parents[1]

if _TEST_DB_PATH.exists():
    _TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["LECTIO_CONTRACTS_DIR"] = str(_BACKEND_ROOT / "contracts")
os.environ.setdefault("RUN_MIGRATIONS_ON_STARTUP", "false")
os.environ.setdefault("JWT_SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("V3_VISUAL_QC_ENABLED", "false")
os.environ.setdefault("V3_IMAGE_CACHE_ENABLED", "false")
os.environ.setdefault("V2_SKELETON_SHADOW_ENABLED", "false")

from core.database.models import Base  # noqa: E402
from core.database.session import engine as runtime_engine  # noqa: E402


async def _create_runtime_schema() -> None:
    async with runtime_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def pytest_sessionstart(session) -> None:
    _ = session
    asyncio.run(_create_runtime_schema())


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "postgres: tests requiring a real PostgreSQL instance",
    )


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine):
    yield async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
async def db_session(db_engine):
    async with async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )() as session:
        yield session
        await session.rollback()
