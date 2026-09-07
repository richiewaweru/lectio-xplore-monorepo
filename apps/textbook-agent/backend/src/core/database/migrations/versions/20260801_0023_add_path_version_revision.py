"""add path version revision

Revision ID: 20260801_0023
Revises: 20260731_0022
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260801_0023"
down_revision = "20260731_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "path_versions",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("path_versions", "revision")
