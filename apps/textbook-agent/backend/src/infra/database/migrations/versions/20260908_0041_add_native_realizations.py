"""Add native_realizations table with legacy read-only backfill.

Revision ID: 20260908_0041
Revises: 20260907_0040
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "20260908_0041"
down_revision = "20260907_0040"
branch_labels = None
depends_on = None

DEFAULT_VARIANT = "everyone"
READ_ONLY = "read_only"
QUEUED = "queued"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_mapping(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _classify_legacy(chunked: dict, planning_spec: dict) -> str | None:
    """Return print|learn when unambiguous; None when provenance must not be guessed."""
    context = chunked.get("context") if isinstance(chunked.get("context"), dict) else {}
    control = chunked.get("control") if isinstance(chunked.get("control"), dict) else {}
    native = bool(
        chunked.get("native_whole_lesson")
        or context.get("native_whole_lesson")
        or chunked.get("page_document_v2")
        or int(planning_spec.get("document_contract_version") or 1) >= 2
    )
    learn = control.get("pipeline") == "component_lectio" and not native
    shared = bool(chunked.get("shared_preparation") or context.get("shared_preparation"))
    if shared and not native and not learn:
        return None
    if native and learn:
        return None
    if native:
        return "print"
    if learn:
        return "learn"
    if native is False and control.get("pipeline") in {None, ""} and not shared:
        # Pre-dual-path row with no clear marker — do not invent a path.
        return None
    return None


def upgrade() -> None:
    op.create_table(
        "native_realizations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("path_lesson_id", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("teaching_plan_id", sa.String(), nullable=False),
        sa.Column("teaching_plan_revision", sa.Integer(), nullable=False),
        sa.Column("teaching_plan_hash", sa.String(), nullable=False),
        sa.Column("variant_id", sa.String(), nullable=False, server_default=DEFAULT_VARIANT),
        sa.Column("native_policy_version", sa.String(), nullable=False),
        sa.Column("native_policy_hash", sa.String(), nullable=False),
        sa.Column("package_contract_version", sa.String(), nullable=False),
        sa.Column("package_contract_hash", sa.String(), nullable=False),
        sa.Column("realization_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=False, server_default=QUEUED),
        sa.Column("output_id", sa.String(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("pack_id", sa.String(), nullable=True),
        sa.Column("preparation_generation_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["path_lesson_id"], ["path_lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "path_lesson_id",
            "path",
            "teaching_plan_revision",
            "variant_id",
            "native_policy_hash",
            "package_contract_hash",
            name="uq_native_realization_identity",
        ),
    )
    op.create_index(
        "ix_native_realizations_path_lesson_id", "native_realizations", ["path_lesson_id"]
    )
    op.create_index("ix_native_realizations_path", "native_realizations", ["path"])
    op.create_index("ix_native_realizations_output_id", "native_realizations", ["output_id"])
    op.create_index("ix_native_realizations_status", "native_realizations", ["status"])
    op.create_index(
        "ix_native_realizations_teaching_plan_id", "native_realizations", ["teaching_plan_id"]
    )

    bind = op.get_bind()
    lessons = bind.execute(
        sa.text(
            "SELECT id, pack_id FROM path_lessons WHERE pack_id IS NOT NULL"
        )
    ).mappings().all()
    now = _utcnow()
    for lesson in lessons:
        pack_id = lesson["pack_id"]
        gen = bind.execute(
            sa.text(
                "SELECT id, chunked_state_json, planning_spec_json, status "
                "FROM generations WHERE id = :gid"
            ),
            {"gid": pack_id},
        ).mappings().first()
        if gen is None:
            continue
        chunked = _as_mapping(gen["chunked_state_json"])
        planning = _as_mapping(gen["planning_spec_json"])
        classified = _classify_legacy(chunked, planning)
        review = chunked.get("teaching_review") if isinstance(chunked.get("teaching_review"), dict) else {}
        plan = chunked.get("teaching_plan") if isinstance(chunked.get("teaching_plan"), dict) else {}
        teaching_plan_id = str(
            chunked.get("teaching_plan_id")
            or plan.get("teaching_plan_id")
            or f"legacy-{pack_id}"
        )
        teaching_revision = int(
            review.get("approved_revision")
            or plan.get("revision")
            or 1
        )
        teaching_hash = str(
            plan.get("preparation_hash")
            or chunked.get("preparation_hash")
            or _sha({"legacy": pack_id, "revision": teaching_revision})
        )
        if classified is None:
            # Ambiguous: explicit read-only placeholder — never guess Print vs Learn.
            # variant_id keeps this out of the normal idempotency key so regenerate
            # can still admit explicit print|learn rows.
            path = "print"
            variant_id = "legacy-ambiguous"
            status = READ_ONLY
            error = (
                "Ambiguous legacy generation markers; regenerate to admit an "
                "explicit Print or Learn realization"
            )
            policy_version = "legacy-ambiguous"
            package_version = "legacy-ambiguous"
        else:
            path = classified
            variant_id = DEFAULT_VARIANT
            status = QUEUED if str(gen["status"] or "") not in {"completed", "ready"} else "ready"
            error = None
            policy_version = f"{path}-policy-1"
            package_version = "1.0.0"
        policy_hash = _sha({"path": path, "version": policy_version, "legacy": True})
        package_hash = _sha({"path": path, "version": package_version, "legacy": True})
        bind.execute(
            sa.text(
                """
                INSERT INTO native_realizations (
                    id, path_lesson_id, path, teaching_plan_id, teaching_plan_revision,
                    teaching_plan_hash, variant_id, native_policy_version, native_policy_hash,
                    package_contract_version, package_contract_hash, realization_revision,
                    status, output_id, error_summary, pack_id, preparation_generation_id,
                    created_at, updated_at
                ) VALUES (
                    :id, :path_lesson_id, :path, :teaching_plan_id, :teaching_plan_revision,
                    :teaching_plan_hash, :variant_id, :native_policy_version, :native_policy_hash,
                    :package_contract_version, :package_contract_hash, 1,
                    :status, :output_id, :error_summary, :pack_id, :preparation_generation_id,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "id": f"legacy-rz-{pack_id}",
                "path_lesson_id": lesson["id"],
                "path": path,
                "teaching_plan_id": teaching_plan_id,
                "teaching_plan_revision": teaching_revision,
                "teaching_plan_hash": teaching_hash,
                "variant_id": variant_id,
                "native_policy_version": policy_version,
                "native_policy_hash": policy_hash,
                "package_contract_version": package_version,
                "package_contract_hash": package_hash,
                "status": status,
                "output_id": pack_id,
                "error_summary": error,
                "pack_id": pack_id,
                "preparation_generation_id": pack_id,
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_native_realizations_teaching_plan_id", table_name="native_realizations")
    op.drop_index("ix_native_realizations_status", table_name="native_realizations")
    op.drop_index("ix_native_realizations_output_id", table_name="native_realizations")
    op.drop_index("ix_native_realizations_path", table_name="native_realizations")
    op.drop_index("ix_native_realizations_path_lesson_id", table_name="native_realizations")
    op.drop_table("native_realizations")
