"""add generation heartbeat

Revision ID: 20260328_0005
Revises: 20260328_0004
Create Date: 2026-03-28 22:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0005"
down_revision = "20260328_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("generations") as batch_op:
        batch_op.add_column(sa.Column("last_heartbeat", sa.DateTime(), nullable=True))
        batch_op.create_index(
            "ix_generations_last_heartbeat",
            ["last_heartbeat"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("generations") as batch_op:
        batch_op.drop_index("ix_generations_last_heartbeat")
        batch_op.drop_column("last_heartbeat")
