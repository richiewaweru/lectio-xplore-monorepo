"""add path shape deviations

Revision ID: 20260801_0025
Revises: 20260801_0024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260801_0025"
down_revision = "20260801_0024"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "lesson_provenance",
        sa.Column("deviations_requested", _json_type(), nullable=True),
    )
    op.add_column(
        "lesson_provenance",
        sa.Column("deviations_approved", _json_type(), nullable=True),
    )
    op.create_table(
        "path_lesson_deviations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "path_lesson_id",
            sa.String(),
            sa.ForeignKey("path_lessons.id"),
            nullable=False,
        ),
        sa.Column("skeleton_id", sa.String(), nullable=False),
        sa.Column("skeleton_version", sa.Integer(), nullable=False),
        sa.Column("lesson_mode", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("target_slot", sa.String(), nullable=False),
        sa.Column("replacement_slot", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending_teacher",
        ),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "ix_path_lesson_deviations_path_lesson_id",
        "path_lesson_deviations",
        ["path_lesson_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_path_lesson_deviations_path_lesson_id",
        table_name="path_lesson_deviations",
    )
    op.drop_table("path_lesson_deviations")
    op.drop_column("lesson_provenance", "deviations_approved")
    op.drop_column("lesson_provenance", "deviations_requested")
