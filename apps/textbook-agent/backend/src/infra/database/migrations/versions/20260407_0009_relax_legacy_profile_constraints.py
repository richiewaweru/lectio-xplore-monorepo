"""relax legacy learner profile constraints for teacher-profile rollout

Revision ID: 20260407_0009
Revises: 20260406_0008
Create Date: 2026-04-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260407_0009"
down_revision = "20260406_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("student_profiles") as batch_op:
        batch_op.alter_column("age", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column(
            "education_level",
            existing_type=sa.String(),
            nullable=True,
        )
        batch_op.alter_column(
            "learning_style",
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    op.execute("UPDATE student_profiles SET age = COALESCE(age, 18)")
    op.execute(
        "UPDATE student_profiles SET education_level = COALESCE(NULLIF(education_level, ''), 'high_school')"
    )
    op.execute(
        "UPDATE student_profiles SET learning_style = COALESCE(NULLIF(learning_style, ''), 'reading_writing')"
    )
    with op.batch_alter_table("student_profiles") as batch_op:
        batch_op.alter_column("age", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column(
            "education_level",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.alter_column(
            "learning_style",
            existing_type=sa.String(),
            nullable=False,
        )
