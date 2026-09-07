"""add nullable class_notes column to units

Revision ID: 20260803_0030
Revises: 20260803_0029
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260803_0030"
down_revision = "20260803_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("units", sa.Column("class_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("units", "class_notes")
