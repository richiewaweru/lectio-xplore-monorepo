"""Admit and manage independent Print/Learn native realizations (P03)."""

from __future__ import annotations

import uuid
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realization_contracts import (
    DEFAULT_VARIANT_ID,
    LEGACY_AMBIGUOUS_VARIANT,
    NativePath,
    RealizationIdentity,
    RealizationStatus,
    canonical_hash,
    package_contract_for,
    policy_for,
)
from core.database.models import NativeRealizationModel


class RealizationAdmissionError(ValueError):
    """Raised when a realization cannot be admitted or mutated."""


class RealizationReadOnlyError(RealizationAdmissionError):
    code = "REALIZATION_READ_ONLY"


def open_href_for(path: NativePath, *, output_id: str | None, status: str) -> str | None:
    if not output_id:
        return None
    if status == "read_only":
        return None
    if path == "print":
        return f"/studio/print/{output_id}"
    return f"/studio?generation_id={output_id}"


def to_identity(row: NativeRealizationModel) -> RealizationIdentity:
    path: NativePath = "print" if row.path == "print" else "learn"
    return RealizationIdentity(
        realization_id=row.id,
        path=path,
        teaching_plan_id=row.teaching_plan_id,
        teaching_plan_revision=int(row.teaching_plan_revision),
        teaching_plan_hash=row.teaching_plan_hash,
        variant_id=row.variant_id,
        native_policy_version=row.native_policy_version,
        native_policy_hash=row.native_policy_hash,
        package_contract_version=row.package_contract_version,
        package_contract_hash=row.package_contract_hash,
        realization_revision=int(row.realization_revision),
        status=row.status,  # type: ignore[arg-type]
        output_id=row.output_id,
        error_summary=row.error_summary,
        pack_id=row.pack_id,
        preparation_generation_id=row.preparation_generation_id,
        open_href=open_href_for(path, output_id=row.output_id, status=str(row.status)),
    )


async def get_realization(
    session: AsyncSession, realization_id: str
) -> NativeRealizationModel | None:
    return await session.get(NativeRealizationModel, realization_id)


async def list_realizations_for_lesson(
    session: AsyncSession,
    *,
    path_lesson_id: str,
) -> list[NativeRealizationModel]:
    result = await session.scalars(
        select(NativeRealizationModel)
        .where(NativeRealizationModel.path_lesson_id == path_lesson_id)
        .order_by(NativeRealizationModel.path, NativeRealizationModel.created_at)
    )
    return list(result.all())


async def find_realization(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    path: NativePath,
    teaching_plan_revision: int,
    variant_id: str,
    native_policy_hash: str,
    package_contract_hash: str,
) -> NativeRealizationModel | None:
    return await session.scalar(
        select(NativeRealizationModel).where(
            NativeRealizationModel.path_lesson_id == path_lesson_id,
            NativeRealizationModel.path == path,
            NativeRealizationModel.teaching_plan_revision == teaching_plan_revision,
            NativeRealizationModel.variant_id == variant_id,
            NativeRealizationModel.native_policy_hash == native_policy_hash,
            NativeRealizationModel.package_contract_hash == package_contract_hash,
        )
    )


async def resolve_by_path(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    path: NativePath,
    prefer_active: bool = True,
) -> NativeRealizationModel | None:
    """Pick the realization for status/open routing for one native path."""
    rows = await session.scalars(
        select(NativeRealizationModel)
        .where(
            NativeRealizationModel.path_lesson_id == path_lesson_id,
            NativeRealizationModel.path == path,
            NativeRealizationModel.variant_id != LEGACY_AMBIGUOUS_VARIANT,
        )
        .order_by(
            NativeRealizationModel.teaching_plan_revision.desc(),
            NativeRealizationModel.realization_revision.desc(),
            NativeRealizationModel.created_at.desc(),
        )
    )
    candidates = list(rows.all())
    if not candidates:
        return None
    if prefer_active:
        for row in candidates:
            if row.status not in {"stale", "read_only", "failed_terminal"}:
                return row
    return candidates[0]


