"""Add admission request keys and caller effect keys (P02 G07/G08).

Revision ID: 20260913_0042
Revises: 20260908_0041
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260913_0042"
down_revision = "20260908_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "native_realizations",
        sa.Column("admission_request_key", sa.String(), nullable=True),
    )
    op.add_column(
        "native_realizations",
        sa.Column("admission_payload_hash", sa.String(), nullable=True),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_native_realization_request_key",
            "native_realizations",
            ["path_lesson_id", "path", "admission_request_key"],
            unique=True,
            postgresql_where=sa.text("admission_request_key IS NOT NULL"),
        )
    else:
        op.create_index(
            "uq_native_realization_request_key",
            "native_realizations",
            ["path_lesson_id", "path", "admission_request_key"],
            unique=True,
        )

    op.create_table(
        "caller_effect_keys",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("request_key", sa.String(), nullable=False),
        sa.Column("payload_hash", sa.String(), nullable=False),
        sa.Column("outcome_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "owner_user_id",
            "kind",
            "resource_id",
            "request_key",
            name="uq_caller_effect_key",
        ),
    )
    op.create_index(
        "ix_caller_effect_keys_resource",
        "caller_effect_keys",
        ["kind", "resource_id"],
    )
    op.create_index(
        "ix_caller_effect_keys_owner_user_id",
        "caller_effect_keys",
        ["owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_caller_effect_keys_owner_user_id", table_name="caller_effect_keys")
    op.drop_index("ix_caller_effect_keys_resource", table_name="caller_effect_keys")
    op.drop_table("caller_effect_keys")
    op.drop_index("uq_native_realization_request_key", table_name="native_realizations")
    op.drop_column("native_realizations", "admission_payload_hash")
    op.drop_column("native_realizations", "admission_request_key")
