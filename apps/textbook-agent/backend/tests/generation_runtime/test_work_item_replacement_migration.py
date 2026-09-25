from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import IntegrityError


def _load_migration(filename: str):
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "infra"
        / "database"
        / "migrations"
        / "versions"
        / filename
    )
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(connection, run_id: str, *, status: str = "running") -> None:
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    connection.execute(
        text(
            "INSERT INTO generation_runs (id, build_id, run_type, owner_user_id, status, stage, "
            "attempt, source_artifact_type, source_artifact_id, source_revision, source_hash, "
            "request_key, created_at, updated_at) VALUES (:id, 'build', 'shared_document', "
            "'owner', :status, 'document_qa', 1, 'teaching_plan', 'plan', 1, 'source-hash', "
            ":request_key, :now, :now)"
        ),
        {"id": run_id, "status": status, "request_key": f"request-{run_id}", "now": now},
    )


def _item(
    connection,
    item_id: str,
    run_id: str,
    *,
    status: str = "queued",
    replaces: str | None = None,
    stage: str = "section_writing",
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    connection.execute(
        text(
            "INSERT INTO generation_work_items (id, run_id, replaces_work_item_id, item_key, "
            "stage, status, attempt, max_attempts, input_hash, definition_hash, output_json, "
            "output_hash, error_class, recovery_action, created_at, updated_at) VALUES "
            "(:id, :run_id, :replaces, :item_key, :stage, :status, 1, 3, 'input-hash', "
            "'definition-hash', :output_json, :output_hash, :error_class, :recovery, :now, :now)"
        ),
        {
            "id": item_id,
            "run_id": run_id,
            "replaces": replaces,
            "item_key": item_id,
            "stage": stage,
            "status": status,
            "output_json": "{}" if status == "ready" else None,
            "output_hash": "output-hash" if status == "ready" else None,
            "error_class": "validation" if status == "failed_recoverable" else None,
            "recovery": "retry" if status == "failed_recoverable" else None,
            "now": now,
        },
    )


def _migrated_connection():
    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    metadata = MetaData()
    Table("users", metadata, Column("id", String, primary_key=True))
    Table("path_lessons", metadata, Column("id", String, primary_key=True))
    metadata.create_all(connection)
    connection.execute(text("INSERT INTO users (id) VALUES ('owner')"))
    connection.execute(text("INSERT INTO path_lessons (id) VALUES ('lesson')"))
    with Operations.context(MigrationContext.configure(connection)):
        _load_migration("20260924_0043_generation_runtime.py").upgrade()
        _load_migration("20260924_0044_generation_runtime_integrity_guards.py").upgrade()
        _load_migration("20260925_0046_generation_work_item_replacements.py").upgrade()
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    connection.execute(
        text(
            "INSERT INTO generation_builds (id, path_lesson_id, owner_user_id, created_at) "
            "VALUES ('build', 'lesson', 'owner', :now)"
        ),
        {"now": now},
    )
    return engine, connection


def test_replacement_migration_guards_lineage_active_leaves_and_ready() -> None:
    engine, connection = _migrated_connection()
    try:
        _run(connection, "empty-run")
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_runs SET status='ready' WHERE id='empty-run'")
            )
        _run(connection, "run-a")
        _item(connection, "old-ready", "run-a", status="ready")
        _item(connection, "replacement", "run-a", replaces="old-ready")

        # The predecessor remains immutable and the new leaf blocks whole-Run ready.
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_work_items SET output_hash='mutated' WHERE id='old-ready'")
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "UPDATE generation_runs SET status='ready', output_artifact_type='shared_document', "
                    "output_artifact_id='doc', output_revision=1, output_hash='doc-hash' "
                    "WHERE id='run-a'"
                )
            )

        _item(connection, "other-ready", "run-a", status="ready")
        with pytest.raises(IntegrityError), connection.begin_nested():
            _item(connection, "duplicate-replacement", "run-a", replaces="old-ready")

        # A link cannot cross Runs, change stages, or replace a live/running item.
        _run(connection, "run-b")
        with pytest.raises(IntegrityError), connection.begin_nested():
            _item(connection, "cross-run", "run-b", replaces="old-ready")
        with pytest.raises(IntegrityError), connection.begin_nested():
            _item(
                connection, "wrong-stage", "run-a", replaces="other-ready", stage="media_generation"
            )
        _item(connection, "live", "run-b", status="running")
        with pytest.raises(IntegrityError), connection.begin_nested():
            _item(connection, "replace-live", "run-b", replaces="live")

        # Readiness is allowed when every active leaf is ready, even with immutable history.
        connection.execute(
            text(
                "UPDATE generation_work_items SET status='ready', output_json='[]', "
                "output_hash='replacement-hash' WHERE id='replacement'"
            )
        )
        connection.execute(
            text(
                "UPDATE generation_runs SET status='ready', output_artifact_type='shared_document', "
                "output_artifact_id='doc', output_revision=1, output_hash='doc-hash' "
                "WHERE id='run-a'"
            )
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM generation_work_items item WHERE item.run_id='run-a' "
                    "AND NOT EXISTS (SELECT 1 FROM generation_work_items successor "
                    "WHERE successor.replaces_work_item_id=item.id) AND item.status='ready'"
                )
            )
            == 2
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            _item(connection, "late-after-ready", "run-a")
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("DELETE FROM generation_work_items WHERE id='old-ready'"))
    finally:
        connection.close()
        engine.dispose()


