"""Link native realizations to their generation Run (Option D, item 4A).

Revision ID: 20260929_0049
Revises: 20260929_0048

Additive only. ``native_realizations.generation_run_id`` is NULL until the
RealizationWorker admits a learn/print Run for the realization; a NULL value
on a mid-flight row is the "created before the job update" legacy signal.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260929_0049"
down_revision = "20260929_0048"
branch_labels = None
depends_on = None

_FK_NAME = "fk_native_realizations_generation_run_id"
_INDEX_NAME = "ix_native_realizations_generation_run_id"


def upgrade() -> None:
    with op.batch_alter_table("native_realizations") as batch:
        batch.add_column(sa.Column("generation_run_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            _FK_NAME,
            "generation_runs",
            ["generation_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(_INDEX_NAME, "native_realizations", ["generation_run_id"])


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="native_realizations")
    with op.batch_alter_table("native_realizations") as batch:
        batch.drop_constraint(_FK_NAME, type_="foreignkey")
        batch.drop_column("generation_run_id")
