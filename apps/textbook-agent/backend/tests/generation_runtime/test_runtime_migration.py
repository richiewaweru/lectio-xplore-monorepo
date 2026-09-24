from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import IntegrityError


def _migration_module():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "infra"
        / "database"
        / "migrations"
        / "versions"
        / "20260924_0043_generation_runtime.py"
    )
    spec = importlib.util.spec_from_file_location("generation_runtime_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _integrity_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "infra"
        / "database"
        / "migrations"
        / "versions"
        / "20260924_0044_generation_runtime_integrity_guards.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generation_runtime_integrity_migration", migration_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_enforces_history_and_ready_immutability() -> None:
    engine = create_engine("sqlite://")
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata = MetaData()
        Table("users", metadata, Column("id", String, primary_key=True))
        Table("path_lessons", metadata, Column("id", String, primary_key=True))
        metadata.create_all(connection)
        connection.execute(text("INSERT INTO users (id) VALUES ('owner')"))
        connection.execute(text("INSERT INTO path_lessons (id) VALUES ('lesson')"))

        migration = _migration_module()
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        connection.execute(
            text(
                "INSERT INTO generation_builds (id, path_lesson_id, owner_user_id, created_at) "
                "VALUES ('build', 'lesson', 'owner', :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "INSERT INTO generation_runs (id, build_id, run_type, owner_user_id, status, stage, "
                "attempt, source_artifact_type, source_artifact_id, source_revision, source_hash, "
                "output_artifact_type, output_artifact_id, output_revision, output_hash, request_key, "
                "created_at, updated_at) VALUES ('run', 'build', 'shared_document', 'owner', 'ready', "
                "'document_qa', 1, 'teaching_plan', 'plan', 1, 'source-hash', 'shared_document', "
                "'document', 1, 'output-hash', 'request', :now, :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "INSERT INTO generation_work_items (id, run_id, item_key, stage, status, attempt, "
                "max_attempts, input_hash, definition_hash, output_json, output_hash, created_at, updated_at) "
                "VALUES ('item', 'run', 'document-qa', 'document_qa', 'ready', 1, 1, 'input', "
                "'definition', :output_json, 'item-hash', :now, :now)"
            ),
            {"output_json": '{"passed":true}', "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO generation_events (id, run_id, work_item_id, seq, event_type, status, "
                "stage, attempt, safe_payload_json, created_at) VALUES ('event', 'run', 'item', 1, "
                "'work_item_ready', 'ready', 'document_qa', 1, '{}', :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "INSERT INTO generation_runs (id, build_id, run_type, owner_user_id, status, stage, "
                "attempt, source_artifact_type, source_artifact_id, source_revision, source_hash, "
                "request_key, created_at, updated_at) VALUES ('transition-run', 'build', "
                "'shared_document', 'owner', 'queued', 'document_qa', 1, 'teaching_plan', 'plan', "
                "1, 'source-hash', 'transition-request', :now, :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "UPDATE generation_runs SET status='ready', output_artifact_type='shared_document', "
                "output_artifact_id='transition-doc', output_revision=1, output_hash='transition-hash' "
                "WHERE id='transition-run'"
            )
        )
        connection.execute(
            text(
                "INSERT INTO generation_work_items (id, run_id, item_key, stage, status, attempt, "
                "max_attempts, input_hash, definition_hash, created_at, updated_at) "
                "VALUES ('transition-item', 'transition-run', 'transition-item', 'document_qa', "
                "'queued', 1, 1, 'input', 'definition', :now, :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "UPDATE generation_work_items SET status='ready', output_json='[1,2,3]', "
                "output_hash='transition-item-hash' WHERE id='transition-item'"
            )
        )
        connection.execute(
            text(
                "INSERT INTO generation_runs (id, build_id, run_type, owner_user_id, status, stage, "
                "attempt, source_artifact_type, source_artifact_id, source_revision, source_hash, "
                "output_artifact_type, output_artifact_id, output_revision, output_hash, request_key, "
                "created_at, updated_at) VALUES ('ready-no-children', 'build', 'shared_document', "
                "'owner', 'ready', 'document_qa', 1, 'teaching_plan', 'plan', 1, 'source-hash', "
                "'shared_document', 'no-children-doc', 1, 'no-children-hash', 'no-children-request', "
                ":now, :now)"
            ),
            {"now": now},
        )

        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO generation_runs (id, build_id, run_type, owner_user_id, status, "
                    "stage, attempt, source_artifact_type, source_artifact_id, source_revision, "
                    "source_hash, request_key, created_at, updated_at) VALUES ('partial-ready', "
                    "'build', 'shared_document', 'owner', 'ready', 'document_qa', 1, 'teaching_plan', "
                    "'plan', 1, 'source-hash', 'partial-request', :now, :now)"
                ),
                {"now": now},
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO generation_events (id, run_id, seq, event_type, status, stage, "
                    "attempt, safe_payload_json, created_at) VALUES ('duplicate-event', 'run', 1, "
                    "'duplicate', 'ready', 'document_qa', 1, '{}', :now)"
                ),
                {"now": now},
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_runs SET output_hash='changed' WHERE id='run'")
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_runs SET source_hash='changed' WHERE id='run'")
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_work_items SET output_hash='changed' WHERE id='item'")
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_work_items SET input_hash='changed' WHERE id='item'")
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_events SET error_code='edited' WHERE id='event'")
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("DELETE FROM generation_events WHERE id='event'"))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("DELETE FROM generation_work_items WHERE id='item'"))
        with pytest.raises(IntegrityError, match="immutable"), connection.begin_nested():
            connection.execute(text("DELETE FROM generation_work_items WHERE id='transition-item'"))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("DELETE FROM generation_runs WHERE id='run'"))
        with pytest.raises(IntegrityError, match="immutable"), connection.begin_nested():
            connection.execute(text("DELETE FROM generation_runs WHERE id='ready-no-children'"))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("DELETE FROM generation_builds WHERE id='build'"))

    engine.dispose()


