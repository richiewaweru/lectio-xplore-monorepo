"""allow append-only repeated generation step events

Revision ID: 20260904_0033
Revises: 20260806_0032

The latest event for a block is authoritative. Repeated failure and recovery
events must therefore be retained instead of rejected by a uniqueness rule.
"""

from __future__ import annotations

from alembic import op

revision = "20260904_0033"
down_revision = "20260806_0032"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "uq_generation_steps_part_variant_step"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "generation_steps", type_="unique")


def downgrade() -> None:
    # Re-establishing the historical constraint requires retaining only the
    # newest event for each former unique key.
    op.execute(
        """
        DELETE FROM generation_steps AS older
        USING generation_steps AS newer
        WHERE older.generation_id = newer.generation_id
          AND older.part_id = newer.part_id
          AND older.variant_id = newer.variant_id
          AND older.step = newer.step
          AND (older.created_at, older.id) < (newer.created_at, newer.id)
        """
    )
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        "generation_steps",
        ["generation_id", "part_id", "variant_id", "step"],
    )
