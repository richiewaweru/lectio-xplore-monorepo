"""add canonical concepts and lesson provenance

Revision ID: 20260731_0019
Revises: 20260731_0018
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260731_0019"
down_revision = "20260731_0018"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "concepts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("canonical_slug", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("canonical_description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("canonical_slug", name="uq_concepts_canonical_slug"),
    )
    op.create_index("ix_concepts_canonical_slug", "concepts", ["canonical_slug"])
    op.create_index("ix_concepts_subject", "concepts", ["subject"])
    op.create_index("ix_concepts_created_by", "concepts", ["created_by"])

    with op.batch_alter_table("concept_cards") as batch_op:
        batch_op.add_column(
            sa.Column("canonical_concept_id", sa.String(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_concept_cards_canonical_concept_id_concepts",
            "concepts",
            ["canonical_concept_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_concept_cards_canonical_concept_id",
            ["canonical_concept_id"],
        )

    op.create_table(
        "lesson_provenance",
        sa.Column("pack_id", sa.String(), primary_key=True),
        sa.Column("concept_id", sa.String(), sa.ForeignKey("concepts.id"), nullable=True),
        sa.Column("path_version_id", sa.String(), nullable=True),
        sa.Column("path_lesson_id", sa.String(), nullable=True),
        sa.Column("objective_hash", sa.String(), nullable=True),
        sa.Column("skeleton_id", sa.String(), nullable=True),
        sa.Column("skeleton_version", sa.Integer(), nullable=True),
        sa.Column("knowledge_type", sa.String(), nullable=True),
        sa.Column("knowledge_type_source", sa.String(), nullable=True),
        sa.Column("toggles_applied", _json_type(), nullable=True),
        sa.Column("deviations_applied", _json_type(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_lesson_provenance_concept_id", "lesson_provenance", ["concept_id"])
    op.create_index(
        "ix_lesson_provenance_path_version_id",
        "lesson_provenance",
        ["path_version_id"],
    )
    op.create_index(
        "ix_lesson_provenance_path_lesson_id",
        "lesson_provenance",
        ["path_lesson_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_provenance_path_lesson_id", table_name="lesson_provenance")
    op.drop_index("ix_lesson_provenance_path_version_id", table_name="lesson_provenance")
    op.drop_index("ix_lesson_provenance_concept_id", table_name="lesson_provenance")
    op.drop_table("lesson_provenance")
    with op.batch_alter_table("concept_cards") as batch_op:
        batch_op.drop_index("ix_concept_cards_canonical_concept_id")
        batch_op.drop_constraint(
            "fk_concept_cards_canonical_concept_id_concepts",
            type_="foreignkey",
        )
        batch_op.drop_column("canonical_concept_id")
    op.drop_index("ix_concepts_created_by", table_name="concepts")
    op.drop_index("ix_concepts_subject", table_name="concepts")
    op.drop_index("ix_concepts_canonical_slug", table_name="concepts")
    op.drop_table("concepts")
