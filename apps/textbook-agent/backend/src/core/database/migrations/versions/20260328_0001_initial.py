"""initial database schema

Revision ID: 20260328_0001
Revises:
Create Date: 2026-03-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260328_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("picture_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "student_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("education_level", sa.String(), nullable=False),
        sa.Column("interests", sa.Text(), nullable=True),
        sa.Column("learning_style", sa.String(), nullable=False),
        sa.Column("preferred_notation", sa.String(), nullable=True),
        sa.Column("prior_knowledge", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("preferred_depth", sa.String(), nullable=True),
        sa.Column("learner_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_student_profiles_user_id"), "student_profiles", ["user_id"], unique=True)

    op.create_table(
        "generations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("document_path", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("requested_template_id", sa.String(), nullable=False),
        sa.Column("resolved_template_id", sa.String(), nullable=True),
        sa.Column("requested_preset_id", sa.String(), nullable=False),
        sa.Column("resolved_preset_id", sa.String(), nullable=True),
        sa.Column("section_count", sa.Integer(), nullable=True),
        sa.Column("quality_passed", sa.Boolean(), nullable=True),
        sa.Column("generation_time_seconds", sa.Float(), nullable=True),
        sa.Column("planning_spec_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_generations_user_id"), "generations", ["user_id"])
    op.create_index(op.f("ix_generations_error_type"), "generations", ["error_type"])
    op.create_index(op.f("ix_generations_error_code"), "generations", ["error_code"])
    op.create_index(
        op.f("ix_generations_requested_template_id"),
        "generations",
        ["requested_template_id"],
    )
    op.create_index(
        op.f("ix_generations_resolved_template_id"),
        "generations",
        ["resolved_template_id"],
    )
    op.create_index(
        op.f("ix_generations_requested_preset_id"),
        "generations",
        ["requested_preset_id"],
    )
    op.create_index(
        op.f("ix_generations_resolved_preset_id"),
        "generations",
        ["resolved_preset_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_generations_resolved_preset_id"), table_name="generations")
    op.drop_index(op.f("ix_generations_requested_preset_id"), table_name="generations")
    op.drop_index(op.f("ix_generations_resolved_template_id"), table_name="generations")
    op.drop_index(op.f("ix_generations_requested_template_id"), table_name="generations")
    op.drop_index(op.f("ix_generations_error_code"), table_name="generations")
    op.drop_index(op.f("ix_generations_error_type"), table_name="generations")
    op.drop_index(op.f("ix_generations_user_id"), table_name="generations")
    op.drop_table("generations")

    op.drop_index(op.f("ix_student_profiles_user_id"), table_name="student_profiles")
    op.drop_table("student_profiles")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