def _new_row(
    *,
    path_lesson_id: str,
    path: NativePath,
    teaching_plan_id: str,
    teaching_plan_revision: int,
    teaching_plan_hash: str,
    variant_id: str,
    native_policy_version: str,
    native_policy_hash: str,
    package_contract_version: str,
    package_contract_hash: str,
    preparation_generation_id: str | None,
    pack_id: str | None,
    status: RealizationStatus = "queued",
    output_id: str | None = None,
    error_summary: str | None = None,
    realization_id: str | None = None,
) -> NativeRealizationModel:
    # Persist path at admission. Later default-config changes must not rewrite it.
    return NativeRealizationModel(
        id=realization_id or str(uuid.uuid4()),
        path_lesson_id=path_lesson_id,
        path=path,
        teaching_plan_id=teaching_plan_id,
        teaching_plan_revision=teaching_plan_revision,
        teaching_plan_hash=teaching_plan_hash,
        variant_id=variant_id,
        native_policy_version=native_policy_version,
        native_policy_hash=native_policy_hash,
        package_contract_version=package_contract_version,
        package_contract_hash=package_contract_hash,
        realization_revision=1,
        status=status,
        output_id=output_id,
        error_summary=error_summary,
        pack_id=pack_id,
        preparation_generation_id=preparation_generation_id,
    )


