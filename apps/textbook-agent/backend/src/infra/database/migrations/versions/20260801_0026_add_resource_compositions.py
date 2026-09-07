"""add deterministic resource compositions

Revision ID: 20260801_0026
Revises: 20260801_0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260801_0026"
down_revision = "20260801_0025"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "resource_compositions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("unit_id", sa.String(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("path_version_id", sa.String(), sa.ForeignKey("path_versions.id"), nullable=False),
        sa.Column("path_version", sa.Integer(), nullable=False),
        sa.Column("path_revision", sa.Integer(), nullable=False),
        sa.Column("projection", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ready"),
        sa.Column("lesson_ids", _json_type(), nullable=False),
        sa.Column("period_ids", _json_type(), nullable=False),
        sa.Column("group_ids", _json_type(), nullable=False),
        sa.Column("selected_component_refs", _json_type(), nullable=False),
        sa.Column("selected_item_ids", _json_type(), nullable=False),
        sa.Column("include_keys", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("template_version", sa.String(), nullable=False),
        sa.Column("source_snapshots", _json_type(), nullable=False),
        sa.Column("document_json", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_resource_compositions_unit_id", "resource_compositions", ["unit_id"])
    op.create_index("ix_resource_compositions_owner_id", "resource_compositions", ["owner_id"])
    op.create_index("ix_resource_compositions_path_version_id", "resource_compositions", ["path_version_id"])
    op.create_index("ix_resource_compositions_projection", "resource_compositions", ["projection"])


def downgrade() -> None:
    op.drop_index("ix_resource_compositions_projection", table_name="resource_compositions")
    op.drop_index("ix_resource_compositions_path_version_id", table_name="resource_compositions")
    op.drop_index("ix_resource_compositions_owner_id", table_name="resource_compositions")
    op.drop_index("ix_resource_compositions_unit_id", table_name="resource_compositions")
    op.drop_table("resource_compositions")
