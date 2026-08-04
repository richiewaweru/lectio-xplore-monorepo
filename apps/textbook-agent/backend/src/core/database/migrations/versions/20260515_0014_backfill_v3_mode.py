"""backfill v3 generation mode

Revision ID: 20260515_0014
Revises: 20260513_0013
"""

from __future__ import annotations

from alembic import op

revision = "20260515_0014"
down_revision = "20260513_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE generations SET mode = 'v3' "
        "WHERE requested_preset_id = 'v3-studio' AND mode != 'v3'"
    )


def downgrade() -> None:
    pass
