"""make Component Lectio Builder opens idempotent

Revision ID: 20260905_0034
Revises: 20260904_0033
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260905_0034"
down_revision = "20260904_0033"
branch_labels = None
depends_on = None


INDEX_NAME = "uq_editable_lessons_component_generation"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "editable_lessons",
        ["user_id", "source_generation_id"],
        unique=True,
        postgresql_where=sa.text("source_type = 'component_lectio'"),
        sqlite_where=sa.text("source_type = 'component_lectio'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="editable_lessons")
