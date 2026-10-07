"""Persistence operations for generic generation builds, runs, items, and events."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import JsonValue, TypeAdapter, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

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
    ErrorClass,
    RecoveryAction,
    RunAdmission,
    RunFailure,
    RunFinalization,
    RuntimeCheckpoint,
    RuntimeCheckpointCompatibility,
    SourceIdentity,
    VerifiedArtifact,
    WorkItemAdmission,
    WorkItemFailure,
    WorkItemReplacement,
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


class OutputValidationError(GenerationRuntimeError):
    """A work-item output is not a canonical JSON value."""


class OutputHashMismatch(GenerationRuntimeError):
    """The claimed output digest does not match the canonical output value."""


class InvalidWorkItemTransition(GenerationRuntimeError):
    """A work item cannot move from its current state to the requested state."""


class InvalidRunTransition(GenerationRuntimeError):
    """A generation run cannot move to the requested terminal state."""


class SourceVerificationError(GenerationRuntimeError):
    """The trusted source verifier could not reproduce the admitted identity."""


class ArtifactVerificationError(GenerationRuntimeError):
    """The trusted artifact loader could not load a canonical persisted artifact."""


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


_JSON_VALUE_ADAPTER = TypeAdapter(JsonValue)


def _canonical_json_value(value: Any) -> tuple[JsonValue, str]:
    try:
        validated = _JSON_VALUE_ADAPTER.validate_python(value, strict=True)
        json.dumps(validated, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValidationError, TypeError, ValueError) as exc:
        raise OutputValidationError("work-item output must be strict JSON") from exc
    return validated, content_hash(validated)


def _active_leaf_clause():
    successor = aliased(GenerationWorkItemModel)
    return (
        ~select(successor.id)
        .where(successor.replaces_work_item_id == GenerationWorkItemModel.id)
        .exists()
    )


def active_work_items(
    items: Iterable[GenerationWorkItemModel],
) -> tuple[GenerationWorkItemModel, ...]:
    """Return current replacement-chain leaves while retaining old rows as history."""
    materialized = tuple(items)
    replaced_ids = {
        item.replaces_work_item_id for item in materialized if item.replaces_work_item_id
    }
    return tuple(item for item in materialized if item.id not in replaced_ids)


async def _lock_run_for_item(
    session: AsyncSession,
    *,
    run_id: str,
    allow_failed_terminal: bool = False,
    allow_failed_recoverable: bool = False,
) -> GenerationRunModel:
    run = await session.scalar(
        select(GenerationRunModel)
        .where(GenerationRunModel.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise RunNotFound("generation run does not exist")
    allowed = {"queued", "running"}
    if allow_failed_terminal:
        allowed.add("failed_terminal")
    if allow_failed_recoverable:
        allowed.add("failed_recoverable")
    if run.status not in allowed:
        raise LeaseLostError("parent generation run is no longer active")
    return run


async def _serialize_run_build_on_sqlite(
    session: AsyncSession,
    *,
    run_id: str,
) -> None:
    """Acquire SQLite's writer lock on the stable Build row for Run mutations."""
    if session.get_bind().dialect.name != "sqlite":
        return
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


async def _execute_fenced_update(session: AsyncSession, statement: Any) -> Any:
    try:
        async with session.begin_nested():
            return await session.execute(statement)
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise LeaseLostError("work-item lease changed during a fenced update") from exc
        raise


