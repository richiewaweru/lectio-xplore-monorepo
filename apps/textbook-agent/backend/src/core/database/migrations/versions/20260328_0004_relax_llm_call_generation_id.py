"""relax llm_call generation id

Revision ID: 20260328_0004
Revises: 20260328_0003
Create Date: 2026-03-28 19:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0004"
down_revision = "20260328_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("llm_calls") as batch_op:
        batch_op.alter_column(
            "generation_id",
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("llm_calls") as batch_op:
        batch_op.alter_column(
            "generation_id",
            existing_type=sa.String(),
            nullable=False,
        )
