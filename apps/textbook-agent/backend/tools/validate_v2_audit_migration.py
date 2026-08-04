from __future__ import annotations

import tempfile
from importlib import import_module
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="xplore-p13-migration-") as temporary:
        database = Path(temporary) / "phase13.db"
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        migration = import_module(
            "core.database.migrations.versions.20260801_0028_add_v2_audit_events"
        )
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql("CREATE TABLE users (id VARCHAR PRIMARY KEY)")
                context = MigrationContext.configure(connection)
                migration.op = Operations(context)

                migration.upgrade()
                inspector = inspect(connection)
                if "v2_audit_events" not in inspector.get_table_names():
                    raise RuntimeError("0028 upgrade did not create v2_audit_events")
                columns = {
                    column["name"]
                    for column in inspector.get_columns("v2_audit_events")
                }
                required = {
                    "actor_id",
                    "method",
                    "path",
                    "status_code",
                    "request_id",
                    "event_metadata",
                    "created_at",
                }
                if not required <= columns:
                    raise RuntimeError("0028 audit columns are incomplete")
                print("upgrade=v2_audit_events,persistent_mutation_metadata")

                migration.downgrade()
                if "v2_audit_events" in inspect(connection).get_table_names():
                    raise RuntimeError("0028 downgrade left v2_audit_events behind")
                print("downgrade=clean")

                migration.upgrade()
                print("revision=20260801_0028")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
