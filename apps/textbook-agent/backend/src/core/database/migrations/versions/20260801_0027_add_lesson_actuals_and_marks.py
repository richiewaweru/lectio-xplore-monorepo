"""add audited lesson actuals and aggregate marks

Revision ID: 20260801_0027
Revises: 20260801_0026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260801_0027"
down_revision = "20260801_0026"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "lesson_actuals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("unit_id", sa.String(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("path_version_id", sa.String(), sa.ForeignKey("path_versions.id"), nullable=False),
        sa.Column("path_lesson_id", sa.String(), sa.ForeignKey("path_lessons.id"), nullable=False),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("lesson_revision", sa.Integer(), nullable=False),
        sa.Column("objective_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("taught", sa.Boolean(), nullable=False),
        sa.Column("pace", sa.String(), nullable=False),
        sa.Column("established_concepts", _json_type(), nullable=False),
        sa.Column("unresolved_misconceptions", _json_type(), nullable=False),
        sa.Column("anchor_used", sa.Text(), nullable=True),
        sa.Column("teacher_note", sa.Text(), nullable=True),
        sa.Column("supersedes_actual_id", sa.String(), sa.ForeignKey("lesson_actuals.id"), nullable=True),
        sa.Column("recorded_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("path_lesson_id", "revision", name="uq_lesson_actual_revision"),
    )
    for name, column in (("unit_id", "unit_id"), ("path_version_id", "path_version_id"), ("path_lesson_id", "path_lesson_id"), ("owner_id", "owner_id")):
        op.create_index(f"ix_lesson_actuals_{name}", "lesson_actuals", [column])

    op.create_table(
        "marks_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("path_version_id", sa.String(), sa.ForeignKey("path_versions.id"), nullable=False),
        sa.Column("path_lesson_id", sa.String(), sa.ForeignKey("path_lessons.id"), nullable=False),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("lesson_revision", sa.Integer(), nullable=False),
        sa.Column("objective_hash", sa.String(), nullable=False),
        sa.Column("pack_id", sa.String(), nullable=False),
        sa.Column("group_id", sa.String(), sa.ForeignKey("unit_groups.id"), nullable=True),
        sa.Column("item_id", sa.String(), sa.ForeignKey("pack_items.id"), nullable=False),
        sa.Column("option_id", sa.String(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("misconception_id", sa.String(), nullable=True),
        sa.Column("recorded_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("submission_id", "item_id", "option_id", name="uq_marks_submission_item_option"),
    )
    for name in ("submission_id", "unit_id", "path_version_id", "path_lesson_id", "owner_id", "pack_id", "group_id", "item_id"):
        op.create_index(f"ix_marks_entries_{name}", "marks_entries", [name])


def downgrade() -> None:
    op.drop_table("marks_entries")
    op.drop_table("lesson_actuals")
