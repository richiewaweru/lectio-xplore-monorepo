"""Store per-lesson "Mark as fine" dismissals for Issues-tab advisories.

Revision ID: 20261007_0051
Revises: 20261006_0050

Additive only. A row dismisses one advisory (``issue_id``) for one lesson path
within one ``scope_key`` (realization output id + shared-document run id), so a
regenerated output or document starts with no dismissals.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261007_0051"
down_revision = "20261006_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_issue_dismissals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("path_lesson_id", sa.String(), sa.ForeignKey("path_lessons.id"), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("issue_id", sa.String(), nullable=False),
        sa.Column("scope_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "path_lesson_id",
            "path",
            "issue_id",
            "scope_key",
            name="uq_lesson_issue_dismissals_scope",
        ),
    )
    with op.batch_alter_table("lesson_issue_dismissals") as batch:
        batch.create_index(
            "ix_lesson_issue_dismissals_lesson_path", ["path_lesson_id", "path"]
        )


def downgrade() -> None:
    with op.batch_alter_table("lesson_issue_dismissals") as batch:
        batch.drop_index("ix_lesson_issue_dismissals_lesson_path")
    op.drop_table("lesson_issue_dismissals")
