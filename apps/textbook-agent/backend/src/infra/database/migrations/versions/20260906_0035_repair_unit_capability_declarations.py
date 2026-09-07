"""repair a stamped-head database missing capability declarations.

Some campaign databases were stamped at ``20260905_0034`` even though the
``20260806_0032`` table was absent.  Alembic consequently had no work to do,
and the first Units write failed when SQLAlchemy flushed a capability
declaration.  This additive repair makes the schema self-healing on the next
upgrade while preserving the original migration's backfill behaviour.

The downgrade is intentionally a no-op.  This migration may have created the
table in a database that was incorrectly stamped, and dropping it during a
rollback would destroy declarations that did not exist before the repair.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "20260906_0035"
down_revision = "20260905_0034"
branch_labels = None
depends_on = None

TABLE_NAME = "unit_capability_declarations"
UNIT_INDEX_NAME = "ix_unit_capability_declarations_unit_id"
UNIQUE_INDEX_NAME = "uq_unit_capability_declarations_unit_lower_label"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _create_table() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def _backfill() -> None:
    """Restore the rows that migration 0032 would have created."""
    bind = op.get_bind()
    units = bind.execute(
        sa.text("SELECT id, starting_knowledge, active_path_version_id FROM units")
    ).mappings().all()
    scopes = {
        row["unit_id"]: row["assumed_prerequisites"]
        for row in bind.execute(
            sa.text("SELECT unit_id, assumed_prerequisites FROM unit_scope_contracts")
        ).mappings()
    }

    now = _utcnow()
    for unit in units:
        unit_id = unit["id"]
        seen: set[str] = set()
        labels: list[tuple[str, str, bool]] = [
            (label, "teacher_intake", True)
            for label in _as_list(unit["starting_knowledge"])
        ]
        labels.extend(
            (label, "teacher_intake", True)
            for label in _as_list(scopes.get(unit_id))
        )
        for label, source, confirmed in labels:
            folded = label.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            bind.execute(
                sa.text(
                    f"""
                    INSERT INTO {TABLE_NAME}
                        (id, unit_id, label, source, confirmed, confirmed_at, created_at)
                    VALUES
                        (:id, :unit_id, :label, :source, :confirmed, :confirmed_at, :created_at)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "unit_id": unit_id,
                    "label": label,
                    "source": source,
                    "confirmed": confirmed,
                    "confirmed_at": now,
                    "created_at": now,
                },
            )

        active_version_id = unit["active_path_version_id"]
        if not active_version_id:
            continue
        lessons = bind.execute(
            sa.text(
                """
                SELECT external_prerequisites
                FROM path_lessons
                WHERE path_version_id = :version_id
                ORDER BY position
                """
            ),
            {"version_id": active_version_id},
        ).mappings().all()
        for lesson in lessons:
            for label in _as_list(lesson["external_prerequisites"]):
                folded = label.casefold()
                if folded in seen:
                    continue
                seen.add(folded)
                bind.execute(
                    sa.text(
                        f"""
                        INSERT INTO {TABLE_NAME}
                            (id, unit_id, label, source, confirmed, confirmed_at, created_at)
                        VALUES
                            (:id, :unit_id, :label, 'path_planner', false, NULL, :created_at)
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "unit_id": unit_id,
                        "label": label,
                        "created_at": now,
                    },
                )


def upgrade() -> None:
    bind = op.get_bind()
    table_created = not sa.inspect(bind).has_table(TABLE_NAME)
    if table_created:
        _create_table()
        _backfill()

    # ``IF NOT EXISTS`` also repairs a partially restored table without
    # attempting to recreate its already-present indexes.
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS {UNIT_INDEX_NAME} "
            f"ON {TABLE_NAME} (unit_id)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {UNIQUE_INDEX_NAME} "
            f"ON {TABLE_NAME} (unit_id, lower(label))"
        )
    )


def downgrade() -> None:
    # See module docstring: this repair must never delete recovered data.
    return None
