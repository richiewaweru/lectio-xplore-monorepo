"""Add nullable SharedLessonDocument lineage columns for the Learn cutover.

Revision ID: 20260928_0047
Revises: 20260925_0046

Additive only (P10B). Pins the verified shared source identity onto the Learn
realization, its generated output, the Builder editable workspace, and the
immutable release row so every consumer can verify lineage without a second
migration. No existing row is touched; every new column is nullable.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_0047"
down_revision = "20260925_0046"
branch_labels = None
depends_on = None

_LINEAGE_COLUMNS = (
    ("shared_document_run_id", sa.String()),
    ("shared_document_id", sa.String()),
    ("shared_document_revision", sa.Integer()),
    ("shared_document_hash", sa.String()),
)


def upgrade() -> None:
    op.add_column(
        "native_realizations",
        sa.Column("shared_document_run_id", sa.String(), nullable=True),
    )
    op.add_column(
        "native_realizations",
        sa.Column("shared_document_id", sa.String(), nullable=True),
    )
    op.add_column(
        "native_realizations",
        sa.Column("shared_document_revision", sa.Integer(), nullable=True),
    )
    op.add_column(
        "native_realizations",
        sa.Column("shared_document_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "native_realizations",
        sa.Column("shared_document_state", sa.String(), nullable=True),
    )
    for table in ("generations", "editable_lessons", "learn_releases"):
        for name, column_type in _LINEAGE_COLUMNS:
            op.add_column(table, sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    for table in ("learn_releases", "editable_lessons", "generations"):
        for name, _column_type in reversed(_LINEAGE_COLUMNS):
            op.drop_column(table, name)
    op.drop_column("native_realizations", "shared_document_state")
    for name, _column_type in reversed(_LINEAGE_COLUMNS):
        op.drop_column("native_realizations", name)
