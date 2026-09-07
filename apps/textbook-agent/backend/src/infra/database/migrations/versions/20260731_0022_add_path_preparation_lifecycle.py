"""add path preparation lifecycle

Revision ID: 20260731_0022
Revises: 20260731_0021
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260731_0022"
down_revision = "20260731_0021"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("lesson_provenance", sa.Column("path_lesson_revision", sa.Integer(), nullable=True))
    op.add_column("lesson_provenance", sa.Column("lesson_mode", sa.String(), nullable=True))
    op.add_column("lesson_provenance", sa.Column("group_ids", _json_type(), nullable=True))
    op.add_column("lesson_provenance", sa.Column("preparation_key", sa.String(), nullable=True))
    op.add_column("lesson_provenance", sa.Column("supersedes_pack_id", sa.String(), nullable=True))
    op.add_column("lesson_provenance", sa.Column("regeneration_reason", sa.Text(), nullable=True))
    op.add_column("lesson_provenance", sa.Column("invalidated_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_lesson_provenance_preparation_key",
        "lesson_provenance",
        ["preparation_key"],
    )
    op.create_index(
        "ix_lesson_provenance_supersedes_pack_id",
        "lesson_provenance",
        ["supersedes_pack_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_provenance_supersedes_pack_id", table_name="lesson_provenance")
    op.drop_index("ix_lesson_provenance_preparation_key", table_name="lesson_provenance")
    op.drop_column("lesson_provenance", "invalidated_at")
    op.drop_column("lesson_provenance", "regeneration_reason")
    op.drop_column("lesson_provenance", "supersedes_pack_id")
    op.drop_column("lesson_provenance", "preparation_key")
    op.drop_column("lesson_provenance", "group_ids")
    op.drop_column("lesson_provenance", "lesson_mode")
    op.drop_column("lesson_provenance", "path_lesson_revision")
