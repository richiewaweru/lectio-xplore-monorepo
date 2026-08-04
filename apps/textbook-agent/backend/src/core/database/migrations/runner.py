from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from core.config import settings


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[4]
    config_path = backend_root / "alembic.ini"
    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    config.set_main_option(
        "script_location",
        str(backend_root / "src" / "core" / "database" / "migrations"),
    )
    config.set_main_option("prepend_sys_path", str(backend_root / "src"))
    return config


def upgrade_database(revision: str = "head") -> None:
    command.upgrade(_alembic_config(), revision)
