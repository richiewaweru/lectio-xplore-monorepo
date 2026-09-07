"""add generation mode

Revision ID: 20260401_0007
Revises: 20260329_0006
Create Date: 2026-04-01 09:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260401_0007"
down_revision = "20260329_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("mode", sa.String(), nullable=False, server_default="balanced"),
    )


def downgrade() -> None:
    op.drop_column("generations", "mode")
