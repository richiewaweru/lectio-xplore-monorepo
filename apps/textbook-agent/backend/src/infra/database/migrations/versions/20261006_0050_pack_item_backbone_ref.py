"""Record which lesson-backbone scenario each approved item is about.

Revision ID: 20261006_0050
Revises: 20260929_0049

Additive only. ``pack_items.backbone_ref`` is NULL for items written before the
lesson backbone existed (or generated without one); otherwise it holds
``{"target": "anchor-1" | "v1" | ..., "figure_id": str | null, "backbone_hash": str}``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261006_0050"
down_revision = "20260929_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pack_items") as batch:
        batch.add_column(sa.Column("backbone_ref", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pack_items") as batch:
        batch.drop_column("backbone_ref")
