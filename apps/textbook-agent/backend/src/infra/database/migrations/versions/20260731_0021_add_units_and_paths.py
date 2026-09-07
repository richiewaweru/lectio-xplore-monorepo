"""add units and path backend

Revision ID: 20260731_0021
Revises: 20260731_0020
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260731_0021"
down_revision = "20260731_0020"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "units",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("grade_level", sa.String(), nullable=False),
        sa.Column("curriculum_context", sa.Text(), nullable=True),
        sa.Column("destination_objective", sa.Text(), nullable=False),
        sa.Column("starting_knowledge", _json_type(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("active_path_version_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("owner_id", "subject", "grade_level", "active_path_version_id"):
        op.create_index(f"ix_units_{column}", "units", [column])

    op.create_table(
        "unit_scope_contracts",
        sa.Column("unit_id", sa.String(), sa.ForeignKey("units.id"), primary_key=True),
        sa.Column("must_establish", _json_type(), nullable=False),
        sa.Column("may_include", _json_type(), nullable=False),
        sa.Column("must_not_introduce", _json_type(), nullable=False),
        sa.Column("assumed_prerequisites", _json_type(), nullable=False),
        sa.Column("terminology", _json_type(), nullable=False),
        sa.Column("notation", sa.Text(), nullable=True),
    )
    op.create_table(
        "path_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("unit_id", sa.String(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("generated_by", sa.String(), nullable=False),
        sa.Column("source_plan_json", _json_type(), nullable=False),
        sa.Column("merge_critic_results", _json_type(), nullable=False),
        sa.Column("prerequisite_risks", _json_type(), nullable=False),
        sa.Column("forward_verified", sa.Boolean(), nullable=False),
        sa.Column("reaches_destination", sa.Boolean(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("unit_id", "version", name="uq_path_version_unit_version"),
    )
    op.create_index("ix_path_versions_unit_id", "path_versions", ["unit_id"])
    op.create_table(
        "path_lessons",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("path_version_id", sa.String(), sa.ForeignKey("path_versions.id"), nullable=False),
        sa.Column("concept_id", sa.String(), sa.ForeignKey("concepts.id"), nullable=False),
        sa.Column("concept_slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("objective_hash", sa.String(), nullable=False),
        sa.Column("external_prerequisites", _json_type(), nullable=False),
        sa.Column("opens_from", sa.Text(), nullable=True),
        sa.Column("must_establish", _json_type(), nullable=False),
        sa.Column("exclusions", _json_type(), nullable=False),
        sa.Column("primary_knowledge_type", sa.String(), nullable=False),
        sa.Column("secondary_demand", sa.String(), nullable=True),
        sa.Column("knowledge_type_source", sa.String(), nullable=False),
        sa.Column("merge_warning", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("teacher_edited", sa.Boolean(), nullable=False),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("pack_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "path_version_id",
            "position",
            name="uq_path_lesson_version_position",
        ),
    )
    for column in ("path_version_id", "concept_id", "concept_slug", "pack_id"):
        op.create_index(f"ix_path_lessons_{column}", "path_lessons", [column])
    op.create_table(
        "path_lesson_prerequisites",
        sa.Column(
            "path_lesson_id",
            sa.String(),
            sa.ForeignKey("path_lessons.id"),
            primary_key=True,
        ),
        sa.Column(
            "prerequisite_lesson_id",
            sa.String(),
            sa.ForeignKey("path_lessons.id"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("path_lesson_prerequisites")
    for column in reversed(("path_version_id", "concept_id", "concept_slug", "pack_id")):
        op.drop_index(f"ix_path_lessons_{column}", table_name="path_lessons")
    op.drop_table("path_lessons")
    op.drop_index("ix_path_versions_unit_id", table_name="path_versions")
    op.drop_table("path_versions")
    op.drop_table("unit_scope_contracts")
    for column in reversed(("owner_id", "subject", "grade_level", "active_path_version_id")):
        op.drop_index(f"ix_units_{column}", table_name="units")
    op.drop_table("units")
