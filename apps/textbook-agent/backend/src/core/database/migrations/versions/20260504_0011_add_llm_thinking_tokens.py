"""add thinking_tokens to llm_calls

Revision ID: 20260504_0011
Revises: 20260501_0010
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260504_0011"
down_revision = "20260501_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("thinking_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_calls", "thinking_tokens")
