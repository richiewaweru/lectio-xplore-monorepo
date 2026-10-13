"""Add planner-assigned lesson mode to path lessons.

Revision ID: 20261014_0052
Revises: 20261007_0051

Additive only. ``lesson_mode`` is nullable with no backfill: a null value means
"first_exposure" at read time. ``lesson_mode_source`` records whether the mode
came from the path planner or a teacher edit.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261014_0052"
down_revision = "20261007_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("path_lessons") as batch:
        batch.add_column(sa.Column("lesson_mode", sa.String(), nullable=True))
        batch.add_column(sa.Column("lesson_mode_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("lesson_mode_source", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("path_lessons") as batch:
        batch.drop_column("lesson_mode_source")
        batch.drop_column("lesson_mode_reason")
        batch.drop_column("lesson_mode")
