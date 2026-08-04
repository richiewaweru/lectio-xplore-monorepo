"""add teacher profile fields

Revision ID: 20260406_0008
Revises: 20260401_0007
Create Date: 2026-04-06 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260406_0008"
down_revision = "20260401_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("student_profiles") as batch_op:
        batch_op.add_column(
            sa.Column("teacher_role", sa.String(), nullable=False, server_default="teacher")
        )
        batch_op.add_column(
            sa.Column("subjects", sa.Text(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column(
                "default_grade_band",
                sa.String(),
                nullable=False,
                server_default="high_school",
            )
        )
        batch_op.add_column(
            sa.Column(
                "default_audience_description",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column("curriculum_framework", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("classroom_context", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("planning_goals", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("school_or_org_name", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("delivery_preferences", sa.Text(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("student_profiles") as batch_op:
        batch_op.drop_column("delivery_preferences")
        batch_op.drop_column("school_or_org_name")
        batch_op.drop_column("planning_goals")
        batch_op.drop_column("classroom_context")
        batch_op.drop_column("curriculum_framework")
        batch_op.drop_column("default_audience_description")
        batch_op.drop_column("default_grade_band")
        batch_op.drop_column("subjects")
        batch_op.drop_column("teacher_role")