async def admit_realization(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    path: NativePath,
    teaching_plan_id: str,
    teaching_plan_revision: int,
    teaching_plan_hash: str,
    variant_id: str = DEFAULT_VARIANT_ID,
    preparation_generation_id: str | None = None,
    pack_id: str | None = None,
    output_id: str | None = None,
    native_policy_version: str | None = None,
    native_policy_hash: str | None = None,
    package_contract_version: str | None = None,
    package_contract_hash: str | None = None,
) -> tuple[NativeRealizationModel, bool]:
    """Create or reuse one realization. Returns (row, created).

    Idempotent on (lesson, path, teaching revision, variant, policy hash,
    package hash). Concurrent inserts collide on the unique constraint and
    resolve to the existing row.
    """
    policy_version, policy_hash = policy_for(path)
    package_version, package_hash = package_contract_for(path)
    if native_policy_version is not None:
        policy_version = native_policy_version
    if native_policy_hash is not None:
        policy_hash = native_policy_hash
    if package_contract_version is not None:
        package_version = package_contract_version
    if package_contract_hash is not None:
        package_hash = package_contract_hash

    existing = await find_realization(
        session,
        path_lesson_id=path_lesson_id,
        path=path,
        teaching_plan_revision=teaching_plan_revision,
        variant_id=variant_id,
        native_policy_hash=policy_hash,
        package_contract_hash=package_hash,
    )
    if existing is not None:
        if existing.status == "read_only":
            raise RealizationReadOnlyError(
                existing.error_summary
                or "Realization is read-only; regenerate with an explicit path"
            )
        return existing, False

    row = _new_row(
        path_lesson_id=path_lesson_id,
        path=path,
        teaching_plan_id=teaching_plan_id,
        teaching_plan_revision=teaching_plan_revision,
        teaching_plan_hash=teaching_plan_hash,
        variant_id=variant_id,
        native_policy_version=policy_version,
        native_policy_hash=policy_hash,
        package_contract_version=package_version,
        package_contract_hash=package_hash,
        preparation_generation_id=preparation_generation_id,
        pack_id=pack_id,
        # output_id is assigned when the native artifact is created; do not
        # invent a generation id that does not exist yet.
        output_id=output_id,
        status="queued",
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        # Unique identity won the race — reuse the surviving row.
        raced = await find_realization(
            session,
            path_lesson_id=path_lesson_id,
            path=path,
            teaching_plan_revision=teaching_plan_revision,
            variant_id=variant_id,
            native_policy_hash=policy_hash,
            package_contract_hash=package_hash,
        )
        if raced is None:
            raise RealizationAdmissionError(
                "Concurrent realization create failed without a surviving row"
            ) from None
        return raced, False
    return row, True


async def request_outputs(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    paths: Iterable[NativePath],
    teaching_plan_id: str,
    teaching_plan_revision: int,
    teaching_plan_hash: str,
    variant_id: str = DEFAULT_VARIANT_ID,
    preparation_generation_id: str | None = None,
    pack_id: str | None = None,
    native_policy_version: str | None = None,
    native_policy_hash: str | None = None,
    package_contract_version: str | None = None,
    package_contract_hash: str | None = None,
) -> list[tuple[NativeRealizationModel, bool]]:
    """Admit one or more native outputs for a lesson. Duplicates reuse rows."""
    results: list[tuple[NativeRealizationModel, bool]] = []
    for path in paths:
        results.append(
            await admit_realization(
                session,
                path_lesson_id=path_lesson_id,
                path=path,
                teaching_plan_id=teaching_plan_id,
                teaching_plan_revision=teaching_plan_revision,
                teaching_plan_hash=teaching_plan_hash,
                variant_id=variant_id,
                preparation_generation_id=preparation_generation_id,
                pack_id=pack_id,
                native_policy_version=native_policy_version,
                native_policy_hash=native_policy_hash,
                package_contract_version=package_contract_version,
                package_contract_hash=package_contract_hash,
            )
        )
    return results


async def retry_realization(
    session: AsyncSession,
    *,
    realization_id: str,
    new_output_id: str | None = None,
) -> NativeRealizationModel:
    """Regenerate one native path without touching sibling realizations or the shared plan."""
    row = await get_realization(session, realization_id)
    if row is None:
        raise RealizationAdmissionError("Realization not found")
    if row.status == "read_only":
        raise RealizationReadOnlyError(
            row.error_summary or "Read-only realization cannot be retried in place"
        )
    # Snapshot fields that must remain stable across retry.
    pinned_path = row.path
    pinned_teaching_plan_id = row.teaching_plan_id
    pinned_teaching_revision = row.teaching_plan_revision
    pinned_teaching_hash = row.teaching_plan_hash

    row.realization_revision = int(row.realization_revision) + 1
    row.output_id = new_output_id or str(uuid.uuid4())
    row.status = "queued"
    row.error_summary = None
    await session.flush()

    # Hard assertions: path and shared plan pins never flip on retry.
    assert row.path == pinned_path
    assert row.teaching_plan_id == pinned_teaching_plan_id
    assert row.teaching_plan_revision == pinned_teaching_revision
    assert row.teaching_plan_hash == pinned_teaching_hash
    return row


async def mark_stale_for_teaching_change(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    teaching_plan_id: str,
    previous_revision: int,
) -> list[NativeRealizationModel]:
    """Shared teaching revision change → dependent realizations become stale.

    Old output_id snapshots stay intact; only status moves to stale.
    """
    rows = await session.scalars(
        select(NativeRealizationModel).where(
            NativeRealizationModel.path_lesson_id == path_lesson_id,
            NativeRealizationModel.teaching_plan_id == teaching_plan_id,
            NativeRealizationModel.teaching_plan_revision == previous_revision,
            NativeRealizationModel.status.notin_(["read_only", "failed_terminal"]),
        )
    )
    updated: list[NativeRealizationModel] = []
    for row in rows.all():
        prior_output = row.output_id
        row.status = "stale"
        row.error_summary = (
            f"Shared teaching revision {previous_revision} superseded; "
            "regenerate against the approved revision"
        )
        # Preserve snapshot pointer — do not clear output_id.
        assert row.output_id == prior_output
        updated.append(row)
    await session.flush()
    return updated


async def mark_stale_for_policy_change(
    session: AsyncSession,
    *,
    path: NativePath,
    previous_policy_hash: str,
    path_lesson_id: str | None = None,
) -> list[NativeRealizationModel]:
    """Native policy hash change invalidates only that path's realizations."""
    stmt = select(NativeRealizationModel).where(
        NativeRealizationModel.path == path,
        NativeRealizationModel.native_policy_hash == previous_policy_hash,
        NativeRealizationModel.status.notin_(["read_only", "failed_terminal", "stale"]),
    )
    if path_lesson_id is not None:
        stmt = stmt.where(NativeRealizationModel.path_lesson_id == path_lesson_id)
    rows = await session.scalars(stmt)
    updated: list[NativeRealizationModel] = []
    for row in rows.all():
        row.status = "stale"
        row.error_summary = (
            f"Native policy hash changed for {path}; regenerate this realization only"
        )
        updated.append(row)
    await session.flush()
    return updated


def classify_legacy_chunked(
    chunked: dict[str, Any],
    planning_spec: dict[str, Any] | None = None,
) -> NativePath | None:
    """Classify unambiguous legacy rows. Ambiguous → None (read-only)."""
    planning = planning_spec or {}
    context = chunked.get("context") if isinstance(chunked.get("context"), dict) else {}
    control = chunked.get("control") if isinstance(chunked.get("control"), dict) else {}
    try:
        contract_version = int(planning.get("document_contract_version") or 1)
    except (TypeError, ValueError):
        contract_version = 1
    native = bool(
        chunked.get("native_whole_lesson")
        or context.get("native_whole_lesson")
        or chunked.get("page_document_v2")
        or contract_version >= 2
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
    return None


async def backfill_legacy_realization(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    pack_id: str,
    chunked: dict[str, Any],
    planning_spec: dict[str, Any] | None = None,
    generation_status: str | None = None,
) -> NativeRealizationModel:
    """Upgrade one legacy fixture row. Ambiguous → read_only, never guess."""
    classified = classify_legacy_chunked(chunked, planning_spec)
    review = chunked.get("teaching_review") if isinstance(chunked.get("teaching_review"), dict) else {}
    plan = chunked.get("teaching_plan") if isinstance(chunked.get("teaching_plan"), dict) else {}
    teaching_plan_id = str(
        chunked.get("teaching_plan_id") or plan.get("teaching_plan_id") or f"legacy-{pack_id}"
    )
    teaching_revision = int(review.get("approved_revision") or plan.get("revision") or 1)
    teaching_hash = str(
        plan.get("preparation_hash")
        or chunked.get("preparation_hash")
        or canonical_hash({"legacy": pack_id, "revision": teaching_revision})
    )

    if classified is None:
        path: NativePath = "print"
        variant_id = LEGACY_AMBIGUOUS_VARIANT
        status: RealizationStatus = "read_only"
        error = (
            "Ambiguous legacy generation markers; regenerate to admit an "
            "explicit Print or Learn realization"
        )
        policy_version = "legacy-ambiguous"
        package_version = "legacy-ambiguous"
        policy_hash = canonical_hash({"path": path, "version": policy_version, "legacy": True})
        package_hash = canonical_hash({"path": path, "version": package_version, "legacy": True})
    else:
        path = classified
        variant_id = DEFAULT_VARIANT_ID
        status = "ready" if generation_status in {"completed", "ready"} else "queued"
        error = None
        policy_version, policy_hash = policy_for(path)
        package_version, package_hash = package_contract_for(path)

    existing = await session.scalar(
        select(NativeRealizationModel).where(
            NativeRealizationModel.path_lesson_id == path_lesson_id,
            NativeRealizationModel.pack_id == pack_id,
            NativeRealizationModel.variant_id == variant_id,
        )
    )
    if existing is not None:
        return existing

    row = _new_row(
        path_lesson_id=path_lesson_id,
        path=path,
        teaching_plan_id=teaching_plan_id,
        teaching_plan_revision=teaching_revision,
        teaching_plan_hash=teaching_hash,
        variant_id=variant_id,
        native_policy_version=policy_version,
        native_policy_hash=policy_hash,
        package_contract_version=package_version,
        package_contract_hash=package_hash,
        preparation_generation_id=pack_id,
        pack_id=pack_id,
        status=status,
        output_id=pack_id,
        error_summary=error,
        realization_id=f"legacy-rz-{pack_id}",
    )
    session.add(row)
    await session.flush()
    return row


def persisted_path_is_stable(row: NativeRealizationModel, expected: NativePath) -> bool:
    """Gate helper: restart/default config must never flip a persisted path."""
    return row.path == expected


__all__ = [
    "RealizationAdmissionError",
    "RealizationReadOnlyError",
    "admit_realization",
    "backfill_legacy_realization",
    "classify_legacy_chunked",
    "find_realization",
    "get_realization",
    "list_realizations_for_lesson",
    "mark_stale_for_policy_change",
    "mark_stale_for_teaching_change",
    "open_href_for",
    "persisted_path_is_stable",
    "request_outputs",
    "resolve_by_path",
    "retry_realization",
    "to_identity",
]
