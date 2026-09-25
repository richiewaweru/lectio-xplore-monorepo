"""Persist same-Run WorkItem replacement lineage and active-leaf guards.

Revision ID: 20260925_0046
Revises: 20260925_0045
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260925_0046"
down_revision = "20260925_0045"
branch_labels = None
depends_on = None


def _create_postgresql_guards() -> None:
    op.execute(
        "CREATE FUNCTION guard_generation_work_item_admission() "
        "RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$ "
        "DECLARE parent_status text; prior_run_id text; prior_status text; prior_stage text; "
        "BEGIN "
        "IF NEW.replaces_work_item_id IS NOT NULL THEN "
        "SELECT run_id, status, stage INTO prior_run_id, prior_status, prior_stage "
        "FROM generation_work_items WHERE id = NEW.replaces_work_item_id FOR UPDATE; "
        "IF prior_run_id IS NULL OR prior_run_id <> NEW.run_id THEN "
        "RAISE EXCEPTION 'replacement must reference an item in the same Run'; END IF; "
        "IF prior_status NOT IN ('ready', 'failed_recoverable') OR prior_stage <> NEW.stage THEN "
        "RAISE EXCEPTION 'replacement predecessor is not eligible'; END IF; "
        "IF EXISTS (SELECT 1 FROM generation_work_items "
        "WHERE replaces_work_item_id = NEW.replaces_work_item_id) THEN "
        "RAISE EXCEPTION 'replacement predecessor already has a successor'; END IF; "
        "END IF; "
        "SELECT status INTO parent_status FROM generation_runs "
        "WHERE id = NEW.run_id FOR UPDATE; "
        "IF parent_status IS NULL THEN RAISE EXCEPTION 'generation run does not exist'; END IF; "
        "IF parent_status NOT IN ('queued', 'running') AND NOT "
        "(parent_status = 'failed_recoverable' AND NEW.replaces_work_item_id IS NOT NULL) THEN "
        "RAISE EXCEPTION 'generation work items require an active Run or a linked repair'; END IF; "
        "RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_generation_work_items_active_run_insert "
        "BEFORE INSERT ON generation_work_items FOR EACH ROW "
        "EXECUTE FUNCTION guard_generation_work_item_admission()"
    )
    op.execute(
        "CREATE FUNCTION guard_generation_run_ready_items() "
        "RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$ BEGIN "
        "IF NEW.status = 'ready' AND "
        "(TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'ready') THEN "
        "IF NOT EXISTS (SELECT 1 FROM generation_work_items item "
        "WHERE item.run_id = NEW.id AND NOT EXISTS "
        "(SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = item.id)) THEN "
        "RAISE EXCEPTION 'ready generation Run requires active work items'; END IF; "
        "IF EXISTS (SELECT 1 FROM generation_work_items item "
        "WHERE item.run_id = NEW.id AND NOT EXISTS "
        "(SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = item.id) AND item.status <> 'ready') THEN "
        "RAISE EXCEPTION 'ready generation Run requires all active items ready'; END IF; "
        "END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_generation_runs_ready_requires_items "
        "BEFORE INSERT OR UPDATE ON generation_runs FOR EACH ROW "
        "EXECUTE FUNCTION guard_generation_run_ready_items()"
    )
    op.execute(
        "CREATE FUNCTION guard_generation_run_reopen_for_repair() "
        "RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$ BEGIN "
        "IF OLD.status IN ('failed_terminal', 'cancelled') AND "
        "NEW.status IN ('queued', 'running') THEN "
        "RAISE EXCEPTION 'terminal generation Run cannot be reopened'; END IF; "
        "IF OLD.status = 'failed_recoverable' AND NEW.status IN ('queued', 'running') THEN "
        "IF NOT EXISTS (SELECT 1 FROM generation_work_items replacement "
        "WHERE replacement.run_id = NEW.id AND replacement.replaces_work_item_id IS NOT NULL "
        "AND replacement.status IN ('queued', 'running', 'ready')) AND NOT EXISTS ("
        "SELECT 1 FROM generation_work_items retried JOIN generation_events event "
        "ON event.work_item_id = retried.id AND event.run_id = NEW.id "
        "WHERE retried.run_id = NEW.id AND retried.replaces_work_item_id IS NULL "
        "AND retried.status IN ('queued', 'running') AND retried.attempt > 1 "
        "AND event.event_type = 'work_item_retry_queued') THEN "
        "RAISE EXCEPTION 'recoverable Run reopens only for a linked replacement or targeted retry'; END IF; "
        "IF EXISTS (SELECT 1 FROM generation_work_items item WHERE item.run_id = NEW.id "
        "AND NOT EXISTS (SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = item.id) "
        "AND item.status IN ('failed_recoverable', 'failed_terminal')) THEN "
        "RAISE EXCEPTION 'unrelated active failures block Run reopening'; END IF; "
        "END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_generation_runs_reopen_for_repair "
        "BEFORE UPDATE OF status ON generation_runs FOR EACH ROW "
        "EXECUTE FUNCTION guard_generation_run_reopen_for_repair()"
    )


def _create_sqlite_guards() -> None:
    op.execute(
        "CREATE TRIGGER trg_generation_work_items_active_run_insert "
        "BEFORE INSERT ON generation_work_items BEGIN "
        "SELECT CASE WHEN NEW.replaces_work_item_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM generation_work_items prior WHERE prior.id = NEW.replaces_work_item_id "
        "AND prior.run_id = NEW.run_id AND prior.status IN ('ready', 'failed_recoverable') "
        "AND prior.stage = NEW.stage) THEN "
        "RAISE(ABORT, 'replacement predecessor is not eligible in this Run') END; "
        "SELECT CASE WHEN NEW.replaces_work_item_id IS NOT NULL AND EXISTS ("
        "SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = NEW.replaces_work_item_id) THEN "
        "RAISE(ABORT, 'replacement predecessor already has a successor') END; "
        "SELECT CASE WHEN (SELECT status FROM generation_runs WHERE id = NEW.run_id) "
        "NOT IN ('queued', 'running') AND NOT ("
        "(SELECT status FROM generation_runs WHERE id = NEW.run_id) = 'failed_recoverable' "
        "AND NEW.replaces_work_item_id IS NOT NULL) THEN "
        "RAISE(ABORT, 'generation work items require an active Run or a linked repair') END; "
        "END"
    )
    op.execute(
        "CREATE TRIGGER trg_generation_runs_ready_requires_items_insert "
        "BEFORE INSERT ON generation_runs WHEN NEW.status = 'ready' BEGIN "
        "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM generation_work_items item "
        "WHERE item.run_id = NEW.id AND NOT EXISTS (SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = item.id)) THEN "
        "RAISE(ABORT, 'ready generation Run requires active work items') END; "
        "SELECT CASE WHEN EXISTS (SELECT 1 FROM generation_work_items item "
        "WHERE item.run_id = NEW.id AND NOT EXISTS (SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = item.id) AND item.status <> 'ready') THEN "
        "RAISE(ABORT, 'ready generation Run requires all active items ready') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_generation_runs_ready_requires_items_update "
        "BEFORE UPDATE OF status ON generation_runs "
        "WHEN NEW.status = 'ready' AND OLD.status <> 'ready' BEGIN "
        "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM generation_work_items item "
        "WHERE item.run_id = NEW.id AND NOT EXISTS (SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = item.id)) THEN "
        "RAISE(ABORT, 'ready generation Run requires active work items') END; "
        "SELECT CASE WHEN EXISTS (SELECT 1 FROM generation_work_items item "
        "WHERE item.run_id = NEW.id AND NOT EXISTS (SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = item.id) AND item.status <> 'ready') THEN "
        "RAISE(ABORT, 'ready generation Run requires all active items ready') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_generation_runs_reopen_for_repair "
        "BEFORE UPDATE OF status ON generation_runs BEGIN "
        "SELECT CASE WHEN OLD.status IN ('failed_terminal', 'cancelled') "
        "AND NEW.status IN ('queued', 'running') THEN "
        "RAISE(ABORT, 'terminal generation Run cannot be reopened') END; "
        "SELECT CASE WHEN OLD.status = 'failed_recoverable' "
        "AND NEW.status IN ('queued', 'running') AND NOT EXISTS ("
        "SELECT 1 FROM generation_work_items replacement WHERE replacement.run_id = NEW.id "
        "AND replacement.replaces_work_item_id IS NOT NULL "
        "AND replacement.status IN ('queued', 'running', 'ready')) AND NOT EXISTS ("
        "SELECT 1 FROM generation_work_items retried JOIN generation_events event "
        "ON event.work_item_id = retried.id AND event.run_id = NEW.id "
        "WHERE retried.run_id = NEW.id AND retried.replaces_work_item_id IS NULL "
        "AND retried.status IN ('queued', 'running') AND retried.attempt > 1 "
        "AND event.event_type = 'work_item_retry_queued') THEN "
        "RAISE(ABORT, 'recoverable Run reopens only for linked replacement or targeted retry') END; "
        "SELECT CASE WHEN OLD.status = 'failed_recoverable' "
        "AND NEW.status IN ('queued', 'running') AND EXISTS ("
        "SELECT 1 FROM generation_work_items item WHERE item.run_id = NEW.id "
        "AND NOT EXISTS (SELECT 1 FROM generation_work_items successor "
        "WHERE successor.replaces_work_item_id = item.id) "
        "AND item.status IN ('failed_recoverable', 'failed_terminal')) THEN "
        "RAISE(ABORT, 'unrelated active failures block Run reopening') END; END"
    )


def _restore_previous_postgresql_guards() -> None:
    op.execute(
        "CREATE FUNCTION guard_generation_work_item_admission() "
        "RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$ "
        "DECLARE parent_status text; BEGIN "
        "SELECT status INTO parent_status FROM generation_runs "
        "WHERE id = NEW.run_id FOR UPDATE; "
        "IF parent_status IS NULL THEN RAISE EXCEPTION 'generation run does not exist'; END IF; "
        "IF parent_status NOT IN ('queued', 'running') THEN "
        "RAISE EXCEPTION 'generation work items require an active run'; END IF; "
        "RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_generation_work_items_active_run_insert "
        "BEFORE INSERT ON generation_work_items FOR EACH ROW "
        "EXECUTE FUNCTION guard_generation_work_item_admission()"
    )
    op.execute(
        "CREATE FUNCTION guard_generation_run_ready_items() "
        "RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$ BEGIN "
        "IF NEW.status = 'ready' AND "
        "(TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'ready') THEN "
        "IF NOT EXISTS (SELECT 1 FROM generation_work_items WHERE run_id = NEW.id) THEN "
        "RAISE EXCEPTION 'ready generation run requires work items'; END IF; "
        "IF EXISTS (SELECT 1 FROM generation_work_items "
        "WHERE run_id = NEW.id AND status <> 'ready') THEN "
        "RAISE EXCEPTION 'ready generation run requires all work items ready'; END IF; "
        "END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_generation_runs_ready_requires_items "
        "BEFORE INSERT OR UPDATE ON generation_runs FOR EACH ROW "
        "EXECUTE FUNCTION guard_generation_run_ready_items()"
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite supports adding a nullable REFERENCES column directly; Alembic's
        # generic add_column path tries a separate ALTER CONSTRAINT operation.
        op.execute(
            "ALTER TABLE generation_work_items ADD COLUMN replaces_work_item_id "
            "VARCHAR REFERENCES generation_work_items(id) ON DELETE RESTRICT"
        )
    else:
        op.add_column(
            "generation_work_items",
            sa.Column(
                "replaces_work_item_id",
                sa.String(),
                sa.ForeignKey(
                    "generation_work_items.id",
                    ondelete="RESTRICT",
                    name="fk_generation_work_items_replaces_work_item",
                ),
                nullable=True,
            ),
        )
    op.create_index(
        "uq_generation_work_items_replacement_child",
        "generation_work_items",
        ["replaces_work_item_id"],
        unique=True,
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_generation_work_items_active_run_insert "
            "ON generation_work_items"
        )
        op.execute("DROP FUNCTION IF EXISTS guard_generation_work_item_admission()")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_generation_runs_ready_requires_items ON generation_runs"
        )
        op.execute("DROP FUNCTION IF EXISTS guard_generation_run_ready_items()")
        _create_postgresql_guards()
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_generation_work_items_active_run_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_requires_items_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_requires_items_update")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_reopen_for_repair")
        _create_sqlite_guards()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_generation_work_items_active_run_insert "
            "ON generation_work_items"
        )
        op.execute("DROP FUNCTION IF EXISTS guard_generation_work_item_admission()")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_generation_runs_ready_requires_items ON generation_runs"
        )
        op.execute("DROP FUNCTION IF EXISTS guard_generation_run_ready_items()")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_generation_runs_reopen_for_repair ON generation_runs"
        )
        op.execute("DROP FUNCTION IF EXISTS guard_generation_run_reopen_for_repair()")
        if (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT EXISTS (SELECT 1 FROM generation_work_items WHERE replaces_work_item_id IS NOT NULL)"
                )
            )
            .scalar()
        ):
            raise RuntimeError("cannot downgrade while WorkItem replacement lineage exists")
        op.drop_index(
            "uq_generation_work_items_replacement_child", table_name="generation_work_items"
        )
        op.drop_column("generation_work_items", "replaces_work_item_id")
        _restore_previous_postgresql_guards()
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_generation_work_items_active_run_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_requires_items_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_requires_items_update")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_reopen_for_repair")
        if (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT EXISTS (SELECT 1 FROM generation_work_items WHERE replaces_work_item_id IS NOT NULL)"
                )
            )
            .scalar()
        ):
            raise RuntimeError("cannot downgrade while WorkItem replacement lineage exists")
        op.drop_index(
            "uq_generation_work_items_replacement_child", table_name="generation_work_items"
        )
        op.execute("ALTER TABLE generation_work_items DROP COLUMN replaces_work_item_id")
        op.execute(
            "CREATE TRIGGER trg_generation_work_items_active_run_insert "
            "BEFORE INSERT ON generation_work_items BEGIN "
            "SELECT CASE WHEN (SELECT status FROM generation_runs WHERE id = NEW.run_id) "
            "NOT IN ('queued', 'running') THEN "
            "RAISE(ABORT, 'generation work items require an active Run') END; END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_runs_ready_requires_items_insert "
            "BEFORE INSERT ON generation_runs WHEN NEW.status = 'ready' BEGIN "
            "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM generation_work_items "
            "WHERE run_id = NEW.id) THEN "
            "RAISE(ABORT, 'ready generation Run requires work items') END; "
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM generation_work_items "
            "WHERE run_id = NEW.id AND status <> 'ready') THEN "
            "RAISE(ABORT, 'ready generation Run requires all work items ready') END; END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_runs_ready_requires_items_update "
            "BEFORE UPDATE OF status ON generation_runs "
            "WHEN NEW.status = 'ready' AND OLD.status <> 'ready' BEGIN "
            "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM generation_work_items "
            "WHERE run_id = NEW.id) THEN "
            "RAISE(ABORT, 'ready generation Run requires work items') END; "
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM generation_work_items "
            "WHERE run_id = NEW.id AND status <> 'ready') THEN "
            "RAISE(ABORT, 'ready generation Run requires all work items ready') END; END"
        )
