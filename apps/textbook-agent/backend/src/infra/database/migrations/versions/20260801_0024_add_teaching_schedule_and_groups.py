"""add teaching schedule and unit groups

Revision ID: 20260801_0024
Revises: 20260801_0023
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260801_0024"
down_revision = "20260801_0023"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "units",
        sa.Column("groups_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "path_versions",
        sa.Column("schedule_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "teaching_periods",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "path_version_id",
            sa.String(),
            sa.ForeignKey("path_versions.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=True),
        sa.Column("teacher_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "path_version_id",
            "position",
            name="uq_teaching_period_path_position",
        ),
    )
    op.create_index(
        "ix_teaching_periods_path_version_id",
        "teaching_periods",
        ["path_version_id"],
    )
    op.create_table(
        "teaching_period_lessons",
        sa.Column(
            "teaching_period_id",
            sa.String(),
            sa.ForeignKey("teaching_periods.id"),
            primary_key=True,
        ),
        sa.Column(
            "path_lesson_id",
            sa.String(),
            sa.ForeignKey("path_lessons.id"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "teaching_period_id",
            "position",
            name="uq_teaching_period_lesson_position",
        ),
        sa.UniqueConstraint("path_lesson_id", name="uq_teaching_period_path_lesson"),
    )
    op.create_index(
        "ix_teaching_period_lessons_path_lesson_id",
        "teaching_period_lessons",
        ["path_lesson_id"],
    )
    op.create_table(
        "unit_groups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("unit_id", sa.String(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("profile", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("toggle_profile", _json_type(), nullable=False),
        sa.Column("voice", _json_type(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("unit_id", "profile", name="uq_unit_group_profile"),
    )
    op.create_index("ix_unit_groups_unit_id", "unit_groups", ["unit_id"])


def downgrade() -> None:
    op.drop_index("ix_unit_groups_unit_id", table_name="unit_groups")
    op.drop_table("unit_groups")
    op.drop_index(
        "ix_teaching_period_lessons_path_lesson_id",
        table_name="teaching_period_lessons",
    )
    op.drop_table("teaching_period_lessons")
    op.drop_index(
        "ix_teaching_periods_path_version_id",
        table_name="teaching_periods",
    )
    op.drop_table("teaching_periods")
    op.drop_column("path_versions", "schedule_revision")
    op.drop_column("units", "groups_revision")
