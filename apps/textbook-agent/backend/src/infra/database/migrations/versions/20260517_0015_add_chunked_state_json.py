"""add chunked_state_json to generations

Revision ID: 20260517_0015
Revises: 20260515_0014
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260517_0015"
down_revision = "20260515_0014"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column(
            "chunked_state_json",
            _json_type(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("generations", "chunked_state_json")

