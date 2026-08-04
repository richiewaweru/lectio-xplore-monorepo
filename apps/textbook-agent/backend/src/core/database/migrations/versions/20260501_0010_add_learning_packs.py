"""add learning packs

Revision ID: 20260501_0010
Revises: 20260407_0009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260501_0010"
down_revision = "20260407_0009"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("learning_packs"):
        op.create_table(
            "learning_packs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("learning_job_type", sa.String(), nullable=False),
            sa.Column("subject", sa.String(), nullable=False),
            sa.Column("topic", sa.String(), nullable=False),
            sa.Column("pack_plan_json", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("resource_count", sa.Integer(), nullable=False),
            sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("current_resource_label", sa.String(), nullable=True),
            sa.Column("current_phase", sa.String(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
    if not _index_exists("learning_packs", "ix_learning_packs_user_id"):
        op.create_index("ix_learning_packs_user_id", "learning_packs", ["user_id"])
    if not _index_exists("learning_packs", "ix_learning_packs_status"):
        op.create_index("ix_learning_packs_status", "learning_packs", ["status"])

    if not _column_exists("generations", "pack_id"):
        op.add_column(
            "generations",
            sa.Column("pack_id", sa.String(), sa.ForeignKey("learning_packs.id"), nullable=True),
        )
    if not _column_exists("generations", "pack_resource_id"):
        op.add_column("generations", sa.Column("pack_resource_id", sa.String(), nullable=True))
    if not _column_exists("generations", "pack_resource_label"):
        op.add_column("generations", sa.Column("pack_resource_label", sa.String(), nullable=True))
    if not _index_exists("generations", "ix_generations_pack_id"):
        op.create_index("ix_generations_pack_id", "generations", ["pack_id"])
    if not _index_exists("generations", "ix_generations_pack_resource_id"):
        op.create_index("ix_generations_pack_resource_id", "generations", ["pack_resource_id"])


def downgrade() -> None:
    if _index_exists("generations", "ix_generations_pack_resource_id"):
        op.drop_index("ix_generations_pack_resource_id", "generations")
    if _index_exists("generations", "ix_generations_pack_id"):
        op.drop_index("ix_generations_pack_id", "generations")
    if _column_exists("generations", "pack_resource_label"):
        op.drop_column("generations", "pack_resource_label")
    if _column_exists("generations", "pack_resource_id"):
        op.drop_column("generations", "pack_resource_id")
    if _column_exists("generations", "pack_id"):
        op.drop_column("generations", "pack_id")
    if _index_exists("learning_packs", "ix_learning_packs_status"):
        op.drop_index("ix_learning_packs_status", "learning_packs")
    if _index_exists("learning_packs", "ix_learning_packs_user_id"):
        op.drop_index("ix_learning_packs_user_id", "learning_packs")
    if _table_exists("learning_packs"):
        op.drop_table("learning_packs")
