from __future__ import annotations

import importlib.util
import json
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
        / "20260925_0045_shared_lesson_documents.py"
    )
    spec = importlib.util.spec_from_file_location("shared_lesson_document_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _document_json(title: str = "Photosynthesis") -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "id": "document-1",
            "revision": 1,
            "content_hash": "c" * 64,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 3,
            "teaching_plan_hash": "a" * 64,
            "title": title,
            "sections": [],
            "tasks": [],
            "provenance": {},
            "created_at": "2026-09-24T09:00:00+03:00",
            "diagnostics": [],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def test_migration_guards_shared_document_json_and_ready_rows() -> None:
    engine = create_engine("sqlite://")
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata = MetaData()
        Table("path_lessons", metadata, Column("id", String, primary_key=True))
        metadata.create_all(connection)
        connection.execute(text("INSERT INTO path_lessons (id) VALUES ('lesson-1')"))
        migration = _migration_module()
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        values = {
            "document_json": _document_json(),
            "now": now,
        }
        connection.execute(
            text(
                "INSERT INTO shared_lesson_documents "
                "(id, revision, path_lesson_id, teaching_plan_id, teaching_plan_revision, "
                "teaching_plan_hash, content_hash, document_json, status, created_at) "
                "VALUES ('document-1', 1, 'lesson-1', 'plan-1', 3, :plan_hash, :content_hash, "
                ":document_json, 'draft', :now)"
            ),
            {**values, "plan_hash": "a" * 64, "content_hash": "c" * 64},
        )

        with pytest.raises(IntegrityError, match="immutable"):
            with connection.begin_nested():
                connection.execute(
                    text(
                        "UPDATE shared_lesson_documents SET document_json=:document_json "
                        "WHERE id='document-1'"
                    ),
                    {"document_json": _document_json("Changed")},
                )

        connection.execute(
            text("UPDATE shared_lesson_documents SET status='ready' WHERE id='document-1'")
        )
        with pytest.raises(IntegrityError, match="immutable"):
            with connection.begin_nested():
                connection.execute(
                    text("UPDATE shared_lesson_documents SET status='draft' WHERE id='document-1'")
                )
        with pytest.raises(IntegrityError, match="immutable"):
            with connection.begin_nested():
                connection.execute(
                    text("DELETE FROM shared_lesson_documents WHERE id='document-1'")
                )

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "shared_lesson_documents" not in sa.inspect(connection).get_table_names()

    engine.dispose()
