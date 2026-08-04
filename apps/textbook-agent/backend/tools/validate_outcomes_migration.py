from __future__ import annotations

import tempfile
from importlib import import_module
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="xplore-p12-migration-") as temporary:
        database = Path(temporary) / "phase12.db"
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        migration = import_module(
            "core.database.migrations.versions.20260801_0027_add_lesson_actuals_and_marks"
        )
        try:
            with engine.begin() as connection:
                for table in ("users", "units", "path_versions", "path_lessons", "unit_groups", "pack_items"):
                    connection.exec_driver_sql(f"CREATE TABLE {table} (id VARCHAR PRIMARY KEY)")
                context = MigrationContext.configure(connection)
                migration.op = Operations(context)

                migration.upgrade()
                tables = set(inspect(connection).get_table_names())
                if not {"lesson_actuals", "marks_entries"} <= tables:
                    raise RuntimeError("0027 upgrade did not create outcomes tables")
                actual_columns = {column["name"] for column in inspect(connection).get_columns("lesson_actuals")}
                marks_columns = {column["name"] for column in inspect(connection).get_columns("marks_entries")}
                if not {"revision", "supersedes_actual_id", "objective_hash", "recorded_by"} <= actual_columns:
                    raise RuntimeError("0027 actual audit columns are incomplete")
                if not {"submission_id", "item_id", "option_id", "count", "misconception_id"} <= marks_columns:
                    raise RuntimeError("0027 aggregate marks columns are incomplete")
                print("upgrade=lesson_actuals,marks_entries,audit_provenance")

                migration.downgrade()
                tables = set(inspect(connection).get_table_names())
                if {"lesson_actuals", "marks_entries"} & tables:
                    raise RuntimeError("0027 downgrade left outcomes tables behind")
                print("downgrade=clean")

                migration.upgrade()
                print("revision=20260801_0027")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
