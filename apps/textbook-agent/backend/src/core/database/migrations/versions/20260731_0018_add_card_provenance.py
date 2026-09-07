"""add concept card reuse provenance

Revision ID: 20260731_0018
Revises: 20260731_0017
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260731_0018"
down_revision = "20260731_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "concept_cards",
        sa.Column("source_card_id", sa.String(), nullable=True),
    )
    op.add_column(
        "concept_cards",
        sa.Column("source_pack_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_concept_cards_source_card_id",
        "concept_cards",
        ["source_card_id"],
    )
    op.create_index(
        "ix_concept_cards_source_pack_id",
        "concept_cards",
        ["source_pack_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_concept_cards_source_pack_id",
        table_name="concept_cards",
    )
    op.drop_index(
        "ix_concept_cards_source_card_id",
        table_name="concept_cards",
    )
    op.drop_column("concept_cards", "source_pack_id")
    op.drop_column("concept_cards", "source_card_id")
