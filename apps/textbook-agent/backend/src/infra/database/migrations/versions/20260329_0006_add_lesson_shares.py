"""add lesson_shares

Revision ID: 20260329_0006
Revises: 20260328_0005
Create Date: 2026-03-29 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260329_0006"
down_revision = "20260328_0005"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "lesson_shares",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("document_json", _json_type(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("allow_download", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lesson_shares_expires_at", "lesson_shares", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lesson_shares_expires_at", table_name="lesson_shares")
    op.drop_table("lesson_shares")
