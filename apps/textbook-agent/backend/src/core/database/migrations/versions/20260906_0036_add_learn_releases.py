"""Add immutable learn_releases table for explicit Publish (Phase 05)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260906_0036"
down_revision = "20260906_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learn_releases",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("editable_lesson_id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("release_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("document_json", sa.JSON(), nullable=False),
        sa.Column("document_hash", sa.String(), nullable=False),
        sa.Column("source_generation_id", sa.String(), nullable=True),
        sa.Column("path_lesson_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="published"),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["editable_lesson_id"], ["editable_lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "editable_lesson_id",
            "release_number",
            name="uq_learn_releases_lesson_number",
        ),
    )
    op.create_index("ix_learn_releases_lesson_id", "learn_releases", ["editable_lesson_id"])
    op.create_index("ix_learn_releases_owner_user_id", "learn_releases", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_learn_releases_owner_user_id", table_name="learn_releases")
    op.drop_index("ix_learn_releases_lesson_id", table_name="learn_releases")
    op.drop_table("learn_releases")
