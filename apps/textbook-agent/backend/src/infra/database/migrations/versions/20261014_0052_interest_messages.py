"""Add interest_messages for the demo interest-capture form.

Revision ID: 20261014_0052
Revises: 20261007_0051

Additive only. Visitors leave a note plus an email or phone; no foreign keys so
notes survive learner deletion.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261014_0052"
down_revision = "20261007_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interest_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("learner_id", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("interest_messages") as batch:
        batch.create_index("ix_interest_messages_created_at", ["created_at"])


def downgrade() -> None:
    with op.batch_alter_table("interest_messages") as batch:
        batch.drop_index("ix_interest_messages_created_at")
    op.drop_table("interest_messages")
