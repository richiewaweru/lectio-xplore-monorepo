"""Persistence operations for generic generation builds, runs, items, and events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infra.database.models import (
    GenerationBuildModel,
    GenerationEventModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.generation_runtime.contracts import BuildAdmission, RunAdmission, WorkItemAdmission


class GenerationRuntimeError(Exception):
    """Base for expected generation-runtime persistence failures."""


class RunAdmissionConflict(GenerationRuntimeError):
    """An idempotency key was reused for a different run identity."""


class WorkItemConflict(GenerationRuntimeError):
    """A stable work-item key was reused for a different identity."""


class RunNotFound(GenerationRuntimeError):
    """A run does not exist or is not visible to the requesting owner."""


@dataclass(frozen=True)
class AdmissionResult:
    record: GenerationRunModel | GenerationWorkItemModel
    created: bool


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def create_build(
    session: AsyncSession,
    request: BuildAdmission,
    *,
    build_id: str | None = None,
) -> GenerationBuildModel:
    owner = await session.get(UserModel, request.owner_user_id)
    if owner is None:
        raise ValueError("generation build owner does not exist")
    lesson_owner = await session.scalar(
        select(UnitModel.owner_id)
        .select_from(PathLessonModel)
        .join(PathVersionModel, PathVersionModel.id == PathLessonModel.path_version_id)
        .join(UnitModel, UnitModel.id == PathVersionModel.unit_id)
        .where(PathLessonModel.id == request.path_lesson_id)
    )
    if lesson_owner != request.owner_user_id:
        raise ValueError("generation build path lesson is unavailable to this owner")
    build = GenerationBuildModel(
        id=build_id or str(uuid.uuid4()),
        owner_user_id=request.owner_user_id,
        path_lesson_id=request.path_lesson_id,
    )
    session.add(build)
    await session.flush()
    return build


def _run_identity_matches(run: GenerationRunModel, request: RunAdmission) -> bool:
    return (
        run.build_id == request.build_id
        and run.owner_user_id == request.owner_user_id
        and run.run_type == str(request.run_type)
        and run.source_artifact_type == request.source_artifact_type
        and run.source_artifact_id == request.source_artifact_id
        and run.source_revision == request.source_revision
        and run.source_hash == request.source_hash
    )


async def admit_run(session: AsyncSession, request: RunAdmission) -> AdmissionResult:
    """Create or reuse a run under owner/run-type/request-key idempotency."""
    build = await session.get(GenerationBuildModel, request.build_id)
    if build is None or build.owner_user_id != request.owner_user_id:
        raise RunNotFound("generation build is unavailable to this owner")

    key_filter = (
        GenerationRunModel.owner_user_id == request.owner_user_id,
        GenerationRunModel.request_key == request.request_key,
    )
    existing = await session.scalar(select(GenerationRunModel).where(*key_filter))
    if existing is not None:
        if not _run_identity_matches(existing, request):
            raise RunAdmissionConflict("request key is already bound to a different run identity")
        return AdmissionResult(existing, created=False)

    run = GenerationRunModel(
        id=str(uuid.uuid4()),
        build_id=request.build_id,
        run_type=str(request.run_type),
        owner_user_id=request.owner_user_id,
        status="queued",
        stage=request.stage,
        attempt=1,
        source_artifact_type=request.source_artifact_type,
        source_artifact_id=request.source_artifact_id,
        source_revision=request.source_revision,
        source_hash=request.source_hash,
        request_key=request.request_key,
    )
    try:
        # The unique constraint remains the concurrency authority; the savepoint
        # lets an idempotent loser recover without rolling back caller work.
        async with session.begin_nested():
            session.add(run)
            await session.flush()
    except IntegrityError:
        existing = await session.scalar(select(GenerationRunModel).where(*key_filter))
        if existing is None:
            raise
        if not _run_identity_matches(existing, request):
            raise RunAdmissionConflict("request key is already bound to a different run identity")
        return AdmissionResult(existing, created=False)
    return AdmissionResult(run, created=True)


def _work_item_identity_matches(
    item: GenerationWorkItemModel,
    request: WorkItemAdmission,
) -> bool:
    return (
        item.stage == request.stage
        and item.input_hash == request.input_hash
        and item.definition_hash == request.definition_hash
        and item.composition_identity == request.composition_identity
        and item.max_attempts == request.max_attempts
    )


async def add_work_item(
    session: AsyncSession,
    request: WorkItemAdmission,
) -> AdmissionResult:
    """Create a stable item key, or return the existing item with identical identity."""
    if await session.get(GenerationRunModel, request.run_id) is None:
        raise RunNotFound("generation run does not exist")
    key_filter = (
        GenerationWorkItemModel.run_id == request.run_id,
        GenerationWorkItemModel.item_key == request.item_key,
    )
    existing = await session.scalar(select(GenerationWorkItemModel).where(*key_filter))
    if existing is not None:
        if not _work_item_identity_matches(existing, request):
            raise WorkItemConflict("item key is already bound to a different work-item identity")
        return AdmissionResult(existing, created=False)

    item = GenerationWorkItemModel(
        id=str(uuid.uuid4()),
        run_id=request.run_id,
        item_key=request.item_key,
        stage=request.stage,
        status="queued",
        attempt=1,
        max_attempts=request.max_attempts,
        input_hash=request.input_hash,
        definition_hash=request.definition_hash,
        composition_identity=request.composition_identity,
    )
    try:
        async with session.begin_nested():
            session.add(item)
            await session.flush()
    except IntegrityError:
        existing = await session.scalar(select(GenerationWorkItemModel).where(*key_filter))
        if existing is None:
            raise
        if not _work_item_identity_matches(existing, request):
            raise WorkItemConflict("item key is already bound to a different work-item identity")
        return AdmissionResult(existing, created=False)
    return AdmissionResult(item, created=True)


async def append_event(
    session: AsyncSession,
    *,
    run_id: str,
    event_type: str,
    work_item_id: str | None = None,
    safe_payload: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> GenerationEventModel:
    """Append the next per-run event sequence number within the caller transaction."""
    if not event_type.strip():
        raise ValueError("event_type must be non-empty")

    bind = session.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite ignores FOR UPDATE. Lock the stable parent build row instead
        # of updating the run, whose ready state is immutable.
        build_id = await session.scalar(
            select(GenerationRunModel.build_id).where(GenerationRunModel.id == run_id)
        )
        if build_id is None:
            raise RunNotFound("generation run does not exist")
        await session.execute(
            update(GenerationBuildModel)
            .where(GenerationBuildModel.id == build_id)
            .values(created_at=GenerationBuildModel.created_at)
        )

    run = await session.scalar(
        select(GenerationRunModel).where(GenerationRunModel.id == run_id).with_for_update()
    )
    if run is None:
        raise RunNotFound("generation run does not exist")

    work_item = None
    if work_item_id is not None:
        work_item = await session.scalar(
            select(GenerationWorkItemModel).where(
                GenerationWorkItemModel.id == work_item_id,
                GenerationWorkItemModel.run_id == run_id,
            )
        )
        if work_item is None:
            raise ValueError("work item does not belong to generation run")

    next_seq = (
        int(
            await session.scalar(
                select(func.coalesce(func.max(GenerationEventModel.seq), 0)).where(
                    GenerationEventModel.run_id == run_id
                )
            )
            or 0
        )
        + 1
    )
    record = GenerationEventModel(
        id=str(uuid.uuid4()),
        run_id=run_id,
        work_item_id=work_item_id,
        seq=next_seq,
        event_type=event_type,
        status=work_item.status if work_item is not None else run.status,
        stage=work_item.stage if work_item is not None else run.stage,
        attempt=work_item.attempt if work_item is not None else run.attempt,
        error_code=error_code,
        safe_payload_json=dict(safe_payload or {}),
    )
    session.add(record)
    await session.flush()
    return record


async def get_run_status(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
) -> GenerationRunModel | None:
    """Read current run and stable work-item state only within its owner scope."""
    return await session.scalar(
        select(GenerationRunModel)
        .options(selectinload(GenerationRunModel.work_items))
        .where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
    )