def test_migration_downgrade_removes_runtime_objects() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        metadata = MetaData()
        Table("users", metadata, Column("id", String, primary_key=True))
        Table("path_lessons", metadata, Column("id", String, primary_key=True))
        metadata.create_all(connection)

        migration = _migration_module()
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.downgrade()

        runtime_tables = {
            name
            for name in sa.inspect(connection).get_table_names()
            if name.startswith("generation_")
        }
        assert runtime_tables == set()

    engine.dispose()


def test_integrity_migration_guards_work_item_admission_and_run_ready() -> None:
    engine = create_engine("sqlite://")
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata = MetaData()
        Table("users", metadata, Column("id", String, primary_key=True))
        Table("path_lessons", metadata, Column("id", String, primary_key=True))
        metadata.create_all(connection)
        connection.execute(text("INSERT INTO users (id) VALUES ('owner')"))
        connection.execute(text("INSERT INTO path_lessons (id) VALUES ('lesson')"))

        with Operations.context(MigrationContext.configure(connection)):
            _migration_module().upgrade()
            integrity_migration = _integrity_migration_module()
            integrity_migration.upgrade()

        connection.execute(
            text(
                "INSERT INTO generation_builds (id, path_lesson_id, owner_user_id, created_at) "
                "VALUES ('build', 'lesson', 'owner', :now)"
            ),
            {"now": now},
        )

        def insert_run(run_id: str, status: str = "queued") -> None:
            connection.execute(
                text(
                    "INSERT INTO generation_runs (id, build_id, run_type, owner_user_id, status, "
                    "stage, attempt, source_artifact_type, source_artifact_id, source_revision, "
                    "source_hash, output_artifact_type, output_artifact_id, output_revision, "
                    "output_hash, request_key, created_at, updated_at) VALUES (:id, 'build', "
                    "'shared_document', 'owner', :status, 'stage', 1, 'source', 'source-1', 1, "
                    "'source-hash', :output_type, :output_id, :output_revision, :output_hash, "
                    ":request_key, :now, :now)"
                ),
                {
                    "id": run_id,
                    "status": status,
                    "output_type": "doc" if status == "ready" else None,
                    "output_id": f"doc-{run_id}" if status == "ready" else None,
                    "output_revision": 1 if status == "ready" else None,
                    "output_hash": "ready-hash" if status == "ready" else None,
                    "request_key": f"request-{run_id}",
                    "now": now,
                },
            )

        def insert_item(item_id: str, run_id: str, status: str = "queued") -> None:
            ready_values = "'{}', 'item-hash'," if status == "ready" else "NULL, NULL,"
            connection.execute(
                text(
                    "INSERT INTO generation_work_items (id, run_id, item_key, stage, status, "
                    "attempt, max_attempts, input_hash, definition_hash, output_json, output_hash, "
                    "created_at, updated_at) VALUES (:id, :run_id, :item_key, 'stage', :status, "
                    f"1, 1, 'input', 'definition', {ready_values} :now, :now)"
                ),
                {
                    "id": item_id,
                    "run_id": run_id,
                    "item_key": item_id,
                    "status": status,
                    "now": now,
                },
            )

        insert_run("zero-child")
        with (
            pytest.raises(IntegrityError, match="ready generation run requires work items"),
            connection.begin_nested(),
        ):
            connection.execute(
                text(
                    "UPDATE generation_runs SET status='ready', output_artifact_type='doc', "
                    "output_artifact_id='doc-0', output_revision=1, output_hash='hash-0' "
                    "WHERE id='zero-child'"
                )
            )

        insert_run("unfinished-child")
        insert_item("unfinished-item", "unfinished-child")
        with pytest.raises(IntegrityError, match="all work items ready"), connection.begin_nested():
            connection.execute(
                text(
                    "UPDATE generation_runs SET status='ready', output_artifact_type='doc', "
                    "output_artifact_id='doc-1', output_revision=1, output_hash='hash-1' "
                    "WHERE id='unfinished-child'"
                )
            )
        connection.execute(
            text(
                "UPDATE generation_work_items SET status='ready', output_json='[1,2,3]', "
                "output_hash='item-hash' WHERE id='unfinished-item'"
            )
        )
        connection.execute(
            text(
                "UPDATE generation_runs SET status='ready', output_artifact_type='doc', "
                "output_artifact_id='doc-1', output_revision=1, output_hash='hash-1' "
                "WHERE id='unfinished-child'"
            )
        )

        insert_run("cancelled-run", "cancelled")
        insert_run("failed-run", "failed_terminal")
        for item_id, run_id in (
            ("late-ready-item", "unfinished-child"),
            ("late-cancelled-item", "cancelled-run"),
            ("late-failed-item", "failed-run"),
        ):
            with pytest.raises(IntegrityError, match="active run"), connection.begin_nested():
                insert_item(item_id, run_id)

        with pytest.raises(IntegrityError, match="requires work items"), connection.begin_nested():
            insert_run("inserted-ready-run", "ready")

        triggers = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='trigger'")
            )
        }
        assert "trg_generation_work_items_active_run_insert" in triggers
        assert "trg_generation_runs_ready_requires_items_insert" in triggers
        assert "trg_generation_runs_ready_requires_items_update" in triggers
        assert "trg_generation_events_no_delete" in triggers
        assert "trg_generation_runs_ready_immutable" in triggers

        with Operations.context(MigrationContext.configure(connection)):
            integrity_migration.downgrade()
        remaining = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='trigger'")
            )
        }
        assert not (triggers & remaining) - {
            "trg_generation_events_no_delete",
            "trg_generation_events_no_update",
            "trg_generation_runs_ready_immutable",
            "trg_generation_work_items_ready_immutable",
            "trg_generation_runs_ready_no_delete",
            "trg_generation_work_items_ready_no_delete",
        }

    engine.dispose()
