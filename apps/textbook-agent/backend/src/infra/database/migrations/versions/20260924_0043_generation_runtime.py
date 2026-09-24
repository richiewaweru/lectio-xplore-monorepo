"""Add generic generation runtime persistence.

Revision ID: 20260924_0043
Revises: 20260913_0042
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260924_0043"
down_revision = "20260913_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_builds",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("path_lesson_id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["path_lesson_id"], ["path_lessons.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_builds_owner_user_id", "generation_builds", ["owner_user_id"])
    op.create_index("ix_generation_builds_path_lesson_id", "generation_builds", ["path_lesson_id"])
    op.create_index(
        "ix_generation_builds_owner_created", "generation_builds", ["owner_user_id", "created_at"]
    )

    op.create_table(
        "generation_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("build_id", sa.String(), nullable=False),
        sa.Column("run_type", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="queued", nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("source_artifact_type", sa.String(), nullable=False),
        sa.Column("source_artifact_id", sa.String(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(), nullable=False),
        sa.Column("output_artifact_type", sa.String(), nullable=True),
        sa.Column("output_artifact_id", sa.String(), nullable=True),
        sa.Column("output_revision", sa.Integer(), nullable=True),
        sa.Column("output_hash", sa.String(), nullable=True),
        sa.Column("request_key", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_class", sa.String(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("recovery_action", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "run_type IN ('preparation', 'shared_document', 'learn', 'print', 'publish', 'pdf')",
            name="ck_generation_runs_run_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'awaiting_review', 'ready', "
            "'failed_recoverable', 'failed_terminal', 'cancelled')",
            name="ck_generation_runs_status",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_generation_runs_attempt_positive"),
        sa.CheckConstraint(
            "source_revision >= 1", name="ck_generation_runs_source_revision_positive"
        ),
        sa.CheckConstraint(
            "output_revision IS NULL OR output_revision >= 1",
            name="ck_generation_runs_output_revision_positive",
        ),
        sa.CheckConstraint(
            "status != 'ready' OR (output_artifact_type IS NOT NULL AND "
            "output_artifact_id IS NOT NULL AND output_revision IS NOT NULL AND output_hash IS NOT NULL)",
            name="ck_generation_runs_ready_has_output",
        ),
        sa.ForeignKeyConstraint(["build_id"], ["generation_builds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "request_key", name="uq_generation_runs_request"),
    )
    op.create_index("ix_generation_runs_build_id", "generation_runs", ["build_id"])
    op.create_index("ix_generation_runs_owner_user_id", "generation_runs", ["owner_user_id"])
    op.create_index("ix_generation_runs_status", "generation_runs", ["status"])
    op.create_index(
        "ix_generation_runs_build_created", "generation_runs", ["build_id", "created_at"]
    )
    op.create_index(
        "ix_generation_runs_owner_status_updated",
        "generation_runs",
        ["owner_user_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_generation_runs_status_created", "generation_runs", ["status", "created_at"]
    )

    op.create_table(
        "generation_work_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("item_key", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="queued", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("definition_hash", sa.String(), nullable=False),
        sa.Column("composition_identity", sa.String(), nullable=True),
        sa.Column("lease_owner", sa.String(), nullable=True),
        sa.Column("lease_token", sa.Integer(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("checkpoint_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("output_hash", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_class", sa.String(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("recovery_action", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed_recoverable', "
            "'failed_terminal', 'cancelled')",
            name="ck_generation_work_items_status",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_generation_work_items_attempt_positive"),
        sa.CheckConstraint(
            "max_attempts >= 1", name="ck_generation_work_items_max_attempts_positive"
        ),
        sa.CheckConstraint(
            "attempt <= max_attempts", name="ck_generation_work_items_attempt_lte_max"
        ),
        sa.CheckConstraint(
            "lease_token IS NULL OR lease_token >= 1",
            name="ck_generation_work_items_lease_token_positive",
        ),
        sa.CheckConstraint(
            "status != 'ready' OR (output_json IS NOT NULL AND output_hash IS NOT NULL)",
            name="ck_generation_work_items_ready_has_output",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "item_key", name="uq_generation_work_items_run_key"),
    )
    op.create_index("ix_generation_work_items_run_id", "generation_work_items", ["run_id"])
    op.create_index("ix_generation_work_items_status", "generation_work_items", ["status"])
    op.create_index(
        "ix_generation_work_items_run_status", "generation_work_items", ["run_id", "status"]
    )
    op.create_index(
        "ix_generation_work_items_status_lease",
        "generation_work_items",
        ["status", "lease_expires_at"],
    )

    op.create_table(
        "generation_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("work_item_id", sa.String(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("safe_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("seq >= 1", name="ck_generation_events_seq_positive"),
        sa.CheckConstraint("attempt >= 1", name="ck_generation_events_attempt_positive"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'awaiting_review', 'ready', "
            "'failed_recoverable', 'failed_terminal', 'cancelled')",
            name="ck_generation_events_status",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["work_item_id"], ["generation_work_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "seq", name="uq_generation_events_run_seq"),
    )
    op.create_index("ix_generation_events_run_id", "generation_events", ["run_id"])
    op.create_index(
        "ix_generation_events_run_created", "generation_events", ["run_id", "created_at"]
    )
    op.create_index("ix_generation_events_work_item", "generation_events", ["work_item_id", "seq"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION guard_ready_generation_run() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF OLD.status = 'ready' THEN "
            "RAISE EXCEPTION 'ready generation run is immutable'; END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_runs_ready_immutable BEFORE UPDATE ON generation_runs "
            "FOR EACH ROW EXECUTE FUNCTION guard_ready_generation_run()"
        )
        op.execute(
            "CREATE FUNCTION guard_ready_generation_work_item() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF OLD.status = 'ready' THEN "
            "RAISE EXCEPTION 'ready generation work item is immutable'; END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_work_items_ready_immutable BEFORE UPDATE ON generation_work_items "
            "FOR EACH ROW EXECUTE FUNCTION guard_ready_generation_work_item()"
        )
        op.execute(
            "CREATE FUNCTION prevent_ready_generation_output_delete() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN IF OLD.status = 'ready' THEN "
            "RAISE EXCEPTION 'ready generation output is immutable'; END IF; RETURN OLD; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_runs_ready_no_delete BEFORE DELETE ON generation_runs "
            "FOR EACH ROW EXECUTE FUNCTION prevent_ready_generation_output_delete()"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_work_items_ready_no_delete BEFORE DELETE ON generation_work_items "
            "FOR EACH ROW EXECUTE FUNCTION prevent_ready_generation_output_delete()"
        )
        op.execute(
            "CREATE FUNCTION prevent_generation_event_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'generation events are append-only'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_events_no_update BEFORE UPDATE ON generation_events "
            "FOR EACH ROW EXECUTE FUNCTION prevent_generation_event_mutation()"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_events_no_delete BEFORE DELETE ON generation_events "
            "FOR EACH ROW EXECUTE FUNCTION prevent_generation_event_mutation()"
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER trg_generation_runs_ready_immutable BEFORE UPDATE ON generation_runs "
            "WHEN OLD.status = 'ready' "
            "BEGIN SELECT RAISE(ABORT, 'ready generation run is immutable'); END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_work_items_ready_immutable BEFORE UPDATE ON generation_work_items "
            "WHEN OLD.status = 'ready' "
            "BEGIN SELECT RAISE(ABORT, 'ready generation work item is immutable'); END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_runs_ready_no_delete BEFORE DELETE ON generation_runs "
            "WHEN OLD.status = 'ready' "
            "BEGIN SELECT RAISE(ABORT, 'ready generation run is immutable'); END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_work_items_ready_no_delete BEFORE DELETE ON generation_work_items "
            "WHEN OLD.status = 'ready' "
            "BEGIN SELECT RAISE(ABORT, 'ready generation work item is immutable'); END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_events_no_update BEFORE UPDATE ON generation_events "
            "BEGIN SELECT RAISE(ABORT, 'generation events are append-only'); END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_events_no_delete BEFORE DELETE ON generation_events "
            "BEGIN SELECT RAISE(ABORT, 'generation events are append-only'); END"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_immutable ON generation_runs")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_generation_work_items_ready_immutable ON generation_work_items"
        )
        op.execute("DROP FUNCTION IF EXISTS guard_ready_generation_run()")
        op.execute("DROP FUNCTION IF EXISTS guard_ready_generation_work_item()")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_no_delete ON generation_runs")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_generation_work_items_ready_no_delete ON generation_work_items"
        )
        op.execute("DROP FUNCTION IF EXISTS prevent_ready_generation_output_delete()")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_events_no_delete ON generation_events")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_events_no_update ON generation_events")
        op.execute("DROP FUNCTION IF EXISTS prevent_generation_event_mutation()")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_immutable")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_work_items_ready_immutable")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_no_delete")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_work_items_ready_no_delete")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_events_no_delete")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_events_no_update")

    op.drop_index("ix_generation_events_work_item", table_name="generation_events")
    op.drop_index("ix_generation_events_run_created", table_name="generation_events")
    op.drop_index("ix_generation_events_run_id", table_name="generation_events")
    op.drop_table("generation_events")
    op.drop_index("ix_generation_work_items_status_lease", table_name="generation_work_items")
    op.drop_index("ix_generation_work_items_run_status", table_name="generation_work_items")
    op.drop_index("ix_generation_work_items_status", table_name="generation_work_items")
    op.drop_index("ix_generation_work_items_run_id", table_name="generation_work_items")
    op.drop_table("generation_work_items")
    op.drop_index("ix_generation_runs_status_created", table_name="generation_runs")
    op.drop_index("ix_generation_runs_owner_status_updated", table_name="generation_runs")
    op.drop_index("ix_generation_runs_build_created", table_name="generation_runs")
    op.drop_index("ix_generation_runs_status", table_name="generation_runs")
    op.drop_index("ix_generation_runs_owner_user_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_build_id", table_name="generation_runs")
    op.drop_table("generation_runs")
    op.drop_index("ix_generation_builds_owner_created", table_name="generation_builds")
    op.drop_index("ix_generation_builds_path_lesson_id", table_name="generation_builds")
    op.drop_index("ix_generation_builds_owner_user_id", table_name="generation_builds")
    op.drop_table("generation_builds")
