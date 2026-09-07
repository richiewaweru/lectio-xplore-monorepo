"""add optional class label to editable lessons

Revision ID: 20260727_0016
Revises: 20260517_0015
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260727_0016"
down_revision = "20260517_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("editable_lessons", sa.Column("class_label", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("editable_lessons", "class_label")
