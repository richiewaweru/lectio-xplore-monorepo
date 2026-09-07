"""add prompt overrides for teacher-editable prompt overlay

Revision ID: 20260803_0029
Revises: 20260801_0028
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260803_0029"
down_revision = "20260801_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_overrides",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("prompt_id", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_prompt_overrides_user_id", "prompt_overrides", ["user_id"])
    op.create_unique_constraint(
        "uq_prompt_overrides_user_prompt",
        "prompt_overrides",
        ["user_id", "prompt_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_prompt_overrides_user_prompt", "prompt_overrides", type_="unique"
    )
    op.drop_index("ix_prompt_overrides_user_id", table_name="prompt_overrides")
    op.drop_table("prompt_overrides")