def test_recoverable_run_reopens_only_for_linked_replacement() -> None:
    engine, connection = _migrated_connection()
    try:
        _run(connection, "recoverable")
        _item(connection, "failed", "recoverable", status="failed_recoverable")
        connection.execute(
            text("UPDATE generation_runs SET status='failed_recoverable' WHERE id='recoverable'")
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_runs SET status='queued' WHERE id='recoverable'")
            )
        _item(connection, "repaired", "recoverable", replaces="failed")
        connection.execute(
            text("UPDATE generation_runs SET status='queued' WHERE id='recoverable'")
        )
        assert (
            connection.scalar(text("SELECT status FROM generation_runs WHERE id='recoverable'"))
            == "queued"
        )

        _run(connection, "terminal", status="failed_terminal")
        with pytest.raises(IntegrityError), connection.begin_nested():
            _item(connection, "terminal-add", "terminal")
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_runs SET status='running' WHERE id='terminal'")
            )
        _run(connection, "cancelled", status="cancelled")
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_runs SET status='queued' WHERE id='cancelled'")
            )
    finally:
        connection.close()
        engine.dispose()


def test_recoverable_run_reopens_for_event_backed_targeted_retry() -> None:
    engine, connection = _migrated_connection()
    try:
        _run(connection, "retry-run")
        _item(connection, "retry-item", "retry-run")
        connection.execute(
            text(
                "UPDATE generation_work_items SET status='failed_recoverable' WHERE id='retry-item'"
            )
        )
        connection.execute(
            text("UPDATE generation_runs SET status='failed_recoverable' WHERE id='retry-run'")
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE generation_runs SET status='queued' WHERE id='retry-run'")
            )

        connection.execute(
            text(
                "UPDATE generation_work_items SET status='queued', attempt=2, error_code=NULL, "
                "error_class=NULL, recovery_action=NULL WHERE id='retry-item'"
            )
        )
        connection.execute(
            text(
                "INSERT INTO generation_events (id, run_id, work_item_id, seq, event_type, status, "
                "stage, attempt, safe_payload_json, created_at) VALUES ('retry-event', 'retry-run', "
                "'retry-item', 1, 'work_item_retry_queued', 'queued', 'document_qa', 2, '{}', CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(text("UPDATE generation_runs SET status='queued' WHERE id='retry-run'"))
        assert (
            connection.scalar(text("SELECT status FROM generation_runs WHERE id='retry-run'"))
            == "queued"
        )
    finally:
        connection.close()
        engine.dispose()


def test_replacement_migration_downgrade_refuses_to_delete_lineage() -> None:
    engine, connection = _migrated_connection()
    try:
        _run(connection, "run")
        _item(connection, "prior", "run", status="ready")
        _item(connection, "next", "run", replaces="prior")
        migration = _load_migration("20260925_0046_generation_work_item_replacements.py")
        with (
            pytest.raises(RuntimeError, match="replacement lineage exists"),
            connection.begin_nested(),
            Operations.context(MigrationContext.configure(connection)),
        ):
            migration.downgrade()
    finally:
        connection.close()
        engine.dispose()