def _live_item_update(
    *,
    item: GenerationWorkItemModel,
    worker_id: str,
    lease_token: int,
    now: datetime,
    values: dict[str, Any],
) -> Any:
    active_run = (
        select(GenerationRunModel.id)
        .where(
            GenerationRunModel.id == item.run_id,
            GenerationRunModel.status.in_({"queued", "running"}),
        )
        .exists()
    )
    return (
        update(GenerationWorkItemModel)
        .where(
            GenerationWorkItemModel.id == item.id,
            GenerationWorkItemModel.run_id == item.run_id,
            GenerationWorkItemModel.status == "running",
            GenerationWorkItemModel.attempt == item.attempt,
            GenerationWorkItemModel.lease_owner == worker_id,
            GenerationWorkItemModel.lease_token == lease_token,
            GenerationWorkItemModel.lease_expires_at > now,
            active_run,
            _active_leaf_clause(),
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )


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
    """Claim work; reconcile an expired, exhausted item instead of leaving it running."""
    if not worker_id.strip():
        raise ValueError("worker_id must be non-empty")
    current_time = _utcnow(now)
    lease_expires_at = _lease_deadline(current_time, lease_seconds)

    selected = await session.execute(
        select(GenerationWorkItemModel, GenerationRunModel)
        .join(GenerationRunModel, GenerationRunModel.id == GenerationWorkItemModel.run_id)
        .where(
            GenerationWorkItemModel.id == work_item_id,
            _active_leaf_clause(),
        )
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
            return await reconcile_expired_work_item(
                session,
                work_item_id=work_item_id,
                now=current_time,
            )
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
        _active_leaf_clause(),
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

            # Lock order is item -> Run, and the Run lock is taken exclusively
            # (never FOR SHARE).  Every later step of the same transaction
            # (checkpoint load, completion, failure) re-locks the Run FOR
            # UPDATE; two concurrent claims each holding a shared Run lock
            # would deadlock on that upgrade.
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
                        .with_for_update()
                    )
                    if current_run_status != "running":
                        raise WorkItemUnavailable("generation run changed before item claim")
            else:
                current_run_status = await session.scalar(
                    select(GenerationRunModel.status)
                    .where(GenerationRunModel.id == run.id)
                    .with_for_update()
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
        .where(GenerationWorkItemModel.id == work_item_id, _active_leaf_clause())
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
    await _lock_run_for_item(session, run_id=item.run_id)
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
    item = await _require_live_lease(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        lease_token=lease_token,
        now=current_time,
    )
    result = await _execute_fenced_update(
        session,
        _live_item_update(
            item=item,
            worker_id=worker_id,
            lease_token=lease_token,
            now=current_time,
            values={"lease_expires_at": new_expiry, "updated_at": current_time},
        ),
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
            GenerationRunModel.status.in_({"queued", "running"}),
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


async def _refresh_run_lifecycle(
    session: AsyncSession,
    *,
    run: GenerationRunModel,
    now: datetime,
) -> None:
    """Aggregate item outcomes while holding the Run lock after the item lock."""
    locked_run = await session.scalar(
        select(GenerationRunModel)
        .where(GenerationRunModel.id == run.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_run is None:
        raise RunNotFound("generation run does not exist")
    run = locked_run
    await session.flush()
    statuses = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel.status).where(
                    GenerationWorkItemModel.run_id == run.id,
                    _active_leaf_clause(),
                )
            )
        ).all()
    )
    if "failed_terminal" in statuses:
        run.status = "failed_terminal"
    elif "running" in statuses:
        run.status = "running"
    elif "queued" in statuses:
        run.status = "queued"
    elif "failed_recoverable" in statuses:
        run.status = "failed_recoverable"
    elif run.status not in {"ready", "cancelled"}:
        # Whole-run validation and ready commit belong to the following phase.
        run.status = "running"

    latest_failure = await session.scalar(
        select(GenerationWorkItemModel)
        .where(
            GenerationWorkItemModel.run_id == run.id,
            GenerationWorkItemModel.status.in_({"failed_recoverable", "failed_terminal"}),
            GenerationWorkItemModel.error_code.is_not(None),
            _active_leaf_clause(),
        )
        .order_by(
            GenerationWorkItemModel.updated_at.desc(),
            GenerationWorkItemModel.id.desc(),
        )
        .limit(1)
    )
    if latest_failure is None:
        run.error_code = None
        run.error_class = None
        run.error_summary = None
        run.recovery_action = None
    else:
        run.error_code = latest_failure.error_code
        run.error_class = latest_failure.error_class
        run.error_summary = latest_failure.error_summary
        run.recovery_action = latest_failure.recovery_action
    run.updated_at = now
    await session.flush()


async def complete_work_item(
    session: AsyncSession,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    output_json: Any,
    output_hash: str,
    now: datetime | None = None,
) -> GenerationWorkItemModel:
    """Commit one canonical output under its live fence and append one event."""
    current_time = _utcnow(now)
    canonical_output, computed_hash = _canonical_json_value(output_json)
    if canonical_output is None:
        raise OutputValidationError("ready work-item output must not be SQL NULL")
    if output_hash != computed_hash:
        raise OutputHashMismatch("output_hash does not match canonical output JSON")

    item = await session.scalar(
        select(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == work_item_id, _active_leaf_clause())
        .with_for_update(skip_locked=True)
    )
    if item is None:
        if await session.get(GenerationWorkItemModel, work_item_id) is None:
            raise WorkItemNotFound("generation work item does not exist")
        raise LeaseLostError("work-item row is locked by another transaction")

    if item.status == "ready":
        if item.lease_owner != worker_id or item.lease_token != lease_token:
            raise LeaseLostError("worker no longer holds the completed item's fence")
        try:
            _stored_output, stored_hash = _canonical_json_value(item.output_json)
        except OutputValidationError as exc:
            raise OutputValidationError("persisted ready output is not canonical JSON") from exc
        if item.output_hash != stored_hash or stored_hash != computed_hash:
            raise OutputHashMismatch("completed output differs from the immutable ready output")
        return item

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

    async with session.begin_nested():
        result = await _execute_fenced_update(
            session,
            _live_item_update(
                item=item,
                worker_id=worker_id,
                lease_token=lease_token,
                now=current_time,
                values={
                    "status": "ready",
                    "output_json": canonical_output,
                    "output_hash": computed_hash,
                    "error_code": None,
                    "error_class": None,
                    "error_summary": None,
                    "recovery_action": None,
                    "completed_at": current_time,
                    "updated_at": current_time,
                },
            ),
        )
        if result.rowcount != 1:
            raise LeaseLostError("work-item lease or parent run changed before completion")
        await session.refresh(item)
        await session.refresh(run)
        await _refresh_run_lifecycle(session, run=run, now=current_time)
        await append_event(
            session,
            run_id=run.id,
            work_item_id=item.id,
            event_type="work_item_ready",
            safe_payload={"output_hash": computed_hash},
        )
    await session.refresh(item)
    return item


async def fail_work_item(
    session: AsyncSession,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    failure: WorkItemFailure,
    now: datetime | None = None,
) -> GenerationWorkItemModel:
    """Persist a typed, safe failure and choose recoverability within the attempt budget."""
    if not isinstance(failure, WorkItemFailure):
        failure = WorkItemFailure.model_validate(failure)
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

    can_retry = (
        failure.retryable
        and failure.recovery_action == RecoveryAction.RETRY.value
        and item.attempt < item.max_attempts
    )
    can_review = (
        failure.error_class in {ErrorClass.VALIDATION, ErrorClass.PROVIDER_OUTPUT}
        and failure.recovery_action == RecoveryAction.REVIEW.value
    )
    # Reviewable content failures remain recoverable so an application can
    # admit a changed, linked replacement.  retry_work_item deliberately
    # continues to reject REVIEW; only targeted replacement may proceed.
    next_status = "failed_recoverable" if can_retry or can_review else "failed_terminal"
    recovery_action = str(failure.recovery_action)
    if not can_retry and recovery_action == RecoveryAction.RETRY.value:
        recovery_action = RecoveryAction.REGENERATE.value

    async with session.begin_nested():
        result = await _execute_fenced_update(
            session,
            _live_item_update(
                item=item,
                worker_id=worker_id,
                lease_token=lease_token,
                now=current_time,
                values={
                    "status": next_status,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "output_json": None,
                    "output_hash": None,
                    "error_code": failure.error_code,
                    "error_class": str(failure.error_class),
                    "error_summary": failure.safe_summary,
                    "recovery_action": recovery_action,
                    "completed_at": current_time,
                    "updated_at": current_time,
                },
            ),
        )
        if result.rowcount != 1:
            raise LeaseLostError("work-item lease or parent run changed before failure commit")
        await session.refresh(item)
        await session.refresh(run)
        await _refresh_run_lifecycle(session, run=run, now=current_time)
        await append_event(
            session,
            run_id=run.id,
            work_item_id=item.id,
            event_type="work_item_failed",
            error_code=failure.error_code,
            safe_payload={
                "error_class": str(failure.error_class),
                "retryable": can_retry,
                "safe_summary": failure.safe_summary,
                "recovery_action": recovery_action,
            },
        )
    await session.refresh(item)
    return item


async def retry_work_item(
    session: AsyncSession,
    *,
    work_item_id: str,
    owner_user_id: str,
    now: datetime | None = None,
) -> GenerationWorkItemModel:
    """Queue one failed-recoverable item without changing healthy siblings/checkpoints."""
    run_id = await session.scalar(
        select(GenerationWorkItemModel.run_id)
        .join(GenerationRunModel, GenerationRunModel.id == GenerationWorkItemModel.run_id)
        .where(
            GenerationWorkItemModel.id == work_item_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
    )
    if run_id is None:
        raise WorkItemNotFound("generation work item does not exist")
    items = await retry_work_items(
        session,
        run_id=run_id,
        work_item_ids=(work_item_id,),
        owner_user_id=owner_user_id,
        now=now,
    )
    return items[0]


async def retry_work_items(
    session: AsyncSession,
    *,
    run_id: str,
    work_item_ids: Sequence[str],
    owner_user_id: str,
    now: datetime | None = None,
) -> tuple[GenerationWorkItemModel, ...]:
    """Atomically retry failed leaves and reopen their Run once.

    A failed-recoverable Run requires all active failed leaves in the same
    retry batch. Healthy siblings and checkpoints remain untouched.
    """
    current_time = _utcnow(now)
    requested_ids = tuple(work_item_ids)
    requested_set = set(requested_ids)
    if not requested_ids:
        raise InvalidWorkItemTransition("at least one work item is required for retry")
    if len(requested_set) != len(requested_ids):
        raise InvalidWorkItemTransition("work item retry IDs must be unique")

    visible_run_id = await session.scalar(
        select(GenerationRunModel.id).where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
    )
    if visible_run_id is None:
        raise RunNotFound("generation run is unavailable to this owner")

    items = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .join(GenerationRunModel, GenerationRunModel.id == GenerationWorkItemModel.run_id)
                .where(
                    GenerationWorkItemModel.id.in_(requested_set),
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationRunModel.owner_user_id == owner_user_id,
                    _active_leaf_clause(),
                )
                .order_by(GenerationWorkItemModel.id)
                .with_for_update(skip_locked=True, of=GenerationWorkItemModel)
            )
        ).all()
    )
    if len(items) != len(requested_ids):
        owned_rows = list(
            (
                await session.execute(
                    select(GenerationWorkItemModel.id, GenerationWorkItemModel.run_id)
                    .join(GenerationRunModel, GenerationRunModel.id == GenerationWorkItemModel.run_id)
                    .where(
                        GenerationWorkItemModel.id.in_(requested_set),
                        GenerationRunModel.owner_user_id == owner_user_id,
                    )
                )
            ).all()
        )
        owned_ids = {row.id for row in owned_rows}
        if owned_ids != requested_set:
            raise WorkItemNotFound("one or more generation work items do not exist")
        if any(row.run_id != run_id for row in owned_rows):
            raise InvalidWorkItemTransition(
                "all retried work items must belong to the specified Run"
            )
        raise WorkItemUnavailable("a work-item row is locked or is not an active leaf")

    run = await _lock_run_for_item(
        session,
        run_id=run_id,
        allow_failed_recoverable=True,
        allow_failed_terminal=True,
    )
    if run.owner_user_id != owner_user_id:
        raise RunNotFound("generation run is unavailable to this owner")
    if run.status not in {"queued", "running", "failed_recoverable"}:
        raise InvalidWorkItemTransition(
            "parent generation Run must be queued, running or failed_recoverable to retry"
        )

    if run.status == "failed_recoverable":
        failed_ids = set(
            (
                await session.scalars(
                    select(GenerationWorkItemModel.id).where(
                        GenerationWorkItemModel.run_id == run_id,
                        GenerationWorkItemModel.status.in_(
                            {"failed_recoverable", "failed_terminal"}
                        ),
                        _active_leaf_clause(),
                    )
                )
            ).all()
        )
        if failed_ids != requested_set:
            raise InvalidRunTransition(
                "all active failed work items must be retried together to reopen the Run"
            )

    for item in items:
        if item.status != "failed_recoverable":
            raise InvalidWorkItemTransition("only failed_recoverable work items can be retried")
        if item.error_class not in {"validation", "provider_transport", "provider_output"}:
            raise InvalidWorkItemTransition(
                "this failure class is not eligible for targeted retry"
            )
        if item.recovery_action != RecoveryAction.RETRY.value:
            raise InvalidWorkItemTransition(
                "work item recovery action does not allow targeted retry"
            )
        if item.attempt >= item.max_attempts:
            raise AttemptLimitExceeded("work item has no remaining retry attempts")

    await _serialize_run_build_on_sqlite(session, run_id=run_id)
    async with session.begin_nested():
        for item in items:
            prior_attempt = item.attempt
            prior_token = item.lease_token or 0
            result = await _execute_fenced_update(
                session,
                update(GenerationWorkItemModel)
                .where(
                    GenerationWorkItemModel.id == item.id,
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.status == "failed_recoverable",
                    GenerationWorkItemModel.attempt == prior_attempt,
                    GenerationWorkItemModel.attempt < GenerationWorkItemModel.max_attempts,
                    GenerationWorkItemModel.error_class.in_(
                        {"validation", "provider_transport", "provider_output"}
                    ),
                    GenerationWorkItemModel.recovery_action == RecoveryAction.RETRY.value,
                    _active_leaf_clause(),
                )
                .values(
                    status="queued",
                    attempt=prior_attempt + 1,
                    lease_owner=None,
                    lease_token=prior_token + 1,
                    lease_expires_at=None,
                    error_code=None,
                    error_class=None,
                    error_summary=None,
                    recovery_action=None,
                    output_json=None,
                    output_hash=None,
                    completed_at=None,
                    updated_at=current_time,
                )
                .execution_options(synchronize_session=False),
            )
            if result.rowcount != 1:
                raise InvalidWorkItemTransition("work item or parent Run changed before retry")
        await session.flush()
        for item in items:
            await session.refresh(item)
            await append_event(
                session,
                run_id=run_id,
                work_item_id=item.id,
                event_type="work_item_retry_queued",
                safe_payload={
                    "from_attempt": item.attempt - 1,
                    "attempt": item.attempt,
                    "recovery_action": RecoveryAction.RETRY.value,
                },
            )
        await _refresh_run_lifecycle(session, run=run, now=current_time)
    for item in items:
        await session.refresh(item)
    return tuple(items)


