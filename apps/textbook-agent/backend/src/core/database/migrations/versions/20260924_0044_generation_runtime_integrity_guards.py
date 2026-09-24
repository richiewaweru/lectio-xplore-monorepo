"""Guard runtime work admission and whole-Run readiness."""

from __future__ import annotations

from alembic import op

revision = "20260924_0044"
down_revision = "20260924_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION guard_generation_work_item_admission() "
            "RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$ "
            "DECLARE parent_status text; BEGIN "
            "SELECT status INTO parent_status FROM generation_runs "
            "WHERE id = NEW.run_id FOR UPDATE; "
            "IF parent_status IS NULL THEN "
            "RAISE EXCEPTION 'generation run does not exist'; END IF; "
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
    elif bind.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER trg_generation_work_items_active_run_insert "
            "BEFORE INSERT ON generation_work_items BEGIN "
            "SELECT CASE WHEN (SELECT status FROM generation_runs WHERE id = NEW.run_id) "
            "NOT IN ('queued', 'running') THEN "
            "RAISE(ABORT, 'generation work items require an active run') END; END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_runs_ready_requires_items_insert "
            "BEFORE INSERT ON generation_runs WHEN NEW.status = 'ready' BEGIN "
            "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM generation_work_items "
            "WHERE run_id = NEW.id) THEN "
            "RAISE(ABORT, 'ready generation run requires work items') END; "
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM generation_work_items "
            "WHERE run_id = NEW.id AND status <> 'ready') THEN "
            "RAISE(ABORT, 'ready generation run requires all work items ready') END; END"
        )
        op.execute(
            "CREATE TRIGGER trg_generation_runs_ready_requires_items_update "
            "BEFORE UPDATE OF status ON generation_runs "
            "WHEN NEW.status = 'ready' AND OLD.status <> 'ready' BEGIN "
            "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM generation_work_items "
            "WHERE run_id = NEW.id) THEN "
            "RAISE(ABORT, 'ready generation run requires work items') END; "
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM generation_work_items "
            "WHERE run_id = NEW.id AND status <> 'ready') THEN "
            "RAISE(ABORT, 'ready generation run requires all work items ready') END; END"
        )


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
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_generation_work_items_active_run_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_requires_items_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_generation_runs_ready_requires_items_update")
