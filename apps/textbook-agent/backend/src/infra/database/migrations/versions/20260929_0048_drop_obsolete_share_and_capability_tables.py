"""Drop obsolete lesson_shares and unit_capability_declarations tables (Phase 14).

Revision ID: 20260929_0048
Revises: 20260928_0047

``lesson_shares`` lost its only reader/writer when ``core/routes/shares.py``
was deleted (P13C); ``unit_capability_declarations`` has had no ORM model or
application reader/writer since the capability-declaration feature was
retired (only the historical repair migration 0035 references it). Neither
table has inbound foreign keys. A pg_dump backup precedes this migration in
the runbook.

Both drops are guarded because some databases never received
``unit_capability_declarations`` (see 0035). The downgrade recreates the
empty structures only; dropped rows are not restored (data loss accepted:
the tables are unused).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260929_0048"
down_revision = "20260928_0047"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("unit_capability_declarations"):
        op.drop_table("unit_capability_declarations")
    if _has_table("lesson_shares"):
        op.drop_table("lesson_shares")


def downgrade() -> None:
    if not _has_table("lesson_shares"):
        op.create_table(
            "lesson_shares",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("document_json", _json_type(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("allow_download", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_lesson_shares_expires_at", "lesson_shares", ["expires_at"], unique=False
        )
    if not _has_table("unit_capability_declarations"):
        op.create_table(
            "unit_capability_declarations",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("unit_id", sa.String(), nullable=False),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("confirmed", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_unit_capability_declarations_unit_id",
            "unit_capability_declarations",
            ["unit_id"],
            unique=False,
        )
