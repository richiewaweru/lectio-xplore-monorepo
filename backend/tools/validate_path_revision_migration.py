from __future__ import annotations

import os
import tempfile
from importlib import import_module
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="xplore-p8-migration-") as temporary:
        database = Path(temporary) / "phase8.db"
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{database.as_posix()}"
        migration = import_module(
            "core.database.migrations.versions.20260801_0023_add_path_version_revision"
        )
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE path_versions "
                    "(id VARCHAR PRIMARY KEY, unit_id VARCHAR NOT NULL, version INTEGER NOT NULL, "
                    "status VARCHAR NOT NULL)"
                )
                context = MigrationContext.configure(connection)
                migration.op = Operations(context)
                migration.upgrade()
                upgraded = [column["name"] for column in inspect(connection).get_columns("path_versions")]
                if "revision" not in upgraded:
                    raise RuntimeError("0023 upgrade did not add path_versions.revision")
                print(f"upgrade_columns={','.join(upgraded)}")

                migration.downgrade()
                downgraded = [column["name"] for column in inspect(connection).get_columns("path_versions")]
                if "revision" in downgraded:
                    raise RuntimeError("0023 downgrade did not remove path_versions.revision")
                print(f"downgrade_columns={','.join(downgraded)}")

                migration.upgrade()
                print("revision=20260801_0023")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
