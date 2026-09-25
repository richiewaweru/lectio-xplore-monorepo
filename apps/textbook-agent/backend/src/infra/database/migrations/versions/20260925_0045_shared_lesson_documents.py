"""Persist immutable SharedLessonDocument aggregates.

Revision ID: 20260925_0045
Revises: 20260924_0044
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260925_0045"
down_revision = "20260924_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    document_json_type = sa.JSON().with_variant(
        postgresql.JSONB(astext_type=sa.Text()), "postgresql"
    )
    op.create_table(
        "shared_lesson_documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("path_lesson_id", sa.String(), nullable=False),
        sa.Column("teaching_plan_id", sa.String(), nullable=False),
        sa.Column("teaching_plan_revision", sa.Integer(), nullable=False),
        sa.Column("teaching_plan_hash", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("document_json", document_json_type, nullable=False),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "revision >= 1", name="ck_shared_lesson_documents_revision_positive"
        ),
        sa.CheckConstraint(
            "teaching_plan_revision >= 1",
            name="ck_shared_lesson_documents_plan_revision_positive",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'ready')", name="ck_shared_lesson_documents_status"
        ),
        sa.ForeignKeyConstraint(
            ["path_lesson_id"], ["path_lessons.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", "revision", name="pk_shared_lesson_documents"),
    )
    op.create_index(
        "ix_shared_lesson_documents_path_lesson",
        "shared_lesson_documents",
        ["path_lesson_id"],
    )
    op.create_index(
        "ix_shared_lesson_documents_content_hash",
        "shared_lesson_documents",
        ["content_hash"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION guard_shared_lesson_document_update() "
            "RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$ BEGIN "
            "IF OLD.status = 'ready' THEN "
            "RAISE EXCEPTION 'ready shared lesson documents are immutable'; END IF; "
            "IF OLD.id IS DISTINCT FROM NEW.id OR OLD.revision IS DISTINCT FROM NEW.revision "
            "OR OLD.path_lesson_id IS DISTINCT FROM NEW.path_lesson_id "
            "OR OLD.teaching_plan_id IS DISTINCT FROM NEW.teaching_plan_id "
            "OR OLD.teaching_plan_revision IS DISTINCT FROM NEW.teaching_plan_revision "
            "OR OLD.teaching_plan_hash IS DISTINCT FROM NEW.teaching_plan_hash "
            "OR OLD.content_hash IS DISTINCT FROM NEW.content_hash "
            "OR OLD.document_json IS DISTINCT FROM NEW.document_json "
            "OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN "
            "RAISE EXCEPTION 'stored shared lesson document identity and JSON are immutable'; "
            "END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_shared_lesson_document_update "
            "BEFORE UPDATE ON shared_lesson_documents FOR EACH ROW "
            "EXECUTE FUNCTION guard_shared_lesson_document_update()"
        )
        op.execute(
            "CREATE FUNCTION guard_shared_lesson_document_delete() "
            "RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$ BEGIN "
            "IF OLD.status = 'ready' THEN "
            "RAISE EXCEPTION 'ready shared lesson documents are immutable'; END IF; "
            "RETURN OLD; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_shared_lesson_document_delete "
            "BEFORE DELETE ON shared_lesson_documents FOR EACH ROW "
            "EXECUTE FUNCTION guard_shared_lesson_document_delete()"
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER trg_shared_lesson_document_update "
            "BEFORE UPDATE ON shared_lesson_documents "
            "WHEN OLD.status = 'ready' OR OLD.id IS NOT NEW.id "
            "OR OLD.revision IS NOT NEW.revision "
            "OR OLD.path_lesson_id IS NOT NEW.path_lesson_id "
            "OR OLD.teaching_plan_id IS NOT NEW.teaching_plan_id "
            "OR OLD.teaching_plan_revision IS NOT NEW.teaching_plan_revision "
            "OR OLD.teaching_plan_hash IS NOT NEW.teaching_plan_hash "
            "OR OLD.content_hash IS NOT NEW.content_hash "
            "OR OLD.document_json IS NOT NEW.document_json "
            "OR OLD.created_at IS NOT NEW.created_at BEGIN "
            "SELECT RAISE(ABORT, 'stored shared lesson document identity and JSON are immutable'); "
            "END"
        )
        op.execute(
            "CREATE TRIGGER trg_shared_lesson_document_delete "
            "BEFORE DELETE ON shared_lesson_documents "
            "WHEN OLD.status = 'ready' BEGIN "
            "SELECT RAISE(ABORT, 'ready shared lesson documents are immutable'); END"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_shared_lesson_document_update "
            "ON shared_lesson_documents"
        )
        op.execute("DROP FUNCTION IF EXISTS guard_shared_lesson_document_update()")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_shared_lesson_document_delete "
            "ON shared_lesson_documents"
        )
        op.execute("DROP FUNCTION IF EXISTS guard_shared_lesson_document_delete()")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_shared_lesson_document_update")
        op.execute("DROP TRIGGER IF EXISTS trg_shared_lesson_document_delete")
    op.drop_index("ix_shared_lesson_documents_content_hash", table_name="shared_lesson_documents")
    op.drop_index("ix_shared_lesson_documents_path_lesson", table_name="shared_lesson_documents")
    op.drop_table("shared_lesson_documents")
