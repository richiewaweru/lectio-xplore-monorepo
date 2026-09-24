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
