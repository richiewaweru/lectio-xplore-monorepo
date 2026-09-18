"""Learn run fencing — reuse Print lease tokens (P03 G13).

Expired / superseded workers cannot commit. Cancellation blocks new dispatch
and late publication. Lease shape matches ``ExecutionLease`` from Print states.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel, NativeRealizationModel
from infra.execution.leases import (
    DEFAULT_LEASE_SECONDS,
    ExecutionLease,
    LeaseLostError,
)

LEARN_EXECUTION_KEY = "learn_execution"
# Learn authoring can involve several sequential provider calls. Keep the
# ownership window comfortably above the heartbeat interval so a brief DB or
# provider stall does not invalidate an otherwise recoverable run.
LEARN_LEASE_SECONDS = 600


class LearnCancelledError(RuntimeError):
    """Learn run was cancelled; new dispatch and late commit are forbidden."""


class LearnFenceError(LeaseLostError):
    """Learn commit rejected due to lease / cancel fence."""


def _now() -> str:
    # Keep full precision (match Print repository._now). Truncating microseconds
    # silently steals up to ~1s from short leases and flakes heartbeat tests.
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def empty_learn_execution_meta() -> dict[str, Any]:
    return {
        "worker_id": None,
        "lease_token": 0,
        "lease_seconds": LEARN_LEASE_SECONDS,
        "heartbeat_at": None,
        "claimed_at": None,
        "cancelled": False,
        "status": "queued",
        "call_budgets": {},
        "checkpoints": {},
    }


def learn_execution_from_generation(generation: GenerationModel) -> dict[str, Any]:
    chunked = generation.chunked_state_json
    if not isinstance(chunked, dict):
        return empty_learn_execution_meta()
    raw = chunked.get(LEARN_EXECUTION_KEY)
    if not isinstance(raw, dict):
        return empty_learn_execution_meta()
    base = empty_learn_execution_meta()
    base.update(raw)
    return base


def write_learn_execution(generation: GenerationModel, execution: dict[str, Any]) -> None:
    chunked = dict(generation.chunked_state_json or {})
    chunked[LEARN_EXECUTION_KEY] = deepcopy(execution)
    generation.chunked_state_json = chunked


def assert_learn_dispatch_allowed(execution: dict[str, Any]) -> None:
    if bool(execution.get("cancelled")):
        raise LearnCancelledError("Learn run cancelled; dispatch blocked")
    status = str(execution.get("status") or "")
    if status == "cancelled":
        raise LearnCancelledError("Learn run cancelled; dispatch blocked")


def assert_learn_commit_allowed(
    execution: dict[str, Any],
    *,
    worker_id: str,
    lease_token: int,
    now: datetime | None = None,
) -> None:
    assert_learn_dispatch_allowed(execution)
    current = now or datetime.now(UTC)
    if execution.get("worker_id") != worker_id:
        raise LearnFenceError("commit rejected: worker does not own Learn lease")
    if int(execution.get("lease_token") or 0) != int(lease_token):
        raise LearnFenceError("commit rejected: lease token mismatch")
    heartbeat = _parse_iso(execution.get("heartbeat_at"))
    lease_seconds = int(execution.get("lease_seconds") or DEFAULT_LEASE_SECONDS)
    if heartbeat is None or heartbeat + timedelta(seconds=lease_seconds) < current:
        raise LearnFenceError("commit rejected: Learn lease expired")


async def claim_learn_execution(
    session: AsyncSession,
    *,
    generation_id: str,
    worker_id: str,
    lease_seconds: int = LEARN_LEASE_SECONDS,
) -> ExecutionLease | None:
    result = await session.execute(
        select(GenerationModel)
        .where(GenerationModel.id == generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    generation = result.scalar_one_or_none()
    if generation is None:
        return None

    execution = learn_execution_from_generation(generation)
    if bool(execution.get("cancelled")) or execution.get("status") == "cancelled":
        return None

    now = datetime.now(UTC)
    heartbeat = _parse_iso(execution.get("heartbeat_at"))
    lease = int(execution.get("lease_seconds") or lease_seconds)
    stale = heartbeat is None or heartbeat + timedelta(seconds=lease) < now
    owner = execution.get("worker_id")
    status = str(execution.get("status") or "queued")

    if status in {"ready", "cancelled"}:
        return None
    if owner is not None and not stale:
        return None

    new_token = int(execution.get("lease_token") or 0) + 1
    execution["worker_id"] = worker_id
    execution["lease_token"] = new_token
    execution["lease_seconds"] = lease_seconds
    execution["claimed_at"] = _now()
    execution["heartbeat_at"] = _now()
    execution["status"] = "running" if status in {"queued", "running", "failed"} else status
    write_learn_execution(generation, execution)
    if generation.status not in {"completed", "cancelled"}:
        generation.status = "running"
    await session.flush()
    return ExecutionLease(
        generation_id=generation_id,
        worker_id=worker_id,
        lease_token=new_token,
        stage=str(execution["status"]),
    )


async def cancel_learn_execution(
    session: AsyncSession,
    *,
    generation_id: str,
) -> dict[str, Any]:
    result = await session.execute(
        select(GenerationModel)
        .where(GenerationModel.id == generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    generation = result.scalar_one_or_none()
    if generation is None:
        raise KeyError(f"generation {generation_id!r} not found")
    execution = learn_execution_from_generation(generation)
    execution["cancelled"] = True
    execution["status"] = "cancelled"
    execution["worker_id"] = None
    write_learn_execution(generation, execution)
    generation.status = "cancelled"
    await session.flush()

    # Mirror cancel onto realization row when present.
    realization = await session.scalar(
        select(NativeRealizationModel).where(NativeRealizationModel.output_id == generation_id)
    )
    if realization is not None and realization.status not in {"ready", "cancelled"}:
        realization.status = "cancelled"
        await session.flush()
    return execution


async def fail_stale_learn_executions(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """Reconcile Learn workers that lost their process after a restart.

    Learn production runs synchronously inside the request that admitted them,
    so a server restart can leave both the generation and realization rows in
    ``running`` forever.  Expired leases are retryable and must be surfaced as
    such instead of making the lesson status endpoint fail validation.
    """
    current = now or datetime.now(UTC)
    result = await session.execute(
        select(GenerationModel).where(GenerationModel.status == "running")
    )
    repaired = 0
    for generation in result.scalars().all():
        state = generation.chunked_state_json if isinstance(generation.chunked_state_json, dict) else {}
        execution = state.get(LEARN_EXECUTION_KEY)
        if not isinstance(execution, dict) or execution.get("status") != "running":
            continue
        heartbeat = _parse_iso(execution.get("heartbeat_at"))
        lease_seconds = int(execution.get("lease_seconds") or DEFAULT_LEASE_SECONDS)
        if heartbeat is not None and heartbeat + timedelta(seconds=lease_seconds) >= current:
            continue
        execution = dict(execution)
        execution.update({"status": "failed", "worker_id": None, "heartbeat_at": None})
        generation.chunked_state_json = {**state, LEARN_EXECUTION_KEY: execution}
        generation.status = "failed"
        realization = await session.scalar(
            select(NativeRealizationModel).where(
                NativeRealizationModel.output_id == generation.id,
                NativeRealizationModel.path == "learn",
            )
        )
        if realization is not None and realization.status == "running":
            realization.status = "failed_recoverable"
            realization.error_summary = "Learn execution interrupted; retry is available"
        repaired += 1
    if repaired:
        await session.commit()
    return repaired


async def require_learn_lease(
    session: AsyncSession,
    *,
    generation_id: str,
    worker_id: str,
    lease_token: int,
) -> dict[str, Any]:
    result = await session.execute(
        select(GenerationModel)
        .where(GenerationModel.id == generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    generation = result.scalar_one_or_none()
    if generation is None:
        raise KeyError(f"generation {generation_id!r} not found")
    execution = learn_execution_from_generation(generation)
    assert_learn_commit_allowed(
        execution, worker_id=worker_id, lease_token=lease_token
    )
    return execution


async def commit_learn_checkpoint(
    session: AsyncSession,
    *,
    generation_id: str,
    worker_id: str,
    lease_token: int,
    checkpoint_key: str,
    checkpoint_payload: dict[str, Any],
) -> dict[str, Any]:
    """Fenced checkpoint write — expired workers cannot commit."""
    result = await session.execute(
        select(GenerationModel)
        .where(GenerationModel.id == generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    generation = result.scalar_one_or_none()
    if generation is None:
        raise KeyError(f"generation {generation_id!r} not found")
    execution = learn_execution_from_generation(generation)
    assert_learn_commit_allowed(
        execution, worker_id=worker_id, lease_token=lease_token
    )
    checkpoints = dict(execution.get("checkpoints") or {})
    existing = checkpoints.get(checkpoint_key)
    if isinstance(existing, dict) and existing.get("status") == "ready":
        # Crash-after-commit reuse: do not rewrite.
        return existing
    checkpoints[checkpoint_key] = {
        **checkpoint_payload,
        "status": "ready",
        "updated_at": _now(),
        "lease_token": lease_token,
        "worker_id": worker_id,
    }
    execution["checkpoints"] = checkpoints
    execution["heartbeat_at"] = _now()
    write_learn_execution(generation, execution)
    await session.flush()
    return checkpoints[checkpoint_key]


__all__ = [
    "LEARN_EXECUTION_KEY",
    "LearnCancelledError",
    "LearnFenceError",
    "assert_learn_commit_allowed",
    "assert_learn_dispatch_allowed",
    "cancel_learn_execution",
    "fail_stale_learn_executions",
    "claim_learn_execution",
    "commit_learn_checkpoint",
    "empty_learn_execution_meta",
    "learn_execution_from_generation",
    "LEARN_LEASE_SECONDS",
    "require_learn_lease",
    "write_learn_execution",
]
