"""Guard the Alembic revision graph.

Two migration files with the same revision id and parent make Alembic report
multiple heads, and startup migrations then abort and the healthcheck never
passes. These tests fail before that can reach a deploy.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]
VERSIONS = BACKEND / "src" / "infra" / "database" / "migrations" / "versions"
_REVISION = re.compile(r'^revision\s*=\s*"([^"]+)"', re.MULTILINE)


def _script_directory() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(VERSIONS.parent))
    return ScriptDirectory.from_config(config)


def test_no_two_migration_files_share_a_revision_id() -> None:
    ids = [
        match.group(1)
        for path in sorted(VERSIONS.glob("*.py"))
        if (match := _REVISION.search(path.read_text(encoding="utf-8")))
    ]
    duplicates = sorted(rev for rev, count in Counter(ids).items() if count > 1)
    assert not duplicates, f"duplicate migration revision ids: {duplicates}"


def test_alembic_has_a_single_head() -> None:
    heads = _script_directory().get_heads()
    assert len(heads) == 1, f"multiple Alembic heads: {heads}"


def _run(module_name: str, direction: str, connection: sa.Connection) -> None:
    script = _script_directory().get_revision(module_name).module
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(script, direction)()


def test_new_migrations_can_be_rerun_after_a_partial_apply() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE path_lessons (id VARCHAR PRIMARY KEY)"))
        # Half-applied: one mode column already exists before the migration runs.
        connection.execute(sa.text("ALTER TABLE path_lessons ADD COLUMN lesson_mode VARCHAR"))
        for revision in ("20261014_0052", "20261014_0053"):
            _run(revision, "upgrade", connection)
            _run(revision, "upgrade", connection)
        columns = {c["name"] for c in sa.inspect(connection).get_columns("path_lessons")}
        assert {"lesson_mode", "lesson_mode_reason", "lesson_mode_source"} <= columns
        assert "interest_messages" in sa.inspect(connection).get_table_names()

        for revision in ("20261014_0053", "20261014_0052"):
            _run(revision, "downgrade", connection)
            _run(revision, "downgrade", connection)
        columns = {c["name"] for c in sa.inspect(connection).get_columns("path_lessons")}
        assert not {"lesson_mode", "lesson_mode_reason", "lesson_mode_source"} & columns
        assert "interest_messages" not in sa.inspect(connection).get_table_names()
