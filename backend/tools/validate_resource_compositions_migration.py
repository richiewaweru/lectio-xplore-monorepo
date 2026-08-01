from __future__ import annotations

import tempfile
from importlib import import_module
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="xplore-p11-migration-") as temporary:
        database = Path(temporary) / "phase11.db"
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        migration = import_module(
            "core.database.migrations.versions.20260801_0026_add_resource_compositions"
        )
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql("CREATE TABLE users (id VARCHAR PRIMARY KEY)")
                connection.exec_driver_sql("CREATE TABLE units (id VARCHAR PRIMARY KEY)")
                connection.exec_driver_sql("CREATE TABLE path_versions (id VARCHAR PRIMARY KEY)")
                context = MigrationContext.configure(connection)
                migration.op = Operations(context)

                migration.upgrade()
                if "resource_compositions" not in inspect(connection).get_table_names():
                    raise RuntimeError("0026 upgrade did not create resource_compositions")
                columns = {
                    column["name"]
                    for column in inspect(connection).get_columns("resource_compositions")
                }
                required = {
                    "source_snapshots", "selected_component_refs", "selected_item_ids",
                    "template_version", "document_json",
                }
                if not required <= columns:
                    raise RuntimeError("0026 upgrade is missing projection provenance columns")
                print("upgrade=resource_compositions,source_provenance")

                migration.downgrade()
                if "resource_compositions" in inspect(connection).get_table_names():
                    raise RuntimeError("0026 downgrade left resource_compositions behind")
                print("downgrade=clean")

                migration.upgrade()
                print("revision=20260801_0026")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
