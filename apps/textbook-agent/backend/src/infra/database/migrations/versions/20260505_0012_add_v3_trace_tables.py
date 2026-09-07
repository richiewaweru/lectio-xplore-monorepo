"""add v3 trace tables

Revision ID: 20260505_0012
Revises: 20260504_0011
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260505_0012"
down_revision = "20260504_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v3_trace_runs",
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("generation_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("template_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column(
            "report_json",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()),
                "postgresql",
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("trace_id"),
    )
    op.create_index(
        "ix_v3_trace_runs_generation_id",
        "v3_trace_runs",
        ["generation_id"],
        unique=True,
    )
    op.create_index("ix_v3_trace_runs_user_id", "v3_trace_runs", ["user_id"])
    op.create_index("ix_v3_trace_runs_status", "v3_trace_runs", ["status"])

    op.create_table(
        "v3_trace_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()),
                "postgresql",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["trace_id"], ["v3_trace_runs.trace_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_v3_trace_events_trace_id", "v3_trace_events", ["trace_id"])
    op.create_index("ix_v3_trace_events_phase", "v3_trace_events", ["phase"])
    op.create_index("ix_v3_trace_events_event_type", "v3_trace_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("v3_trace_events")
    op.drop_table("v3_trace_runs")
