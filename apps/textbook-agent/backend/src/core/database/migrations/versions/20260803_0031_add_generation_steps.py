"""add generation_steps table and backfill briefs from chunked_state_json

Revision ID: 20260803_0031
Revises: 20260803_0030

Migration choice: backfill. Existing generations with section_briefs in
chunked_state_json get brief step rows so in-flight stage-2 work is not orphaned.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260803_0031"
down_revision = "20260803_0030"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    op.create_table(
        "generation_steps",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("generation_id", sa.String(), nullable=False),
        sa.Column("part_id", sa.String(), nullable=False),
        sa.Column("variant_id", sa.String(), nullable=False, server_default="everyone"),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="lesson"),
        sa.Column("payload", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "generation_id",
            "part_id",
            "variant_id",
            "step",
            name="uq_generation_steps_part_variant_step",
        ),
    )
    op.create_index(
        "ix_generation_steps_generation_id",
        "generation_steps",
        ["generation_id"],
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, chunked_state_json FROM generations "
            "WHERE chunked_state_json IS NOT NULL"
        )
    ).fetchall()

    steps = sa.table(
        "generation_steps",
        sa.column("id", sa.String),
        sa.column("generation_id", sa.String),
        sa.column("part_id", sa.String),
        sa.column("variant_id", sa.String),
        sa.column("step", sa.String),
        sa.column("kind", sa.String),
        sa.column("payload", _json_type()),
        sa.column("created_at", sa.DateTime),
    )
    now = _utcnow()
    batch: list[dict] = []
    for generation_id, raw_state in rows:
        if raw_state is None:
            continue
        if isinstance(raw_state, str):
            try:
                state = json.loads(raw_state)
            except json.JSONDecodeError:
                continue
        elif isinstance(raw_state, dict):
            state = raw_state
        else:
            continue
        briefs = state.get("section_briefs") or {}
        if not isinstance(briefs, dict):
            continue
        for part_id, payload in briefs.items():
            if payload is None or not isinstance(payload, dict):
                continue
            batch.append(
                {
                    "id": str(uuid.uuid4()),
                    "generation_id": generation_id,
                    "part_id": str(part_id),
                    "variant_id": "everyone",
                    "step": "brief",
                    "kind": "lesson",
                    "payload": payload,
                    "created_at": now,
                }
            )
    if batch:
        op.bulk_insert(steps, batch)


def downgrade() -> None:
    op.drop_index("ix_generation_steps_generation_id", table_name="generation_steps")
    op.drop_table("generation_steps")
