"""add generation json storage

Revision ID: 20260328_0002
Revises: 20260328_0001
Create Date: 2026-03-28 00:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260328_0002"
down_revision = "20260328_0001"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    op.add_column("generations", sa.Column("document_json", _json_type(), nullable=True))
    op.add_column("generations", sa.Column("report_json", _json_type(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("generations") as batch_op:
        batch_op.drop_column("report_json")
        batch_op.drop_column("document_json")
