"""Test-only stand-in for the retired Print output claim.

Option D (4A) moved Print output execution onto the shared generation runtime
and deleted ``PageDocumentRepository.claim_execution``.  Several tests still
need *a live page-document lease* to exercise the kept lease-fenced seam
(``mutate_state`` fencing).  This helper installs one without any production
path (Option D 3A also deleted ``heartbeat`` and the pre-worker retry path).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.database.models import GenerationModel
from print.generation.whole_lesson.events import make_event
from print.generation.whole_lesson.repository import PageDocumentRepository, empty_execution_meta
from print.generation.whole_lesson.states import (
    WORK_KIND_POST_APPROVAL,
    ExecutionLease,
    assert_legal_transition,
)


class _NoClaim(Exception):
    pass


async def claim_test_execution(
    repo: PageDocumentRepository,
    *,
    worker_id: str,
    lease_seconds: int = 300,
) -> ExecutionLease | None:
    """Claim a ``queued`` (or stale active) generation like the retired claim did."""
    box: list[ExecutionLease] = []

    def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
        status = str(generation.status or "")
        execution = dict(state.get("execution") or empty_execution_meta())
        heartbeat_raw = execution.get("heartbeat_at")
        heartbeat = datetime.fromisoformat(heartbeat_raw) if heartbeat_raw else None
        lease = int(execution.get("lease_seconds") or lease_seconds)
        now = datetime.now(UTC)
        stale = heartbeat is None or (now - heartbeat).total_seconds() > lease
        if status == "queued":
            assert_legal_transition(status, "planning_forms")
            generation.status = "planning_forms"
            target = "planning_forms"
        elif status in {"planning_forms", "assembling"} and stale:
            target = status
        else:
            raise _NoClaim()
        token = int(execution.get("lease_token") or 0) + 1
        execution.update(
            {
                "worker_id": worker_id,
                "lease_token": token,
                "claimed_at": now.isoformat(),
                "heartbeat_at": now.isoformat(),
                "lease_seconds": lease_seconds,
                "attempt": int(execution.get("attempt") or 0) + 1,
                "work_kind": WORK_KIND_POST_APPROVAL,
            }
        )
        state["execution"] = execution
        events = list(state.get("events") or [])
        events.append(
            {
                **make_event(
                    "execution_claimed",
                    generation_id=repo.generation_id,
                    status=target,
                    worker_id=worker_id,
                    lease_token=token,
                ),
                "at": now.isoformat(),
            }
        )
        state["events"] = events[-500:]
        box.append(
            ExecutionLease(
                generation_id=repo.generation_id,
                worker_id=worker_id,
                lease_token=token,
                stage=target,
            )
        )

    try:
        await repo.mutate_state(mutation=_mut)
    except _NoClaim:
        await repo.session.rollback()
        return None
    return box[0] if box else None


async def heartbeat_test_execution(
    repo: PageDocumentRepository, *, worker_id: str, lease_token: int
) -> None:
    """Lease-fenced ``heartbeat_at`` write (the retired ``repo.heartbeat``)."""

    def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
        execution = dict(state.get("execution") or empty_execution_meta())
        execution["heartbeat_at"] = datetime.now(UTC).isoformat()
        state["execution"] = execution

    await repo.mutate_state(worker_id=worker_id, lease_token=lease_token, mutation=_mut)
