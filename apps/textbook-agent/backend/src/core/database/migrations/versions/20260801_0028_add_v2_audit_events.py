"""add persistent V2 mutation audit events

Revision ID: 20260801_0028
Revises: 20260801_0027
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260801_0028"
down_revision = "20260801_0027"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "v2_audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("actor_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("event_metadata", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for name in ("actor_id", "path", "status_code", "request_id", "created_at"):
        op.create_index(f"ix_v2_audit_events_{name}", "v2_audit_events", [name])


def downgrade() -> None:
    op.drop_table("v2_audit_events")
