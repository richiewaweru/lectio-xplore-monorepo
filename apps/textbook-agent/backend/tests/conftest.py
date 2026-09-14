from __future__ import annotations

import asyncio
import logging
import os
import secrets
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_TEST_DB_DIR = Path(tempfile.gettempdir()) / "textbook-agent-pytest"
_TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
_TEST_DB_PATH = _TEST_DB_DIR / f"app-runtime-{os.getpid()}.db"
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

from core.database.models import Base
from core.database.session import engine as runtime_engine


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


class _LogCaptureFixture:
    """Minimal caplog stand-in for runs with ``-p no:logging``."""

    def __init__(self) -> None:
        self.records: list[logging.LogRecord] = []
        self._handler: logging.Handler | None = None
        self._level = logging.NOTSET
        self._logger_name: str | None = None
        self._prev_levels: dict[str, int] = {}

    @property
    def text(self) -> str:
        return "\n".join(record.getMessage() for record in self.records)

    def set_level(self, level: int | str, logger: str | None = None) -> None:
        resolved = logging._checkLevel(level)  # type: ignore[attr-defined]
        self._level = resolved
        self._logger_name = logger
        target = logging.getLogger(logger)
        self._prev_levels[target.name] = target.level
        target.setLevel(resolved)
        if self._handler is not None:
            self._handler.setLevel(resolved)

    @contextmanager
    def at_level(self, level: int | str, logger: str | None = None) -> Iterator[None]:
        target = logging.getLogger(logger)
        previous = target.level
        resolved = logging._checkLevel(level)  # type: ignore[attr-defined]
        target.setLevel(resolved)
        previous_handler = None
        if self._handler is not None:
            previous_handler = self._handler.level
            self._handler.setLevel(resolved)
        try:
            yield
        finally:
            target.setLevel(previous)
            if self._handler is not None and previous_handler is not None:
                self._handler.setLevel(previous_handler)

    def _install(self) -> None:
        handler = _CapturingHandler(self)
        handler.setLevel(self._level if self._level != logging.NOTSET else logging.DEBUG)
        logging.getLogger().addHandler(handler)
        self._handler = handler

    def _uninstall(self) -> None:
        if self._handler is not None:
            logging.getLogger().removeHandler(self._handler)
            self._handler = None
        for name, level in self._prev_levels.items():
            logging.getLogger(name).setLevel(level)
        self._prev_levels.clear()


class _CapturingHandler(logging.Handler):
    def __init__(self, fixture: _LogCaptureFixture) -> None:
        super().__init__()
        self.fixture = fixture

    def emit(self, record: logging.LogRecord) -> None:
        # Match pytest LogCaptureFixture: expose `.message` on records.
        record.message = record.getMessage()
        self.fixture.records.append(record)


@pytest.fixture
def caplog() -> Iterator[_LogCaptureFixture]:
    """Provide caplog even when pytest's logging plugin is disabled."""
    fixture = _LogCaptureFixture()
    fixture._install()
    try:
        yield fixture
    finally:
        fixture._uninstall()


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
