"""add editable lessons table for builder persistence

Revision ID: 20260513_0013
Revises: 20260505_0012
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260513_0013"
down_revision = "20260505_0012"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "editable_lessons",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("source_generation_id", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False, server_default="manual"),
        sa.Column("title", sa.String(), nullable=False, server_default="Untitled lesson"),
        sa.Column("document_json", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_editable_lessons_user", "editable_lessons", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_editable_lessons_user", table_name="editable_lessons")
    op.drop_table("editable_lessons")
