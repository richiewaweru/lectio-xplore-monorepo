from __future__ import annotations

import tempfile
from importlib import import_module
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="xplore-p10-migration-") as temporary:
        database = Path(temporary) / "phase10.db"
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        migration = import_module(
            "core.database.migrations.versions.20260801_0025_add_path_shape_deviations"
        )
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql("CREATE TABLE users (id VARCHAR PRIMARY KEY)")
                connection.exec_driver_sql("CREATE TABLE path_lessons (id VARCHAR PRIMARY KEY)")
                connection.exec_driver_sql("CREATE TABLE lesson_provenance (pack_id VARCHAR PRIMARY KEY)")
                context = MigrationContext.configure(connection)
                migration.op = Operations(context)

                migration.upgrade()
                tables = set(inspect(connection).get_table_names())
                if "path_lesson_deviations" not in tables:
                    raise RuntimeError("0025 upgrade did not create the deviation table")
                provenance_columns = {
                    column["name"]
                    for column in inspect(connection).get_columns("lesson_provenance")
                }
                if not {"deviations_requested", "deviations_approved"} <= provenance_columns:
                    raise RuntimeError("0025 upgrade did not add provenance snapshots")
                print("upgrade=path_lesson_deviations,provenance_snapshots")

                migration.downgrade()
                tables = set(inspect(connection).get_table_names())
                provenance_columns = {
                    column["name"]
                    for column in inspect(connection).get_columns("lesson_provenance")
                }
                if "path_lesson_deviations" in tables or {
                    "deviations_requested",
                    "deviations_approved",
                } & provenance_columns:
                    raise RuntimeError("0025 downgrade left Phase 10 schema behind")
                print("downgrade=clean")

                migration.upgrade()
                print("revision=20260801_0025")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
