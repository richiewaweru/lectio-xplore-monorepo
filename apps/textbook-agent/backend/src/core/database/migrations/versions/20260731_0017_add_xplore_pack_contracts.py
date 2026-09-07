"""add xplore concept cards, pack items, and variant metadata

Revision ID: 20260731_0017
Revises: 20260727_0016
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260731_0017"
down_revision = "20260727_0016"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "concept_cards",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("pack_id", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("prereqs", _json_type(), nullable=False, server_default="[]"),
        sa.Column("misconceptions", _json_type(), nullable=False, server_default="[]"),
        sa.Column("teacher_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_concept_cards_pack_id", "concept_cards", ["pack_id"])

    op.create_table(
        "pack_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("pack_id", sa.String(), nullable=False),
        sa.Column(
            "card_id",
            sa.String(),
            sa.ForeignKey("concept_cards.id"),
            nullable=False,
        ),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", _json_type(), nullable=False),
        sa.Column("correct_key", sa.String(), nullable=False),
        sa.Column("diagnoses", _json_type(), nullable=False, server_default="{}"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pack_items_pack_id", "pack_items", ["pack_id"])
    op.create_index("ix_pack_items_card_id", "pack_items", ["card_id"])

    op.add_column("generations", sa.Column("variant_label", sa.String(), nullable=True))
    op.add_column("generations", sa.Column("variant_spec", _json_type(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "variant_spec")
    op.drop_column("generations", "variant_label")
    op.drop_index("ix_pack_items_card_id", table_name="pack_items")
    op.drop_index("ix_pack_items_pack_id", table_name="pack_items")
    op.drop_table("pack_items")
    op.drop_index("ix_concept_cards_pack_id", table_name="concept_cards")
    op.drop_table("concept_cards")
