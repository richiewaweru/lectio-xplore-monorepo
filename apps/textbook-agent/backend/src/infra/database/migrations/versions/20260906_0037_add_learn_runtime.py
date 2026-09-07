"""Add Learn runtime / classes / assignments tables (Phases 06–09)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260906_0037"
down_revision = "20260906_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learner_identities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("invite_code", sa.String(), nullable=True),
        sa.Column("created_by_teacher_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_teacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code"),
    )
    op.create_index("ix_learner_identities_invite_code", "learner_identities", ["invite_code"])

    op.create_table(
        "learn_classes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("teacher_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("invite_code", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code"),
    )
    op.create_index("ix_learn_classes_teacher_id", "learn_classes", ["teacher_id"])

    op.create_table(
        "learn_class_memberships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("class_id", sa.String(), nullable=False),
        sa.Column("learner_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["learn_classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_identities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_id", "learner_id", name="uq_class_membership"),
    )

    op.create_table(
        "learn_assignments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("teacher_id", sa.String(), nullable=False),
        sa.Column("learn_release_id", sa.String(), nullable=False),
        sa.Column("class_id", sa.String(), nullable=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("selected_learner_ids", sa.JSON(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closes_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["learn_release_id"], ["learn_releases.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["learn_classes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "learning_instances",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("learner_id", sa.String(), nullable=False),
        sa.Column("learn_release_id", sa.String(), nullable=False),
        sa.Column("assignment_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("current_section_id", sa.String(), nullable=True),
        sa.Column("score_earned", sa.Float(), nullable=False, server_default="0"),
        sa.Column("score_possible", sa.Float(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_identities.id"]),
        sa.ForeignKeyConstraint(["learn_release_id"], ["learn_releases.id"]),
        sa.ForeignKeyConstraint(["assignment_id"], ["learn_assignments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_instances_learner_release",
        "learning_instances",
        ["learner_id", "learn_release_id"],
    )

    op.create_table(
        "learner_attempts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("learning_instance_id", sa.String(), nullable=False),
        sa.Column("interaction_id", sa.String(), nullable=False),
        sa.Column("section_id", sa.String(), nullable=True),
        sa.Column("client_submission_id", sa.String(), nullable=False),
        sa.Column("assessment_mode", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("score_earned", sa.Float(), nullable=False),
        sa.Column("score_possible", sa.Float(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["learning_instance_id"], ["learning_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_instance_id",
            "client_submission_id",
            name="uq_learner_attempts_instance_submission",
        ),
    )

    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("learning_instance_id", sa.String(), nullable=False),
        sa.Column("completed_section_ids", sa.JSON(), nullable=False),
        sa.Column("completed_interaction_ids", sa.JSON(), nullable=False),
        sa.Column("score_earned", sa.Float(), nullable=False),
        sa.Column("score_possible", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["learning_instance_id"], ["learning_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learning_instance_id", name="uq_lesson_progress_instance"),
    )

    op.create_table(
        "concept_evidence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("learner_id", sa.String(), nullable=False),
        sa.Column("learning_instance_id", sa.String(), nullable=False),
        sa.Column("attempt_id", sa.String(), nullable=False),
        sa.Column("learn_release_id", sa.String(), nullable=False),
        sa.Column("path_lesson_id", sa.String(), nullable=True),
        sa.Column("concept_id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=True),
        sa.Column("node_id", sa.String(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("score_earned", sa.Float(), nullable=False),
        sa.Column("score_possible", sa.Float(), nullable=False),
        sa.Column("misconception_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_identities.id"]),
        sa.ForeignKeyConstraint(["learning_instance_id"], ["learning_instances.id"]),
        sa.ForeignKeyConstraint(["attempt_id"], ["learner_attempts.id"]),
        sa.ForeignKeyConstraint(["learn_release_id"], ["learn_releases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "concept_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("learner_id", sa.String(), nullable=False),
        sa.Column("concept_id", sa.String(), nullable=False),
        sa.Column("classification", sa.String(), nullable=False),
        sa.Column("score_earned", sa.Float(), nullable=False),
        sa.Column("score_possible", sa.Float(), nullable=False),
        sa.Column("first_attempt_success", sa.Boolean(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_identities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "concept_id", name="uq_concept_state_learner_concept"),
    )


def downgrade() -> None:
    for table in (
        "concept_states",
        "concept_evidence",
        "lesson_progress",
        "learner_attempts",
        "learning_instances",
        "learn_assignments",
        "learn_class_memberships",
        "learn_classes",
        "learner_identities",
    ):
        op.drop_table(table)
