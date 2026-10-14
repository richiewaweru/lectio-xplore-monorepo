"""Add planner-assigned lesson mode to path lessons.

Revision ID: 20261014_0053
Revises: 20261014_0052

Additive only. ``lesson_mode`` is nullable with no backfill: a null value means
"first_exposure" at read time. ``lesson_mode_source`` records whether the mode
came from the path planner or a teacher edit.

Renumbered from 0052, which collided with the interest_messages migration.
Columns are checked before they are added or dropped so a half-applied state
does not break the next upgrade.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261014_0053"
down_revision = "20261014_0052"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("lesson_mode", sa.String()),
    ("lesson_mode_reason", sa.Text()),
    ("lesson_mode_source", sa.String()),
)


def _existing_columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("path_lessons")}


def upgrade() -> None:
    existing = _existing_columns()
    missing = [(name, kind) for name, kind in _COLUMNS if name not in existing]
    if not missing:
        return
    with op.batch_alter_table("path_lessons") as batch:
        for name, kind in missing:
            batch.add_column(sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    existing = _existing_columns()
    present = [name for name, _ in reversed(_COLUMNS) if name in existing]
    if not present:
        return
    with op.batch_alter_table("path_lessons") as batch:
        for name in present:
            batch.drop_column(name)
