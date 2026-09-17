"""Learn mid-run durable reliability persistence (correction pass C01/C02).

Recovery authority is committed ``generations.chunked_state_json``, written via
short independent sessions so heartbeat and generation never share a locked
AsyncSession across provider I/O.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from core.database.models import GenerationModel
from core.database.session import async_session_factory
from infra.execution.call_budget import CallBudgetLedger
from infra.execution.checkpoints import CheckpointStore
from infra.execution.progress import ProgressStore
from learn.generation.fencing import (
    LearnCancelledError,
    LearnFenceError,
    assert_learn_commit_allowed,
    learn_execution_from_generation,
    write_learn_execution,
)

logger = logging.getLogger(__name__)

LEARN_HEARTBEAT_INTERVAL_SECONDS = 25.0


async def _persist_learn_reliability_state_once(
    *,
    generation_id: str,
    budget_ledger: CallBudgetLedger | None = None,
    checkpoint_store: CheckpointStore | None = None,
    progress_store: ProgressStore | None = None,
    progress_run_id: str | None = None,
    worker_id: str | None = None,
    lease_token: int | None = None,
    renew_heartbeat: bool = False,
    session_factory: Any | None = None,
) -> dict[str, Any]:
    """Commit ledger/checkpoint/progress (+ optional heartbeat) under ownership fence.

    Raises LearnFenceError / LearnCancelledError so callers cannot treat a failed
    durable write as success. Uses an independent session + ``commit()``.
    """
    factory = session_factory or async_session_factory
    async with factory() as session:
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
        if worker_id is not None and lease_token is not None:
            assert_learn_commit_allowed(
                execution, worker_id=worker_id, lease_token=lease_token
            )
            if renew_heartbeat:
                from learn.generation.fencing import _now

                execution["heartbeat_at"] = _now()
                write_learn_execution(generation, execution)

        payload = dict(generation.chunked_state_json or {})
        if budget_ledger is not None:
            payload["call_budget_ledger"] = budget_ledger.export_state()
        if checkpoint_store is not None:
            payload["checkpoint_store"] = checkpoint_store.snapshot()
        if progress_store is not None and progress_run_id:
            try:
                payload["progress_store"] = progress_store.snapshot(progress_run_id)
            except KeyError:
                pass
        # Preserve learn_execution key written above.
        if "learn_execution" in (generation.chunked_state_json or {}):
            payload["learn_execution"] = dict(
                (generation.chunked_state_json or {}).get("learn_execution") or {}
            )
        generation.chunked_state_json = payload
        await session.commit()
        return {
            "generation_id": generation_id,
            "budget_items": len(payload.get("call_budget_ledger") or {}),
            "checkpoints": len(payload.get("checkpoint_store") or {}),
            "heartbeat_at": (payload.get("learn_execution") or {}).get("heartbeat_at"),
        }


async def persist_learn_reliability_state(
    **kwargs: Any,
) -> dict[str, Any]:
    """Persist reliability state, retrying transient SQLite writer contention.

    Production uses Postgres row locks, while the offline integration suite
    intentionally uses SQLite.  The heartbeat and the provider budget hook can
    legitimately overlap there; retry the whole short transaction instead of
    turning that transient lock into a generation failure.
    """
    for attempt in range(4):
        try:
            return await _persist_learn_reliability_state_once(**kwargs)
        except OperationalError as exc:
            if "database is locked" not in str(exc).lower() or attempt == 3:
                raise
            await asyncio.sleep(0.1 * (2**attempt))


def make_budget_persist_hook(
    *,
    generation_id: str,
    budget_ledger: CallBudgetLedger,
    checkpoint_store: CheckpointStore | None = None,
    progress_store: ProgressStore | None = None,
    progress_run_id: str | None = None,
    worker_id: str | None = None,
    lease_token: int | None = None,
) -> Callable[[], Awaitable[None]]:
    """Return an awaitable that durable-persists after in-memory budget.reserve()."""

    async def _hook() -> None:
        await persist_learn_reliability_state(
            generation_id=generation_id,
            budget_ledger=budget_ledger,
            checkpoint_store=checkpoint_store,
            progress_store=progress_store,
            progress_run_id=progress_run_id,
            worker_id=worker_id,
            lease_token=lease_token,
            renew_heartbeat=True,
        )

    return _hook


async def learn_heartbeat_loop(
    *,
    generation_id: str,
    worker_id: str,
    lease_token: int,
    budget_ledger: CallBudgetLedger | None = None,
    checkpoint_store: CheckpointStore | None = None,
    progress_store: ProgressStore | None = None,
    progress_run_id: str | None = None,
    interval_seconds: float = LEARN_HEARTBEAT_INTERVAL_SECONDS,
    stop_event: asyncio.Event | None = None,
    session_factory: Any | None = None,
) -> None:
    """Renew Learn lease until stopped or ownership is lost."""
    stop = stop_event or asyncio.Event()
    first = True
    while not stop.is_set():
        if not first:
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=max(0.05, interval_seconds)
                )
                break
            except TimeoutError:
                pass
        first = False
        try:
            await persist_learn_reliability_state(
                generation_id=generation_id,
                budget_ledger=budget_ledger,
                checkpoint_store=checkpoint_store,
                progress_store=progress_store,
                progress_run_id=progress_run_id,
                worker_id=worker_id,
                lease_token=lease_token,
                renew_heartbeat=True,
                session_factory=session_factory,
            )
        except (LearnFenceError, LearnCancelledError, KeyError) as exc:
            logger.warning(
                "learn heartbeat stopped for %s: %s", generation_id, exc
            )
            stop.set()
            return
        except Exception:
            logger.exception("learn heartbeat persist failed for %s", generation_id)
            # Keep trying until fence rejects — transient DB errors should not
            # silently disable renewal for the rest of a long run.
            continue


__all__ = [
    "LEARN_HEARTBEAT_INTERVAL_SECONDS",
    "learn_heartbeat_loop",
    "make_budget_persist_hook",
    "persist_learn_reliability_state",
]
