"""Persistence operations for generic generation builds, runs, items, and events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
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
from infra.execution.checkpoints import content_hash
from infra.execution.leases import DEFAULT_LEASE_SECONDS, LeaseLostError
from infra.generation_runtime.contracts import (
    BuildAdmission,
    RunAdmission,
    RuntimeCheckpoint,
    RuntimeCheckpointCompatibility,
    SourceIdentity,
    WorkItemAdmission,
)


class GenerationRuntimeError(Exception):
    """Base for expected generation-runtime persistence failures."""


class RunAdmissionConflict(GenerationRuntimeError):
    """An idempotency key was reused for a different run identity."""


class WorkItemConflict(GenerationRuntimeError):
    """A stable work-item key was reused for a different identity."""


class RunNotFound(GenerationRuntimeError):
    """A run does not exist or is not visible to the requesting owner."""


class WorkItemNotFound(GenerationRuntimeError):
    """A work item does not exist."""


class WorkItemUnavailable(GenerationRuntimeError):
    """A work item is not claimable or another worker currently holds its row lock."""


class SourceIdentityConflict(GenerationRuntimeError):
    """The freshly recomputed source does not match the admitted run lineage."""


class AttemptLimitExceeded(GenerationRuntimeError):
    """The work item exhausted its bounded attempts without a new claim."""


class CheckpointCompatibilityError(GenerationRuntimeError):
    """Checkpoint reuse was requested under different source or definition inputs."""


class CheckpointIntegrityError(GenerationRuntimeError):
    """Persisted checkpoint data is malformed or its payload hash changed."""


@dataclass(frozen=True)
class AdmissionResult:
    record: GenerationRunModel | GenerationWorkItemModel
    created: bool


def _utcnow(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is not None:
        return current.astimezone(UTC).replace(tzinfo=None)
    return current


def _lease_deadline(now: datetime, lease_seconds: int) -> datetime:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    return now + timedelta(seconds=lease_seconds)


async def _execute_fenced_update(session: AsyncSession, statement: Any) -> Any:
    try:
        async with session.begin_nested():
            return await session.execute(statement)
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise LeaseLostError("work-item lease changed during a fenced update") from exc
        raise


def _assert_source_identity(run: GenerationRunModel, source: SourceIdentity) -> None:
    persisted = (
        run.source_artifact_type,
        run.source_artifact_id,
        run.source_revision,
        run.source_hash,
    )
    observed = (
        source.source_artifact_type,
        source.source_artifact_id,
        source.source_revision,
        source.source_hash,
    )
    if persisted != observed:
        raise SourceIdentityConflict("fresh source identity differs from the admitted run")


async def claim_work_item(
    session: AsyncSession,
    *,
    work_item_id: str,
    worker_id: str,
    source: SourceIdentity,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> GenerationWorkItemModel:
    """Claim a queued or expired item under a new monotonically increasing fence."""
    if not worker_id.strip():
        raise ValueError("worker_id must be non-empty")
    current_time = _utcnow(now)
    lease_expires_at = _lease_deadline(current_time, lease_seconds)

    selected = await session.execute(
        select(GenerationWorkItemModel, GenerationRunModel)
        .join(GenerationRunModel, GenerationRunModel.id == GenerationWorkItemModel.run_id)
        .where(GenerationWorkItemModel.id == work_item_id)
        .with_for_update(skip_locked=True, of=GenerationWorkItemModel)
    )
    row = selected.first()
    if row is None:
        if await session.get(GenerationWorkItemModel, work_item_id) is None:
            raise WorkItemNotFound("generation work item does not exist")
        raise WorkItemUnavailable("generation work item is locked or already claimed")
    item, run = row

    # Source validation happens before any lease, attempt, or status mutation.
    _assert_source_identity(run, source)
    if run.status not in {"queued", "running"}:
        raise WorkItemUnavailable("generation run is not active for work-item claims")

    prior_status = item.status
    prior_attempt = item.attempt
    prior_token = item.lease_token
    prior_expiry = item.lease_expires_at
    if prior_status == "queued":
        if prior_attempt > item.max_attempts:
            raise AttemptLimitExceeded("work item attempt exceeds max_attempts")
        next_attempt = prior_attempt
    elif (
        prior_status == "running"
        and prior_expiry is not None
        and _utcnow(prior_expiry) <= current_time
    ):
        if prior_attempt >= item.max_attempts:
            raise AttemptLimitExceeded("expired work item exhausted max_attempts")
        next_attempt = prior_attempt + 1
    else:
        raise WorkItemUnavailable("generation work item is not queued or expired")

    next_token = (prior_token or 0) + 1
    predicates = [
        GenerationWorkItemModel.id == item.id,
        GenerationWorkItemModel.status == prior_status,
        GenerationWorkItemModel.attempt == prior_attempt,
        (
            GenerationWorkItemModel.lease_token.is_(None)
            if prior_token is None
            else GenerationWorkItemModel.lease_token == prior_token
        ),
        (
            GenerationWorkItemModel.lease_expires_at.is_(None)
            if prior_expiry is None
            else GenerationWorkItemModel.lease_expires_at == prior_expiry
        ),
    ]
    try:
        # The conditional update is the SQLite equivalent of row locking. It
        # prevents two readers of the same queued snapshot from both claiming.
        async with session.begin_nested():
            result = await session.execute(
                update(GenerationWorkItemModel)
                .where(*predicates)
                .values(
                    status="running",
                    attempt=next_attempt,
                    lease_owner=worker_id,
                    lease_token=next_token,
                    lease_expires_at=lease_expires_at,
                    started_at=item.started_at or current_time,
                    updated_at=current_time,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise WorkItemUnavailable("generation work item was claimed concurrently")

            if run.status == "queued":
                run_started = await session.execute(
                    update(GenerationRunModel)
                    .where(
                        GenerationRunModel.id == run.id,
                        GenerationRunModel.status == "queued",
                    )
                    .values(
                        status="running",
                        started_at=func.coalesce(GenerationRunModel.started_at, current_time),
                        updated_at=current_time,
                    )
                )
                if run_started.rowcount != 1:
                    current_run_status = await session.scalar(
                        select(GenerationRunModel.status)
                        .where(GenerationRunModel.id == run.id)
                        .with_for_update(read=True)
                    )
                    if current_run_status != "running":
                        raise WorkItemUnavailable("generation run changed before item claim")
            else:
                current_run_status = await session.scalar(
                    select(GenerationRunModel.status)
                    .where(GenerationRunModel.id == run.id)
                    .with_for_update(read=True)
                )
                if current_run_status != "running":
                    raise WorkItemUnavailable("generation run changed before item claim")
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise WorkItemUnavailable("generation work item is contended") from exc
        raise
    await session.refresh(item)
    return item


async def _require_live_lease(
    session: AsyncSession,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    now: datetime,
) -> GenerationWorkItemModel:
    item = await session.scalar(
        select(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == work_item_id)
        .with_for_update(skip_locked=True)
    )
    if (
        item is None
        or item.status != "running"
        or item.lease_owner != worker_id
        or item.lease_token != lease_token
        or item.lease_expires_at is None
        or _utcnow(item.lease_expires_at) <= now
    ):
        raise LeaseLostError("worker no longer holds a live work-item lease")
    return item


async def heartbeat_work_item(
    session: AsyncSession,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> GenerationWorkItemModel:
    """Extend a live lease only while its owner and fence still match."""
    current_time = _utcnow(now)
    new_expiry = _lease_deadline(current_time, lease_seconds)
    result = await _execute_fenced_update(
        session,
        update(GenerationWorkItemModel)
        .where(
            GenerationWorkItemModel.id == work_item_id,
            GenerationWorkItemModel.status == "running",
            GenerationWorkItemModel.lease_owner == worker_id,
            GenerationWorkItemModel.lease_token == lease_token,
            GenerationWorkItemModel.lease_expires_at > current_time,
        )
        .values(lease_expires_at=new_expiry, updated_at=current_time)
        .execution_options(synchronize_session=False),
    )
    if result.rowcount != 1:
        raise LeaseLostError("worker no longer holds a live work-item lease")
    item = await session.get(GenerationWorkItemModel, work_item_id)
    if item is None:
        raise LeaseLostError("generation work item disappeared during heartbeat")
    await session.refresh(item)
    return item


def _assert_checkpoint_compatibility(
    run: GenerationRunModel,
    item: GenerationWorkItemModel,
    compatibility: RuntimeCheckpointCompatibility,
) -> None:
    expected = (
        run.source_revision,
        run.source_hash,
        item.input_hash,
        item.definition_hash,
        item.composition_identity,
    )
    supplied = (
        compatibility.source_revision,
        compatibility.source_hash,
        compatibility.input_hash,
        compatibility.definition_hash,
        compatibility.composition_identity,
    )
    if expected != supplied:
        raise CheckpointCompatibilityError(
            "checkpoint source, input, definition, or composition identity differs"
        )


def _decode_checkpoint(value: Any) -> RuntimeCheckpoint:
    try:
        checkpoint = RuntimeCheckpoint.model_validate(value)
    except ValidationError as exc:
        raise CheckpointIntegrityError("persisted checkpoint does not match its contract") from exc
    if content_hash(checkpoint.payload) != checkpoint.payload_hash:
        raise CheckpointIntegrityError("persisted checkpoint payload hash changed")
    return checkpoint


async def persist_checkpoint(
    session: AsyncSession,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    compatibility: RuntimeCheckpointCompatibility,
    payload: Any,
    now: datetime | None = None,
) -> RuntimeCheckpoint:
    """Persist a serializable checkpoint only under the live worker fence."""
    current_time = _utcnow(now)
    item = await _require_live_lease(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        lease_token=lease_token,
        now=current_time,
    )
    run = await session.get(GenerationRunModel, item.run_id)
    if run is None:
        raise RunNotFound("generation run does not exist")
    _assert_checkpoint_compatibility(run, item, compatibility)
    if item.checkpoint_json is not None:
        existing = _decode_checkpoint(item.checkpoint_json)
        if existing.compatibility != compatibility:
            raise CheckpointCompatibilityError(
                "existing checkpoint has different compatibility inputs"
            )
    checkpoint = RuntimeCheckpoint(
        compatibility=compatibility,
        payload=payload,
        payload_hash=content_hash(payload),
    )
    run_identity_matches = (
        select(GenerationRunModel.id)
        .where(
            GenerationRunModel.id == GenerationWorkItemModel.run_id,
            GenerationRunModel.source_revision == compatibility.source_revision,
            GenerationRunModel.source_hash == compatibility.source_hash,
        )
        .exists()
    )
    result = await _execute_fenced_update(
        session,
        update(GenerationWorkItemModel)
        .where(
            GenerationWorkItemModel.id == work_item_id,
            GenerationWorkItemModel.status == "running",
            GenerationWorkItemModel.lease_owner == worker_id,
            GenerationWorkItemModel.lease_token == lease_token,
            GenerationWorkItemModel.lease_expires_at > current_time,
            GenerationWorkItemModel.input_hash == compatibility.input_hash,
            GenerationWorkItemModel.definition_hash == compatibility.definition_hash,
            GenerationWorkItemModel.composition_identity == compatibility.composition_identity,
            run_identity_matches,
        )
        .values(
            checkpoint_json=checkpoint.model_dump(mode="json"),
            updated_at=current_time,
        )
        .execution_options(synchronize_session=False),
    )
    if result.rowcount != 1:
        raise LeaseLostError("work-item lease changed before checkpoint persistence")
    await session.refresh(item)
    return checkpoint


async def load_compatible_checkpoint(
    session: AsyncSession,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    compatibility: RuntimeCheckpointCompatibility,
    now: datetime | None = None,
) -> RuntimeCheckpoint | None:
    """Load a checkpoint only for a live fence and an exact compatibility match."""
    item = await _require_live_lease(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        lease_token=lease_token,
        now=_utcnow(now),
    )
    run = await session.get(GenerationRunModel, item.run_id)
    if run is None:
        raise RunNotFound("generation run does not exist")
    _assert_checkpoint_compatibility(run, item, compatibility)
    if item.checkpoint_json is None:
        return None
    checkpoint = _decode_checkpoint(item.checkpoint_json)
    if checkpoint.compatibility != compatibility:
        raise CheckpointCompatibilityError("persisted checkpoint compatibility differs")
    return checkpoint


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
