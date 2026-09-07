"""add llm_calls telemetry table

Revision ID: 20260328_0003
Revises: 20260328_0002
Create Date: 2026-03-28 01:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260328_0003"
down_revision = "20260328_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("generation_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("caller", sa.String(), nullable=False),
        sa.Column("node", sa.String(), nullable=False),
        sa.Column("slot", sa.String(), nullable=False),
        sa.Column("family", sa.String(), nullable=True),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("endpoint_host", sa.String(), nullable=True),
        sa.Column("section_id", sa.String(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_llm_calls_trace_id"), "llm_calls", ["trace_id"])
    op.create_index(op.f("ix_llm_calls_generation_id"), "llm_calls", ["generation_id"])
    op.create_index(op.f("ix_llm_calls_user_id"), "llm_calls", ["user_id"])
    op.create_index(op.f("ix_llm_calls_caller"), "llm_calls", ["caller"])
    op.create_index(op.f("ix_llm_calls_node"), "llm_calls", ["node"])
    op.create_index(op.f("ix_llm_calls_slot"), "llm_calls", ["slot"])
    op.create_index(op.f("ix_llm_calls_family"), "llm_calls", ["family"])
    op.create_index(op.f("ix_llm_calls_model_name"), "llm_calls", ["model_name"])
    op.create_index(op.f("ix_llm_calls_endpoint_host"), "llm_calls", ["endpoint_host"])
    op.create_index(op.f("ix_llm_calls_section_id"), "llm_calls", ["section_id"])
    op.create_index(op.f("ix_llm_calls_status"), "llm_calls", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_calls_status"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_section_id"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_endpoint_host"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_model_name"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_family"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_slot"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_node"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_caller"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_user_id"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_generation_id"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_trace_id"), table_name="llm_calls")
    op.drop_table("llm_calls")
