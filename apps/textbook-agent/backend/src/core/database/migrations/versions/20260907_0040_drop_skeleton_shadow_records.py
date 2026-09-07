"""D4: drop retired skeleton_shadow_records table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260907_0040"
down_revision = "20260906_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "skeleton_shadow_records" not in inspector.get_table_names():
        return
    for column in (
        "generation_id",
        "skeleton_id",
        "skeleton_version",
        "knowledge_type",
        "created_at",
    ):
        index_name = f"ix_skeleton_shadow_records_{column}"
        indexes = {idx["name"] for idx in inspector.get_indexes("skeleton_shadow_records")}
        if index_name in indexes:
            op.drop_index(index_name, table_name="skeleton_shadow_records")
    op.drop_table("skeleton_shadow_records")


def downgrade() -> None:
    op.create_table(
        "skeleton_shadow_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("generation_id", sa.String(), nullable=False),
        sa.Column("skeleton_id", sa.String(), nullable=True),
        sa.Column("skeleton_version", sa.Integer(), nullable=True),
        sa.Column("knowledge_type", sa.String(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_id", name="uq_skeleton_shadow_generation_id"),
    )
    for column in (
        "generation_id",
        "skeleton_id",
        "skeleton_version",
        "knowledge_type",
        "created_at",
    ):
        op.create_index(
            f"ix_skeleton_shadow_records_{column}",
            "skeleton_shadow_records",
            [column],
        )
