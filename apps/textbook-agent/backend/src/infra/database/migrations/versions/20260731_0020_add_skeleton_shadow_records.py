"""add skeleton shadow records

Revision ID: 20260731_0020
Revises: 20260731_0019
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260731_0020"
down_revision = "20260731_0019"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "skeleton_shadow_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("generation_id", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("grade", sa.String(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("current_roles", _json_type(), nullable=False),
        sa.Column("classifier_type", sa.String(), nullable=False),
        sa.Column("classifier_confidence", sa.String(), nullable=False),
        sa.Column("classifier_success_test", sa.Text(), nullable=False),
        sa.Column("classifier_note", sa.Text(), nullable=True),
        sa.Column("skeleton_id", sa.String(), nullable=False),
        sa.Column("skeleton_version", sa.Integer(), nullable=False),
        sa.Column("expanded_slots", _json_type(), nullable=False),
        sa.Column("toggles_applied", _json_type(), nullable=False),
        sa.Column("expansion_warnings", _json_type(), nullable=False),
        sa.Column("structural_match_score", sa.Float(), nullable=False),
        sa.Column("reviewer_preference", sa.String(), nullable=True),
        sa.Column("wrong_classification", sa.Boolean(), nullable=True),
        sa.Column("deviation_required", sa.Boolean(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("generation_id", name="uq_skeleton_shadow_generation_id"),
    )
    for column in (
        "generation_id",
        "subject",
        "grade",
        "classifier_type",
        "classifier_confidence",
        "skeleton_id",
    ):
        op.create_index(
            f"ix_skeleton_shadow_records_{column}",
            "skeleton_shadow_records",
            [column],
        )


def downgrade() -> None:
    for column in reversed(
        (
            "generation_id",
            "subject",
            "grade",
            "classifier_type",
            "classifier_confidence",
            "skeleton_id",
        )
    ):
        op.drop_index(
            f"ix_skeleton_shadow_records_{column}",
            table_name="skeleton_shadow_records",
        )
    op.drop_table("skeleton_shadow_records")
