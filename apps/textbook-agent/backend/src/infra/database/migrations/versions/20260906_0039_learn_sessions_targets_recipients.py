"""Additive Learn closeout tables: sessions, class roles, assignment targets/recipients."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260906_0039"
down_revision = "20260906_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learner_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("learner_id", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_identities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_learner_sessions_learner_id", "learner_sessions", ["learner_id"])
    op.create_index("ix_learner_sessions_token", "learner_sessions", ["token"])

    # Class membership: staff roles + nullable learner_id
    with op.batch_alter_table("learn_class_memberships") as batch:
        batch.add_column(sa.Column("teacher_user_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("role", sa.String(), nullable=False, server_default="learner")
        )
        batch.alter_column("learner_id", existing_type=sa.String(), nullable=True)
        batch.create_foreign_key(
            "fk_learn_class_memberships_teacher_user_id",
            "users",
            ["teacher_user_id"],
            ["id"],
        )

    op.create_table(
        "learn_assignment_targets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("assignment_id", sa.String(), nullable=False),
        sa.Column("class_id", sa.String(), nullable=True),
        sa.Column("learner_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["learn_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["learn_classes.id"]),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_identities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id",
            "class_id",
            "learner_id",
            name="uq_learn_assignment_target",
        ),
    )
    op.create_index(
        "ix_learn_assignment_targets_assignment_id",
        "learn_assignment_targets",
        ["assignment_id"],
    )

    op.create_table(
        "learn_assignment_recipients",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("assignment_id", sa.String(), nullable=False),
        sa.Column("learner_id", sa.String(), nullable=False),
        sa.Column("class_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="assigned"),
        sa.Column("learning_instance_id", sa.String(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("overdue_at", sa.DateTime(), nullable=True),
        sa.Column("excused", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["assignment_id"], ["learn_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_identities.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["learn_classes.id"]),
        sa.ForeignKeyConstraint(["learning_instance_id"], ["learning_instances.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id",
            "learner_id",
            name="uq_learn_assignment_recipient",
        ),
    )
    op.create_index(
        "ix_learn_assignment_recipients_assignment_id",
        "learn_assignment_recipients",
        ["assignment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learn_assignment_recipients_assignment_id",
        table_name="learn_assignment_recipients",
    )
    op.drop_table("learn_assignment_recipients")
    op.drop_index(
        "ix_learn_assignment_targets_assignment_id",
        table_name="learn_assignment_targets",
    )
    op.drop_table("learn_assignment_targets")
    with op.batch_alter_table("learn_class_memberships") as batch:
        batch.drop_constraint("fk_learn_class_memberships_teacher_user_id", type_="foreignkey")
        batch.drop_column("role")
        batch.drop_column("teacher_user_id")
        batch.alter_column("learner_id", existing_type=sa.String(), nullable=False)
    op.drop_index("ix_learner_sessions_token", table_name="learner_sessions")
    op.drop_index("ix_learner_sessions_learner_id", table_name="learner_sessions")
    op.drop_table("learner_sessions")