async def requeue_failed_terminal_work_item(
    session: AsyncSession,
    *,
    work_item_id: str,
    owner_user_id: str,
    expected_error_code: str,
    now: datetime | None = None,
) -> GenerationWorkItemModel:
    """Requeue one active ``failed_terminal`` leaf whose failure was a resolvable false positive.

    Generic, application-gated recovery primitive: the caller proves (outside
    this layer) that the failure carrying ``expected_error_code`` should not
    have been terminal.  The leaf returns to ``queued`` under a bumped fence
    WITHOUT consuming an attempt; its checkpoint is retained, error and output
    fields are cleared, and the parent Run is refreshed (``failed_terminal``
    -> ``queued`` when no other terminal leaf remains).  Only an active leaf
    whose persisted ``error_code`` equals ``expected_error_code`` qualifies.
    """
    current_time = _utcnow(now)
    run_id = await session.scalar(
        select(GenerationWorkItemModel.run_id)
        .join(GenerationRunModel, GenerationRunModel.id == GenerationWorkItemModel.run_id)
        .where(
            GenerationWorkItemModel.id == work_item_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
    )
    if run_id is None:
        raise WorkItemNotFound("generation work item does not exist")
    await _serialize_run_build_on_sqlite(session, run_id=run_id)
    item = await session.scalar(
        select(GenerationWorkItemModel)
        .where(
            GenerationWorkItemModel.id == work_item_id,
            GenerationWorkItemModel.run_id == run_id,
            _active_leaf_clause(),
        )
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise WorkItemUnavailable("work item is locked or is not an active leaf")
    run = await _lock_run_for_item(
        session,
        run_id=run_id,
        allow_failed_terminal=True,
        allow_failed_recoverable=True,
    )
    if run.owner_user_id != owner_user_id:
        raise RunNotFound("generation run is unavailable to this owner")
    if item.status != "failed_terminal" or item.error_code != expected_error_code:
        raise InvalidWorkItemTransition(
            "only a failed_terminal work item with the expected error code can be requeued"
        )
    prior_attempt = item.attempt
    prior_token = item.lease_token or 0
    async with session.begin_nested():
        result = await _execute_fenced_update(
            session,
            update(GenerationWorkItemModel)
            .where(
                GenerationWorkItemModel.id == item.id,
                GenerationWorkItemModel.run_id == run_id,
                GenerationWorkItemModel.status == "failed_terminal",
                GenerationWorkItemModel.error_code == expected_error_code,
                GenerationWorkItemModel.attempt == prior_attempt,
                _active_leaf_clause(),
            )
            .values(
                status="queued",
                lease_owner=None,
                lease_token=prior_token + 1,
                lease_expires_at=None,
                error_code=None,
                error_class=None,
                error_summary=None,
                recovery_action=None,
                output_json=None,
                output_hash=None,
                completed_at=None,
                updated_at=current_time,
            )
            .execution_options(synchronize_session=False),
        )
        if result.rowcount != 1:
            raise InvalidWorkItemTransition("work item changed before it could be requeued")
        if run.status == "failed_terminal":
            await session.execute(
                update(GenerationRunModel)
                .where(
                    GenerationRunModel.id == run_id,
                    GenerationRunModel.status == "failed_terminal",
                )
                .values(completed_at=None, updated_at=current_time)
                .execution_options(synchronize_session=False)
            )
        await session.flush()
        await session.refresh(item)
        await session.refresh(run)
        await _refresh_run_lifecycle(session, run=run, now=current_time)
        await append_event(
            session,
            run_id=run_id,
            work_item_id=item.id,
            event_type="work_item_resolution_queued",
            safe_payload={
                "previous_error_code": expected_error_code,
                "attempt": item.attempt,
            },
        )
    await session.refresh(item)
    return item


async def reconcile_expired_work_item(
    session: AsyncSession,
    *,
    work_item_id: str,
    now: datetime | None = None,
) -> GenerationWorkItemModel:
    """Close an expired running item whose bounded attempt budget is exhausted."""
    current_time = _utcnow(now)
    item = await session.scalar(
        select(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == work_item_id, _active_leaf_clause())
        .with_for_update(skip_locked=True)
    )
    if item is None:
        if await session.get(GenerationWorkItemModel, work_item_id) is None:
            raise WorkItemNotFound("generation work item does not exist")
        raise WorkItemUnavailable("work-item row is locked by another transaction")

    if (
        item.status == "failed_terminal"
        and item.error_class == "budget_exhausted"
        and item.error_code == "budget_exhausted"
    ):
        return item
    if (
        item.status != "running"
        or item.lease_expires_at is None
        or _utcnow(item.lease_expires_at) > current_time
    ):
        raise InvalidWorkItemTransition("only expired running work items can be reconciled")
    if item.attempt < item.max_attempts:
        raise InvalidWorkItemTransition("work item still has a claim attempt available")

    run = await _lock_run_for_item(
        session,
        run_id=item.run_id,
        allow_failed_terminal=True,
    )
    async with session.begin_nested():
        run_may_reconcile = (
            select(GenerationRunModel.id)
            .where(
                GenerationRunModel.id == run.id,
                GenerationRunModel.status.in_({"queued", "running", "failed_terminal"}),
            )
            .exists()
        )
        result = await _execute_fenced_update(
            session,
            update(GenerationWorkItemModel)
            .where(
                GenerationWorkItemModel.id == item.id,
                GenerationWorkItemModel.run_id == item.run_id,
                GenerationWorkItemModel.status == "running",
                GenerationWorkItemModel.attempt == item.attempt,
                GenerationWorkItemModel.attempt >= GenerationWorkItemModel.max_attempts,
                GenerationWorkItemModel.lease_expires_at.is_not(None),
                GenerationWorkItemModel.lease_expires_at <= current_time,
                (
                    GenerationWorkItemModel.lease_token.is_(None)
                    if item.lease_token is None
                    else GenerationWorkItemModel.lease_token == item.lease_token
                ),
                (
                    GenerationWorkItemModel.lease_owner.is_(None)
                    if item.lease_owner is None
                    else GenerationWorkItemModel.lease_owner == item.lease_owner
                ),
                _active_leaf_clause(),
                run_may_reconcile,
            )
            .values(
                status="failed_terminal",
                lease_owner=None,
                lease_expires_at=None,
                error_code="budget_exhausted",
                error_class="budget_exhausted",
                error_summary="Work item lease expired after all attempts were used.",
                recovery_action=RecoveryAction.REGENERATE.value,
                output_json=None,
                output_hash=None,
                completed_at=current_time,
                updated_at=current_time,
            )
            .execution_options(synchronize_session=False),
        )
        if result.rowcount != 1:
            raise WorkItemUnavailable("work item changed before exhausted-attempt reconciliation")
        await session.refresh(item)
        await session.refresh(run)
        await _refresh_run_lifecycle(session, run=run, now=current_time)
        await append_event(
            session,
            run_id=run.id,
            work_item_id=item.id,
            event_type="work_item_attempts_exhausted",
            error_code="budget_exhausted",
            safe_payload={
                "error_class": "budget_exhausted",
                "retryable": False,
                "safe_summary": item.error_summary,
                "recovery_action": item.recovery_action,
            },
        )
    await session.refresh(item)
    return item


def _assert_finalization_identity(
    run: GenerationRunModel,
    *,
    request: RunFinalization,
    computed_hash: str,
) -> None:
    _assert_source_identity(run, request.source)
    if (
        run.output_artifact_type != request.output_artifact_type
        or run.output_artifact_id != request.output_artifact_id
        or run.output_revision != request.output_revision
        or run.output_hash != computed_hash
    ):
        raise InvalidRunTransition(
            "final artifact identity or hash differs from persisted ready output"
        )


SourceVerifier = Callable[
    [AsyncSession, SourceIdentity], Awaitable[SourceIdentity | dict[str, Any]]
]
ArtifactLoader = Callable[
    [AsyncSession, str, str, int], Awaitable[VerifiedArtifact | dict[str, Any]]
]


async def _verify_finalization_inputs(
    session: AsyncSession,
    *,
    request: RunFinalization,
    source_verifier: SourceVerifier,
    artifact_loader: ArtifactLoader,
    verify_current_source: bool = True,
) -> str:
    if verify_current_source:
        try:
            verified_source = await source_verifier(session, request.source)
            if not isinstance(verified_source, SourceIdentity):
                verified_source = SourceIdentity.model_validate(verified_source)
        except Exception as exc:
            raise SourceVerificationError("trusted source verification failed") from exc
        if verified_source != request.source:
            raise SourceIdentityConflict(
                "current persisted source differs from admitted source identity"
            )

    try:
        artifact = await artifact_loader(
            session,
            request.output_artifact_type,
            request.output_artifact_id,
            request.output_revision,
        )
        if not isinstance(artifact, VerifiedArtifact):
            artifact = VerifiedArtifact.model_validate(artifact)
        if (
            artifact.artifact_type != request.output_artifact_type
            or artifact.artifact_id != request.output_artifact_id
            or artifact.revision != request.output_revision
        ):
            raise ArtifactVerificationError(
                "loaded artifact identity differs from requested identity"
            )
        _canonical, output_hash = _canonical_json_value(artifact.output_json)
        if artifact.output_hash != output_hash:
            raise ArtifactVerificationError("loaded artifact hash differs from canonical content")
    except ArtifactVerificationError:
        raise
    except Exception as exc:
        raise ArtifactVerificationError(
            "trusted artifact could not be loaded as strict JSON"
        ) from exc
    return output_hash


async def _finalize_run_in_transaction(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    finalization: RunFinalization,
    source_verifier: SourceVerifier,
    artifact_loader: ArtifactLoader,
    now: datetime | None = None,
) -> GenerationRunModel:
    """Commit ready only after trusted source and persisted-artifact verification."""
    if not isinstance(finalization, RunFinalization):
        finalization = RunFinalization.model_validate(finalization)
    current_time = _utcnow(now)

    visible = await session.scalar(
        select(GenerationRunModel).where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
    )
    if visible is None:
        raise RunNotFound("generation run is unavailable to this owner")

    # SQLite ignores FOR UPDATE, so serialize admission/terminal operations before
    # scanning children; PostgreSQL preserves the item-then-Run lock order below.
    await _serialize_run_build_on_sqlite(session, run_id=run_id)

    # Child rows are locked in a stable order before the parent Run, matching worker paths.
    all_items = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
                .with_for_update()
            )
        ).all()
    )
    items = active_work_items(all_items)
    if not items:
        raise InvalidRunTransition("a run with no declared work items cannot be finalized")
    if any(item.status != "ready" for item in items):
        raise InvalidRunTransition("all declared work items must be ready before run finalization")
    for item in items:
        _canonical_output, item_hash = _canonical_json_value(item.output_json)
        if item_hash != item.output_hash:
            raise OutputHashMismatch("a persisted work-item output failed hash validation")

    run = await session.scalar(
        select(GenerationRunModel)
        .where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise RunNotFound("generation run is unavailable to this owner")
    if run.status == "ready":
        computed_hash = await _verify_finalization_inputs(
            session,
            request=finalization,
            source_verifier=source_verifier,
            artifact_loader=artifact_loader,
            verify_current_source=False,
        )
        _assert_finalization_identity(run, request=finalization, computed_hash=computed_hash)
        return run
    if run.status not in {"queued", "running"}:
        raise InvalidRunTransition("only an active run can be finalized")
    _assert_source_identity(run, finalization.source)
    current_all_items = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
            )
        ).all()
    )
    if [item.id for item in current_all_items] != [item.id for item in all_items]:
        raise InvalidRunTransition(
            "work-item set changed during finalization; retry after admission settles"
        )
    current_items = active_work_items(current_all_items)
    if any(item.status != "ready" for item in current_items):
        raise InvalidRunTransition("all declared work items must be ready before run finalization")
    computed_hash = await _verify_finalization_inputs(
        session,
        request=finalization,
        source_verifier=source_verifier,
        artifact_loader=artifact_loader,
    )

    async with session.begin_nested():
        result = await session.execute(
            update(GenerationRunModel)
            .where(
                GenerationRunModel.id == run_id,
                GenerationRunModel.owner_user_id == owner_user_id,
                GenerationRunModel.status.in_({"queued", "running"}),
                GenerationRunModel.source_artifact_type == finalization.source.source_artifact_type,
                GenerationRunModel.source_artifact_id == finalization.source.source_artifact_id,
                GenerationRunModel.source_revision == finalization.source.source_revision,
                GenerationRunModel.source_hash == finalization.source.source_hash,
            )
            .values(
                status="ready",
                output_artifact_type=finalization.output_artifact_type,
                output_artifact_id=finalization.output_artifact_id,
                output_revision=finalization.output_revision,
                output_hash=computed_hash,
                error_code=None,
                error_class=None,
                error_summary=None,
                recovery_action=None,
                completed_at=current_time,
                updated_at=current_time,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise InvalidRunTransition("run status or source identity changed before ready commit")
        await session.refresh(run)
        await append_event(
            session,
            run_id=run_id,
            event_type="run_ready",
            safe_payload={
                "output_artifact_type": finalization.output_artifact_type,
                "output_artifact_id": finalization.output_artifact_id,
                "output_revision": finalization.output_revision,
                "output_hash": computed_hash,
            },
        )
    await session.refresh(run)
    return run


async def finalize_run(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    finalization: RunFinalization,
    source_verifier: SourceVerifier,
    artifact_loader: ArtifactLoader,
    now: datetime | None = None,
) -> GenerationRunModel:
    """Finalize within one savepoint, rolling back on any verifier/commit failure."""
    async with session.begin_nested():
        return await _finalize_run_in_transaction(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            finalization=finalization,
            source_verifier=source_verifier,
            artifact_loader=artifact_loader,
            now=now,
        )


async def cancel_run(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    now: datetime | None = None,
) -> GenerationRunModel:
    """Cancel an active/recoverable Run and fence every remaining non-ready item."""
    current_time = _utcnow(now)
    visible = await session.scalar(
        select(GenerationRunModel).where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
    )
    if visible is None:
        raise RunNotFound("generation run is unavailable to this owner")
    if visible.status == "cancelled":
        return visible
    if visible.status not in {"queued", "running", "failed_recoverable"}:
        raise InvalidRunTransition("only an active or failed-recoverable run can be cancelled")

    await _serialize_run_build_on_sqlite(session, run_id=run_id)

    all_items = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
                .with_for_update()
            )
        ).all()
    )
    items = active_work_items(all_items)
    run = await session.scalar(
        select(GenerationRunModel)
        .where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise RunNotFound("generation run is unavailable to this owner")
    if run.status == "cancelled":
        return run
    if run.status not in {"queued", "running", "failed_recoverable"}:
        raise InvalidRunTransition("run became terminal before cancellation")
    current_all_item_ids = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel.id)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
            )
        ).all()
    )
    if current_all_item_ids != [item.id for item in all_items]:
        raise InvalidRunTransition(
            "work-item set changed during cancellation; retry after admission settles"
        )

    async with session.begin_nested():
        for item in items:
            if item.status == "ready" or item.status == "cancelled":
                continue
            result = await session.execute(
                update(GenerationWorkItemModel)
                .where(
                    GenerationWorkItemModel.id == item.id,
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.status == item.status,
                    GenerationWorkItemModel.attempt == item.attempt,
                )
                .values(
                    status="cancelled",
                    lease_owner=None,
                    lease_token=(item.lease_token or 0) + 1,
                    lease_expires_at=None,
                    output_json=None,
                    output_hash=None,
                    error_code="cancelled",
                    error_class=ErrorClass.CANCELLED.value,
                    error_summary="Generation work item was cancelled.",
                    recovery_action=RecoveryAction.NONE.value,
                    completed_at=current_time,
                    updated_at=current_time,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise InvalidRunTransition("a work item changed before cancellation committed")
            await session.refresh(item)
            await append_event(
                session,
                run_id=run_id,
                work_item_id=item.id,
                event_type="work_item_cancelled",
                error_code="cancelled",
                safe_payload={"error_class": ErrorClass.CANCELLED.value},
            )

        result = await session.execute(
            update(GenerationRunModel)
            .where(
                GenerationRunModel.id == run_id,
                GenerationRunModel.owner_user_id == owner_user_id,
                GenerationRunModel.status.in_({"queued", "running", "failed_recoverable"}),
            )
            .values(
                status="cancelled",
                error_code="cancelled",
                error_class=ErrorClass.CANCELLED.value,
                error_summary="Generation run was cancelled.",
                recovery_action=RecoveryAction.NONE.value,
                completed_at=current_time,
                updated_at=current_time,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise InvalidRunTransition("run became terminal before cancellation committed")
        await session.refresh(run)
        await append_event(
            session,
            run_id=run_id,
            event_type="run_cancelled",
            error_code="cancelled",
            safe_payload={"error_class": ErrorClass.CANCELLED.value},
        )
    await session.refresh(run)
    return run


async def fail_run_terminal(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    failure: RunFailure,
    now: datetime | None = None,
) -> GenerationRunModel:
    """Fail an active Run when a dependency transition cannot admit a WorkItem."""
    if not isinstance(failure, RunFailure):
        failure = RunFailure.model_validate(failure)
    current_time = _utcnow(now)
    visible = await session.scalar(
        select(GenerationRunModel).where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
    )
    if visible is None:
        raise RunNotFound("generation run is unavailable to this owner")
    if visible.status not in {"queued", "running"}:
        raise InvalidRunTransition("only an active run can fail terminally")

    await _serialize_run_build_on_sqlite(session, run_id=run_id)
    all_items = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
                .with_for_update()
            )
        ).all()
    )
    items = active_work_items(all_items)
    run = await session.scalar(
        select(GenerationRunModel)
        .where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise RunNotFound("generation run is unavailable to this owner")
    if run.status not in {"queued", "running"}:
        raise InvalidRunTransition("run became terminal before failure")
    current_item_ids = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel.id)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
            )
        ).all()
    )
    if current_item_ids != [item.id for item in all_items]:
        raise InvalidRunTransition(
            "work-item set changed during terminal failure; retry after admission settles"
        )
    if any(item.status in {"queued", "running"} for item in items):
        raise InvalidRunTransition("a run with active work items cannot fail terminally")

    async with session.begin_nested():
        result = await session.execute(
            update(GenerationRunModel)
            .where(
                GenerationRunModel.id == run_id,
                GenerationRunModel.owner_user_id == owner_user_id,
                GenerationRunModel.status.in_({"queued", "running"}),
            )
            .values(
                status="failed_terminal",
                error_code=failure.error_code,
                error_class=str(failure.error_class),
                error_summary=failure.safe_summary,
                recovery_action=RecoveryAction.NONE.value,
                completed_at=current_time,
                updated_at=current_time,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise InvalidRunTransition("run changed before terminal failure committed")
        await session.refresh(run)
        await append_event(
            session,
            run_id=run_id,
            event_type="run_failed",
            error_code=failure.error_code,
            safe_payload={
                "error_class": str(failure.error_class),
                "safe_summary": failure.safe_summary,
                "recovery_action": RecoveryAction.NONE.value,
            },
        )
    await session.refresh(run)
    return run


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
        item.replaces_work_item_id is None
        and item.stage == request.stage
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
    run = await session.scalar(
        select(GenerationRunModel)
        .where(GenerationRunModel.id == request.run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise RunNotFound("generation run does not exist")
    await _serialize_run_build_on_sqlite(session, run_id=request.run_id)
    if session.get_bind().dialect.name == "sqlite":
        run = await session.scalar(
            select(GenerationRunModel)
            .where(GenerationRunModel.id == request.run_id)
            .execution_options(populate_existing=True)
        )
        if run is None:
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
    if run.status not in {"queued", "running"}:
        raise InvalidRunTransition("new work items cannot be admitted after run termination")

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


def _replacement_identity_matches(
    item: GenerationWorkItemModel,
    request: WorkItemAdmission,
    predecessor_id: str,
) -> bool:
    return (
        item.run_id == request.run_id
        and item.replaces_work_item_id == predecessor_id
        and item.item_key == request.item_key
        and item.stage == request.stage
        and item.input_hash == request.input_hash
        and item.definition_hash == request.definition_hash
        and item.composition_identity == request.composition_identity
        and item.max_attempts == request.max_attempts
    )


async def replace_work_item(
    session: AsyncSession,
    request: WorkItemReplacement,
    *,
    now: datetime | None = None,
) -> GenerationWorkItemModel:
    """Admit one linked successor after an application-validated targeted repair.

    This is an internal application-service operation, not a generic user-facing
    admission route. The caller must validate the repair against its durable QA
    issue; this layer enforces owner/source identity, lineage, lock order and
    idempotency.
    """
    if not isinstance(request, WorkItemReplacement):
        request = WorkItemReplacement.model_validate(request)
    predecessor_id = request.predecessor_work_item_id
    replacement = request.replacement
    preliminary_run_id = await session.scalar(
        select(GenerationWorkItemModel.run_id).where(GenerationWorkItemModel.id == predecessor_id)
    )
    if preliminary_run_id is None:
        raise WorkItemNotFound("replacement predecessor does not exist")
    if replacement.run_id != preliminary_run_id:
        raise WorkItemConflict("replacement must remain in the predecessor's Run")

    # SQLite serializes through the stable Build row. PostgreSQL locks item then
    # Run, matching claim/finalization and the database insertion trigger.
    await _serialize_run_build_on_sqlite(session, run_id=preliminary_run_id)
    predecessor = await session.scalar(
        select(GenerationWorkItemModel)
        .where(
            GenerationWorkItemModel.id == predecessor_id,
            GenerationWorkItemModel.run_id == preliminary_run_id,
        )
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    if predecessor is None:
        if await session.get(GenerationWorkItemModel, predecessor_id) is None:
            raise WorkItemNotFound("replacement predecessor does not exist")
        raise WorkItemUnavailable("replacement predecessor is locked by another transaction")

    run = await session.scalar(
        select(GenerationRunModel)
        .where(GenerationRunModel.id == preliminary_run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise RunNotFound("generation run does not exist")
    if run.owner_user_id != request.owner_user_id:
        raise RunNotFound("replacement predecessor is unavailable to this owner")
    source = request.source
    if not isinstance(source, SourceIdentity):
        source = SourceIdentity.model_validate(source)
    _assert_source_identity(run, source)

    child = await session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.run_id == run.id,
            GenerationWorkItemModel.replaces_work_item_id == predecessor_id,
        )
    )
    if child is not None:
        if _replacement_identity_matches(child, replacement, predecessor_id):
            return child
        raise WorkItemConflict("predecessor already has a different replacement")

    if run.status not in {"queued", "running", "failed_recoverable"}:
        raise InvalidRunTransition("only an active or recoverable Run can admit a replacement")
    if predecessor.status not in {"ready", "failed_recoverable"}:
        raise InvalidWorkItemTransition(
            "only a ready or failed_recoverable work item can be replaced"
        )
    if predecessor.stage != replacement.stage:
        raise WorkItemConflict("replacement stage must match the predecessor stage")
    if predecessor.item_key == replacement.item_key:
        raise WorkItemConflict("replacement must use a new stable item key")
    if (
        predecessor.input_hash == replacement.input_hash
        and predecessor.definition_hash == replacement.definition_hash
        and predecessor.composition_identity == replacement.composition_identity
    ):
        raise WorkItemConflict("replacement must bind a changed work identity")
    if predecessor.status == "failed_recoverable" and (
        predecessor.error_class not in {"validation", "provider_output"}
        or predecessor.recovery_action
        not in {RecoveryAction.RETRY.value, RecoveryAction.REVIEW.value}
    ):
        raise InvalidWorkItemTransition(
            "this failure is not eligible for targeted repaired-work replacement"
        )

    same_key = await session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.run_id == run.id,
            GenerationWorkItemModel.item_key == replacement.item_key,
        )
    )
    if same_key is not None:
        if _replacement_identity_matches(same_key, replacement, predecessor_id):
            return same_key
        raise WorkItemConflict("replacement key is already bound to different work")

    if session.get_bind().dialect.name == "sqlite":
        run = await session.scalar(
            select(GenerationRunModel)
            .where(GenerationRunModel.id == run.id)
            .execution_options(populate_existing=True)
        )
        if run is None:
            raise RunNotFound("generation run does not exist")
    _assert_source_identity(run, source)
    if run.status not in {"queued", "running", "failed_recoverable"}:
        raise InvalidRunTransition("Run became terminal before replacement admission")

    current_time = _utcnow(now)
    item = GenerationWorkItemModel(
        id=str(uuid.uuid4()),
        run_id=run.id,
        replaces_work_item_id=predecessor.id,
        item_key=replacement.item_key,
        stage=replacement.stage,
        status="queued",
        attempt=1,
        max_attempts=replacement.max_attempts,
        input_hash=replacement.input_hash,
        definition_hash=replacement.definition_hash,
        composition_identity=replacement.composition_identity,
        created_at=current_time,
        updated_at=current_time,
    )
    try:
        async with session.begin_nested():
            session.add(item)
            await session.flush()
            if run.status == "failed_recoverable":
                result = await session.execute(
                    update(GenerationRunModel)
                    .where(
                        GenerationRunModel.id == run.id,
                        GenerationRunModel.owner_user_id == request.owner_user_id,
                        GenerationRunModel.status == "failed_recoverable",
                        GenerationRunModel.source_artifact_type == source.source_artifact_type,
                        GenerationRunModel.source_artifact_id == source.source_artifact_id,
                        GenerationRunModel.source_revision == source.source_revision,
                        GenerationRunModel.source_hash == source.source_hash,
                    )
                    .values(
                        status="queued",
                        error_code=None,
                        error_class=None,
                        error_summary=None,
                        recovery_action=None,
                        completed_at=None,
                        updated_at=current_time,
                    )
                    .execution_options(synchronize_session=False)
                )
                if result.rowcount != 1:
                    raise InvalidRunTransition("Run changed before replacement admission")
            await session.refresh(run)
            await _refresh_run_lifecycle(session, run=run, now=current_time)
            await append_event(
                session,
                run_id=run.id,
                work_item_id=item.id,
                event_type="work_item_replacement_queued",
                safe_payload={
                    "replaces_work_item_id": predecessor.id,
                    "replaces_item_key": predecessor.item_key,
                    "input_hash": item.input_hash,
                    "definition_hash": item.definition_hash,
                    "composition_identity": item.composition_identity,
                },
            )
    except IntegrityError as exc:
        existing = await session.scalar(
            select(GenerationWorkItemModel).where(
                GenerationWorkItemModel.run_id == run.id,
                GenerationWorkItemModel.replaces_work_item_id == predecessor_id,
            )
        )
        if existing is not None and _replacement_identity_matches(
            existing, replacement, predecessor_id
        ):
            return existing
        raise WorkItemConflict("replacement was concurrently admitted or violates lineage") from exc
    await session.refresh(item)
    return item


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
        select(GenerationRunModel)
        .where(GenerationRunModel.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
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
