"""Add LearnRelease path revision and objective_hash provenance columns."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260906_0038"
down_revision = "20260906_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learn_releases", sa.Column("path_lesson_revision", sa.Integer(), nullable=True))
    op.add_column("learn_releases", sa.Column("objective_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("learn_releases", "objective_hash")
    op.drop_column("learn_releases", "path_lesson_revision")
