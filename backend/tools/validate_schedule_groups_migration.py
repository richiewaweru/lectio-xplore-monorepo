from __future__ import annotations

import tempfile
from importlib import import_module
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="xplore-p9-migration-") as temporary:
        database = Path(temporary) / "phase9.db"
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        migration = import_module(
            "core.database.migrations.versions.20260801_0024_add_teaching_schedule_and_groups"
        )
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE units (id VARCHAR PRIMARY KEY)"
                )
                connection.exec_driver_sql(
                    "CREATE TABLE path_versions (id VARCHAR PRIMARY KEY)"
                )
                connection.exec_driver_sql(
                    "CREATE TABLE path_lessons (id VARCHAR PRIMARY KEY)"
                )
                context = MigrationContext.configure(connection)
                migration.op = Operations(context)
                migration.upgrade()
                tables = set(inspect(connection).get_table_names())
                expected = {
                    "teaching_periods",
                    "teaching_period_lessons",
                    "unit_groups",
                }
                if not expected <= tables:
                    raise RuntimeError("0024 upgrade did not create all Phase 9 tables")
                print(f"upgrade_tables={','.join(sorted(expected))}")

                migration.downgrade()
                tables = set(inspect(connection).get_table_names())
                if expected & tables:
                    raise RuntimeError("0024 downgrade did not remove all Phase 9 tables")
                unit_columns = {column["name"] for column in inspect(connection).get_columns("units")}
                path_columns = {
                    column["name"] for column in inspect(connection).get_columns("path_versions")
                }
                if "groups_revision" in unit_columns or "schedule_revision" in path_columns:
                    raise RuntimeError("0024 downgrade did not remove revision guards")
                print("downgrade=clean")

                migration.upgrade()
                print("revision=20260801_0024")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
