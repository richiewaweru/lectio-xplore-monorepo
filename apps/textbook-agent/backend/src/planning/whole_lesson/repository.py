"""Persist whole-lesson planning artifacts in GenerationModel.chunked_state_json."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel
from planning.whole_lesson.events import make_event
from planning.whole_lesson.states import (
    ACTIVE_STATUSES,
    CLAIMABLE_STATUSES,
    DEFAULT_LEASE_SECONDS,
    ExecutionLease,
    IllegalTransitionError,
    LEGAL_TRANSITIONS,
    LeaseLostError,
    PRE_WORKER_RETRY_STATUSES,
    PRE_WORKER_WORK_KINDS,
    WORK_KIND_POST_APPROVAL,
    assert_legal_transition,
    execution_key,
)

PAGE_DOCUMENT_KEY = "page_document_v2"
# Visual topology checkpoints deliberately live beside (not inside) the page
# object.  A topology retry must never make an upstream page-object revision
# look as though it was recomputed.
VISUAL_TOPOLOGY_KEY = "visual_topology_v1"
_PAGE_STATE_LOCKS: dict[str, asyncio.Lock] = {}
_PAGE_STATE_LOCK_GUARD = asyncio.Lock()
_NATIVE_RUNNING_STAGES = ACTIVE_STATUSES | PRE_WORKER_RETRY_STATUSES | {
    "awaiting_teaching_approval",
    "awaiting_visuals",
    "queued",
}


async def _page_state_lock(generation_id: str) -> asyncio.Lock:
    async with _PAGE_STATE_LOCK_GUARD:
        lock = _PAGE_STATE_LOCKS.get(generation_id)
        if lock is None:
            lock = asyncio.Lock()
            _PAGE_STATE_LOCKS[generation_id] = lock
        return lock


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coerce_chunked(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _project_native_report_status(generation: GenerationModel) -> None:
    """Mirror native execution truth into the report without owning artifact state."""
    native_stage = str(generation.status or "").strip()
    if not native_stage:
        return

    report = (
        dict(generation.report_json)
        if isinstance(generation.report_json, dict)
        else {}
    )
    report["native_stage"] = native_stage
    if native_stage in {"failed_recoverable", "failed_terminal"}:
        report["process_status"] = native_stage
    elif native_stage == "ready":
        report["process_status"] = "completed"
    elif native_stage in _NATIVE_RUNNING_STAGES:
        report["process_status"] = "running"
    generation.report_json = report


def empty_execution_meta() -> dict[str, Any]:
    return {
        "worker_id": None,
        "lease_token": 0,
        "attempt": 0,
        "claimed_at": None,
        "heartbeat_at": None,
        "lease_seconds": DEFAULT_LEASE_SECONDS,
        "last_error": None,
        "pre_worker_retry_active": False,
        "work_kind": None,
        "document_sha256": None,
        "reloaded_sha256": None,
        "reload_verified": False,
        "candidate_document_sha256": None,
        "candidate_lease_token": None,
        "candidate_written_at": None,
    }


def apply_generation_error_aliases(
    generation: GenerationModel,
    error: Mapping[str, Any] | dict[str, Any] | None,
) -> None:
    """Mirror structured last_error onto GenerationModel error columns."""
    if not isinstance(error, Mapping):
        generation.error = None
        generation.error_type = None
        generation.error_code = None
        return
    generation.error = str(error.get("message") or "")[:2000] or None
    generation.error_type = str(error.get("type") or "") or None
    generation.error_code = str(error.get("code") or "") or None


def clear_generation_error_state(
    generation: GenerationModel,
    state: dict[str, Any],
) -> None:
    """Clear generation-level error aliases together with execution.last_error."""
    apply_generation_error_aliases(generation, None)
    execution = dict(state.get("execution") or empty_execution_meta())
    execution["last_error"] = None
    execution["pre_worker_retry_active"] = False
    execution["work_kind"] = None
    state["execution"] = execution
    chunked = _coerce_chunked(generation.chunked_state_json)
    chunked.pop("error", None)
    chunked.pop("error_type", None)
    generation.chunked_state_json = chunked


def empty_page_document_state() -> dict[str, Any]:
    """Empty page_document_v2 state.

    schema_version 1: optional fat FormPlan; no lesson_legality.
    schema_version 2: slim FormDecision; persisted LessonLegalitySnapshot required
    for form planning/resume revalidation.
    """
    return {
        "schema_version": 2,
        "lesson_packet": None,
        "lesson_legality": None,
        "catalogue": {
            "version": None,
            "teaching_projection_hash": None,
            "form_projection_hash": None,
        },
        "teaching_plan": None,
        "teaching_validation": None,
        "teaching_qc": [],
        "teaching_raw": None,
        "teaching_prompt": None,
        "teaching_review": {
            "status": "pending",
            "reviewed_by": None,
            "reviewed_at": None,
            "revision": 1,
            "teacher_note": None,
        },
        "form_plan": None,
        "form_validation": None,
        "form_qc": [],
        "form_raw": None,
        "form_prompt": None,
        "block_execution": {},
        "execution": empty_execution_meta(),
        "advisory_qc": [],
        "events": [],
        "last_heartbeat": None,
        "document_revision": 0,
    }


def _normalize_page_state(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict):
        state = empty_page_document_state()
    else:
        state = deepcopy(state)
    execution = dict(state.get("execution") or {})
    base = empty_execution_meta()
    base.update(execution)
    if "lease_token" not in execution:
        base["lease_token"] = int(execution.get("lease_token") or 0)
    state["execution"] = base
    if not isinstance(state.get("block_execution"), dict):
        state["block_execution"] = {}
    return state


class _ClaimAbort(Exception):
    """Internal: claim could not be acquired."""


class DocumentFenceError(RuntimeError):
    """Raised when candidate/finalize fencing checks fail."""


class VisualRequestNotFound(LookupError):
    pass


class VisualCompletionConflict(RuntimeError):
    pass


class VisualCompletionInvariantError(RuntimeError):
    """Missing execution outcome or unknown asset status."""


class VisualCompletionStateError(RuntimeError):
    """Visual callback received in an unrelated generation status."""


class VisualTopologyConflict(RuntimeError):
    """A request id was persisted with a different topology identity."""


class VisualTopologyNotFound(LookupError):
    """A requested topology checkpoint does not exist."""


def _invalidate_reload_proof(execution: dict[str, Any]) -> None:
    """Clear final document proof after any material visual mutation.

    A visual patch changes the persisted document revision. Hashes from the prior
    candidate therefore cannot authorize ``ready`` for the new document.
    """
    execution["document_sha256"] = None
    execution["reloaded_sha256"] = None
    execution["reload_verified"] = False
    execution["candidate_document_sha256"] = None
    execution["candidate_lease_token"] = None
    execution["candidate_written_at"] = None


_UNRESOLVED_ASSET_STATUSES = frozenset({"pending", "generating", "failed"})
_VISUAL_CALLBACK_STATUSES = frozenset({"awaiting_visuals", "ready"})


def visual_outcome_status(asset_status: str) -> str:
    status = str(asset_status or "").strip()
    if status == "ready":
        return "ready"
    if status in {"pending", "generating"}:
        return "visual_pending"
    if status == "failed":
        return "failed_recoverable"
    raise VisualCompletionInvariantError(f"unknown asset status {status!r}")


@dataclass(frozen=True)
class VisualCompletionResult:
    generation_id: str
    block_id: str
    request_id: str
    status: str
    document_revision: int
    idempotent: bool


class PageDocumentRepository:
    def __init__(self, session: AsyncSession, generation_id: str) -> None:
        self.session = session
        self.generation_id = generation_id

    async def _lock_generation(self) -> GenerationModel:
        result = await self.session.execute(
            select(GenerationModel)
            .where(GenerationModel.id == self.generation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        generation = result.scalar_one_or_none()
        if generation is None:
            raise KeyError(f"generation {self.generation_id!r} not found")
        await self.session.refresh(generation)
        return generation

    def _page_state_from_generation(self, generation: GenerationModel) -> dict[str, Any]:
        chunked = _coerce_chunked(generation.chunked_state_json)
        return _normalize_page_state(chunked.get(PAGE_DOCUMENT_KEY))

    def _write_page_state(
        self,
        generation: GenerationModel,
        state: dict[str, Any],
        *,
        stage: str | None = None,
    ) -> dict[str, Any]:
        state = deepcopy(state)
        state["last_heartbeat"] = _now()
        chunked = _coerce_chunked(generation.chunked_state_json)
        chunked[PAGE_DOCUMENT_KEY] = state
        if stage is not None:
            chunked["stage"] = stage
        elif generation.status:
            chunked["stage"] = str(generation.status)
        generation.chunked_state_json = chunked
        _project_native_report_status(generation)
        return state

    async def require_execution_lease(
        self,
        *,
        worker_id: str,
        lease_token: int,
    ) -> GenerationModel:
        """Row-lock the generation and assert lease ownership in this transaction."""
        generation = await self._lock_generation()
        state = self._page_state_from_generation(generation)
        self._assert_lease_on_state(
            state,
            worker_id=worker_id,
            lease_token=lease_token,
        )
        return generation

    async def mutate_state(
        self,
        *,
        expected_statuses: set[str] | None = None,
        worker_id: str | None = None,
        lease_token: int | None = None,
        mutation: Callable[[GenerationModel, dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Row-locked page-document mutation. Correctness boundary for Phase 02."""
        lock = await _page_state_lock(self.generation_id)
        async with lock:
            generation = await self._lock_generation()
            current = str(generation.status or "")
            if expected_statuses is not None and current not in expected_statuses:
                raise IllegalTransitionError(
                    f"expected status in {sorted(expected_statuses)}, got {current!r}"
                )
            state = self._page_state_from_generation(generation)
            if worker_id is not None or lease_token is not None:
                self._assert_lease_on_state(
                    state,
                    worker_id=worker_id,
                    lease_token=lease_token,
                )
            mutation(generation, state)
            stage = str(generation.status or "") or None
            saved = self._write_page_state(generation, state, stage=stage)
            await self.session.commit()
            return saved

    def _assert_lease_on_state(
        self,
        state: dict[str, Any],
        *,
        worker_id: str | None,
        lease_token: int | None,
    ) -> None:
        execution = dict(state.get("execution") or empty_execution_meta())
        if worker_id is not None and execution.get("worker_id") != worker_id:
            raise LeaseLostError(
                f"lease worker mismatch: have {execution.get('worker_id')!r}, "
                f"want {worker_id!r}"
            )
        if lease_token is not None and int(execution.get("lease_token") or 0) != int(
            lease_token
        ):
            raise LeaseLostError(
                f"lease token mismatch: have {execution.get('lease_token')!r}, "
                f"want {lease_token!r}"
            )

    async def assert_lease(self, *, worker_id: str, lease_token: int) -> None:
        generation = await self._lock_generation()
        state = self._page_state_from_generation(generation)
        self._assert_lease_on_state(state, worker_id=worker_id, lease_token=lease_token)

    async def load_page_generation_state(self) -> dict[str, Any]:
        generation = await self.session.get(GenerationModel, self.generation_id)
        if generation is None:
            raise KeyError(f"generation {self.generation_id!r} not found")
        return self._page_state_from_generation(generation)

    async def load_visual_topology_state(self) -> dict[str, Any]:
        """Load the bounded topology checkpoint outside ``page_document_v2``."""
        generation = await self.session.get(GenerationModel, self.generation_id)
        if generation is None:
            raise KeyError(f"generation {self.generation_id!r} not found")
        chunked = _coerce_chunked(generation.chunked_state_json)
        raw = chunked.get(VISUAL_TOPOLOGY_KEY)
        if not isinstance(raw, dict):
            return {"schema_version": "visual-topology/1", "requests": {}, "history": [], "events": []}
        state = deepcopy(raw)
        state.setdefault("schema_version", "visual-topology/1")
        state.setdefault("requests", {})
        state.setdefault("history", [])
        state.setdefault("events", [])
        return state

    async def persist_visual_topology(
        self,
        *,
        request_id: str,
        record: dict[str, Any],
        identity_digest: str,
        history_limit: int = 20,
    ) -> dict[str, Any]:
        """Atomically persist one validated topology checkpoint.

        The request identity is a fence: exact repeats are reused, while a
        changed source/labels/version digest fails closed before rendering.
        This mutation only changes the top-level chunked checkpoint and event
        ledger; page-object JSON, revision, and upstream artifacts are untouched.
        """
        rid = str(request_id or "").strip()
        if not rid:
            raise ValueError("request_id is required")
        digest = str(identity_digest or "").strip()
        if not digest:
            raise ValueError("identity_digest is required")
        result_box: list[dict[str, Any]] = []

        def _mut(generation: GenerationModel, _page: dict[str, Any]) -> None:
            # JSON columns are not mutable-tracked. Work on a fresh object so
            # topology checkpoints cannot be lost when the ORM compares the
            # pre-mutation value with the post-mutation value.
            chunked = deepcopy(_coerce_chunked(generation.chunked_state_json))
            topology = chunked.get(VISUAL_TOPOLOGY_KEY)
            if not isinstance(topology, dict):
                topology = {
                    "schema_version": "visual-topology/1",
                    "requests": {},
                    "history": [],
                    "events": [],
                }
            requests = topology.get("requests")
            if not isinstance(requests, dict):
                requests = {}
            existing = requests.get(rid)
            if isinstance(existing, dict):
                existing_digest = str(existing.get("identity_digest") or "")
                if existing_digest != digest:
                    raise VisualTopologyConflict(
                        f"topology request {rid!r} identity mismatch"
                    )
                result_box.append({"record": deepcopy(existing), "reused": True})
                return

            persisted = deepcopy(record)
            persisted["request_id"] = rid
            persisted["identity_digest"] = digest
            requests[rid] = persisted
            history = [
                item for item in (topology.get("history") or []) if isinstance(item, dict)
            ]
            history.append(deepcopy(persisted))
            topology["history"] = history[-max(1, int(history_limit)):]
            topology["requests"] = requests
            topology["schema_version"] = "visual-topology/1"
            events = [
                item for item in (topology.get("events") or []) if isinstance(item, dict)
            ]
            events.append(
                {
                    "type": "topology_persisted",
                    "generation_id": self.generation_id,
                    "request_id": rid,
                    "identity_digest": digest,
                    "topology_sha256": persisted.get("topology_sha256"),
                    "at": _now(),
                }
            )
            topology["events"] = events[-100:]
            chunked[VISUAL_TOPOLOGY_KEY] = topology
            generation.chunked_state_json = chunked
            result_box.append({"record": deepcopy(persisted), "reused": False})

        # ``mutate_state`` writes the page state back, so use the same row lock
        # and transaction boundary while preserving the existing page object.
        lock = await _page_state_lock(self.generation_id)
        async with lock:
            generation = await self._lock_generation()
            page = self._page_state_from_generation(generation)
            _mut(generation, page)
            await self.session.commit()
        return result_box[0]

    async def append_visual_topology_event(
        self,
        *,
        event_type: str,
        request_id: str,
        payload: Mapping[str, Any] | None = None,
        event_limit: int = 100,
    ) -> dict[str, Any]:
        """Append a topology event without touching page-object state."""
        event_payload = dict(payload or {})
        event_payload.update(
            {
                "type": str(event_type),
                "generation_id": self.generation_id,
                "request_id": str(request_id),
                "at": _now(),
            }
        )
        lock = await _page_state_lock(self.generation_id)
        async with lock:
            generation = await self._lock_generation()
            # See persist_visual_topology: nested JSON mutation must start from
            # a detached copy to produce a durable column update.
            chunked = deepcopy(_coerce_chunked(generation.chunked_state_json))
            topology = chunked.get(VISUAL_TOPOLOGY_KEY)
            if not isinstance(topology, dict):
                topology = {
                    "schema_version": "visual-topology/1",
                    "requests": {},
                    "history": [],
                    "events": [],
                }
            events = [item for item in (topology.get("events") or []) if isinstance(item, dict)]
            events.append(event_payload)
            topology["events"] = events[-max(1, int(event_limit)):]
            chunked[VISUAL_TOPOLOGY_KEY] = topology
            generation.chunked_state_json = chunked
            await self.session.commit()
        return event_payload

    async def transition(
        self,
        *,
        expected: set[str],
        target: str,
        event: str,
        error: dict[str, Any] | None = None,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            current = str(generation.status or "")
            assert_legal_transition(current, target)
            generation.status = target
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["heartbeat_at"] = _now()
            if error is not None:
                execution["last_error"] = error
                apply_generation_error_aliases(generation, error)
            elif target in {
                "ready",
                "queued",
                "planning_forms",
                "awaiting_teaching_approval",
            }:
                clear_generation_error_state(generation, state)
                execution = dict(state.get("execution") or empty_execution_meta())
                execution["heartbeat_at"] = _now()
            state["execution"] = execution
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(event, generation_id=self.generation_id, status=target),
                    "at": _now(),
                    "error": error,
                }
            )
            state["events"] = events[-500:]

        return await self.mutate_state(
            expected_statuses=expected,
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def persist_native_failure(
        self,
        *,
        exc: BaseException,
        stage: str,
        event: str = "native_failure",
        attempt: int = 1,
        worker_id: str | None = None,
        lease_token: int | None = None,
        expected: set[str] | None = None,
    ) -> dict[str, Any]:
        """Atomically persist a native failure across status, chunked stage, error, and event.

        Ensures page_document_v2 exists, classifies the exception, and transitions to
        failed_recoverable or failed_terminal. Clears legacy stage2_error as durable truth.
        """
        from planning.whole_lesson.failure_policy import (
            classify_failure,
            structured_error_from_exc,
        )

        classification = classify_failure(exc)
        if classification.code in {"LEASE_LOST", "CANCELLED"}:
            return await self.load_page_generation_state()

        recoverable = classification.code in {
            "TRANSPORT",
            "TIMEOUT",
            "RATE_LIMIT",
            "MODEL_OUTPUT_INVALID",
        }
        target = "failed_recoverable" if recoverable else "failed_terminal"
        error = structured_error_from_exc(
            exc=exc,
            stage=stage,
            attempt=attempt,
        )

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            # Ensure page document scaffold exists even before teaching plan.
            if not state or state.get("schema_version") is None:
                base = empty_page_document_state()
                base.update(state or {})
                state.clear()
                state.update(base)
            for key, value in empty_page_document_state().items():
                state.setdefault(key, deepcopy(value) if isinstance(value, (dict, list)) else value)
            if not isinstance(state.get("execution"), dict):
                state["execution"] = empty_execution_meta()
            if not isinstance(state.get("events"), list):
                state["events"] = []

            current = str(generation.status or "").strip() or "pending"
            # Normalize legacy chunked-only stage2_error onto a legal source status.
            chunked = _coerce_chunked(generation.chunked_state_json)
            chunked_stage = str(chunked.get("stage") or "")
            if current not in LEGAL_TRANSITIONS and chunked_stage in LEGAL_TRANSITIONS:
                current = chunked_stage
                generation.status = current
            if current not in LEGAL_TRANSITIONS:
                current = "pending"
                generation.status = current

            assert_legal_transition(current, target)
            generation.status = target
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["heartbeat_at"] = _now()
            execution["last_error"] = error
            execution["attempt"] = int(execution.get("attempt") or 0) + 1
            execution["pre_worker_retry_active"] = False
            execution["work_kind"] = None
            execution["worker_id"] = None
            execution["claimed_at"] = None
            state["execution"] = execution
            apply_generation_error_aliases(generation, error)
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        event,
                        generation_id=self.generation_id,
                        status=target,
                    ),
                    "at": _now(),
                    "error": error,
                    "stage": stage,
                }
            )
            state["events"] = events[-500:]
            # Clear legacy stage2_error keys from the outer chunked blob after write
            # by stamping authoritative stage via _write_page_state.
            chunked_out = _coerce_chunked(generation.chunked_state_json)
            if chunked_out.get("stage") == "stage2_error":
                chunked_out["stage"] = target
            generation.chunked_state_json = chunked_out

        return await self.mutate_state(
            expected_statuses=expected,
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def claim_execution(
        self,
        *,
        worker_id: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> ExecutionLease | None:
        lease_box: list[ExecutionLease] = []

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            status = str(generation.status or "")
            execution = dict(state.get("execution") or empty_execution_meta())
            now = datetime.now(timezone.utc)
            heartbeat = _parse_iso(execution.get("heartbeat_at"))
            lease = int(execution.get("lease_seconds") or lease_seconds)
            stale = heartbeat is None or heartbeat + timedelta(seconds=lease) < now

            if status in CLAIMABLE_STATUSES:
                assert_legal_transition(status, "planning_forms")
                generation.status = "planning_forms"
                target_stage = "planning_forms"
                event_name = "execution_claimed"
            elif status in ACTIVE_STATUSES and stale:
                target_stage = status
                event_name = "execution_reclaimed"
            else:
                raise _ClaimAbort()

            new_token = int(execution.get("lease_token") or 0) + 1
            execution["worker_id"] = worker_id
            execution["lease_token"] = new_token
            execution["claimed_at"] = _now()
            execution["heartbeat_at"] = _now()
            execution["lease_seconds"] = lease_seconds
            execution["attempt"] = int(execution.get("attempt") or 0) + 1
            execution["work_kind"] = WORK_KIND_POST_APPROVAL
            state["execution"] = execution
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        event_name,
                        generation_id=self.generation_id,
                        status=target_stage,
                        worker_id=worker_id,
                        lease_token=new_token,
                    ),
                    "at": _now(),
                }
            )
            state["events"] = events[-500:]
            lease_box.append(
                ExecutionLease(
                    generation_id=self.generation_id,
                    worker_id=worker_id,
                    lease_token=new_token,
                    stage=target_stage,
                )
            )

        try:
            await self.mutate_state(mutation=_mut)
        except _ClaimAbort:
            await self.session.rollback()
            return None
        return lease_box[0] if lease_box else None

    async def claim_pre_worker_retry(
        self,
        *,
        worker_id: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> ExecutionLease | None:
        """Claim an unclaimed or stale pre-worker retry without forcing planning_forms."""
        lease_box: list[ExecutionLease] = []

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            status = str(generation.status or "")
            if status not in PRE_WORKER_RETRY_STATUSES:
                raise _ClaimAbort()
            execution = dict(state.get("execution") or empty_execution_meta())
            work_kind = execution.get("work_kind")
            if work_kind not in PRE_WORKER_WORK_KINDS:
                raise _ClaimAbort()

            now = datetime.now(timezone.utc)
            heartbeat = _parse_iso(execution.get("heartbeat_at"))
            lease = int(execution.get("lease_seconds") or lease_seconds)
            stale = heartbeat is None or heartbeat + timedelta(seconds=lease) < now
            current_owner = execution.get("worker_id")
            if current_owner is not None and not stale:
                raise _ClaimAbort()

            new_token = int(execution.get("lease_token") or 0) + 1
            event_name = (
                "pre_worker_retry_reclaimed"
                if current_owner is not None
                else "pre_worker_retry_claimed"
            )
            execution["worker_id"] = worker_id
            execution["lease_token"] = new_token
            execution["claimed_at"] = _now()
            execution["heartbeat_at"] = _now()
            execution["lease_seconds"] = lease_seconds
            execution["attempt"] = int(execution.get("attempt") or 0) + 1
            state["execution"] = execution
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        event_name,
                        generation_id=self.generation_id,
                        status=status,
                        worker_id=worker_id,
                        lease_token=new_token,
                    ),
                    "at": _now(),
                    "work_kind": work_kind,
                }
            )
            state["events"] = events[-500:]
            lease_box.append(
                ExecutionLease(
                    generation_id=self.generation_id,
                    worker_id=worker_id,
                    lease_token=new_token,
                    stage=status,
                )
            )

        try:
            await self.mutate_state(mutation=_mut)
        except _ClaimAbort:
            await self.session.rollback()
            return None
        return lease_box[0] if lease_box else None

    async def heartbeat(self, *, worker_id: str, lease_token: int) -> None:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["heartbeat_at"] = _now()
            state["execution"] = execution

        await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def release_execution(self, *, worker_id: str, lease_token: int | None = None) -> None:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("execution") or empty_execution_meta())
            if execution.get("worker_id") not in {None, worker_id}:
                raise LeaseLostError("release rejected: worker does not own lease")
            if lease_token is not None and int(execution.get("lease_token") or 0) != int(
                lease_token
            ):
                raise LeaseLostError("release rejected: lease token mismatch")
            execution["worker_id"] = None
            execution["claimed_at"] = None
            state["execution"] = execution

        await self.mutate_state(mutation=_mut)

    async def load_block_results(self) -> dict[str, dict[str, Any]]:
        state = await self.load_page_generation_state()
        raw = state.get("block_execution") or {}
        return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}

    async def save_block_outcome(
        self,
        key: str,
        outcome: dict[str, Any],
        *,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("block_execution") or {})
            previous = dict(execution.get(key) or {})
            merged = {**previous, **outcome, "updated_at": _now()}
            if worker_id is not None:
                merged["worker_id"] = worker_id
            if lease_token is not None:
                merged["lease_token"] = lease_token
            if "created_at" not in merged:
                merged["created_at"] = previous.get("created_at") or _now()
            execution[key] = merged
            state["block_execution"] = execution
            content = merged.get("content") or {}
            asset = content.get("asset") if isinstance(content, dict) else None
            asset_status = str(asset.get("status") or "") if isinstance(asset, dict) else ""
            if str(merged.get("object") or "") == "figure" and (
                str(merged.get("status") or "") == "visual_pending"
                or asset_status in _UNRESOLVED_ASSET_STATUSES
            ):
                proof = dict(state.get("execution") or empty_execution_meta())
                _invalidate_reload_proof(proof)
                state["execution"] = proof

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def load_expected_writer_results(
        self,
        *,
        form_plan: dict[str, Any],
        variant_id: str = "everyone",
    ) -> dict[str, dict[str, Any]]:
        expected: dict[str, dict[str, Any]] = {}
        stored = await self.load_block_results()
        for section in form_plan.get("sections") or []:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("slot_id") or "")
            decisions = section.get("forms")
            if not isinstance(decisions, list):
                # Legacy fat form_plan used blocks[].id
                decisions = section.get("blocks") or []
            for block in decisions:
                if not isinstance(block, dict):
                    continue
                block_id = str(block.get("block_id") or block.get("id") or "")
                key = execution_key(section_id, block_id, variant_id)
                expected[key] = stored.get(key) or {}
        return expected

    async def save_lesson_packet(
        self,
        packet: dict[str, Any],
        *,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            state["lesson_packet"] = packet

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def save_lesson_legality(
        self,
        legality: dict[str, Any],
        *,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            state["lesson_legality"] = legality
            state["schema_version"] = 2

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def load_lesson_legality(self) -> dict[str, Any]:
        """Fail closed: missing/invalid snapshot is an execution error."""
        from planning.whole_lesson.legality import (
            LessonLegalityError,
            LessonLegalitySnapshot,
        )

        state = await self.load_page_generation_state()
        raw = state.get("lesson_legality")
        if not isinstance(raw, dict) or not raw:
            raise LessonLegalityError(
                "lesson_legality snapshot missing; cannot plan forms or resume",
                code="LESSON_LEGALITY_MISSING",
            )
        try:
            snapshot = LessonLegalitySnapshot.model_validate(raw)
        except Exception as exc:  # noqa: BLE001
            raise LessonLegalityError(
                f"lesson_legality snapshot invalid: {exc}",
                code="LESSON_LEGALITY_INVALID",
            ) from exc
        return snapshot.model_dump(mode="json")

    async def save_catalogue_meta(
        self,
        *,
        version: str,
        teaching_projection_hash: str | None = None,
        form_projection_hash: str | None = None,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            catalogue = dict(state.get("catalogue") or {})
            catalogue["version"] = version
            if teaching_projection_hash is not None:
                catalogue["teaching_projection_hash"] = teaching_projection_hash
            if form_projection_hash is not None:
                catalogue["form_projection_hash"] = form_projection_hash
            state["catalogue"] = catalogue

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def save_teaching_plan(
        self,
        *,
        plan: dict[str, Any],
        validation: dict[str, Any],
        qc: list[dict[str, Any]],
        prompt: str | None = None,
        raw: str | None = None,
        stage: str = "awaiting_teaching_approval",
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        """Initialize teaching-plan artifacts and enter awaiting_teaching_approval.

        Direct status assignment is allowed only for this pre-state-machine init.
        When worker_id/lease_token are provided, the write is lease-fenced.
        """

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            state["teaching_plan"] = plan
            state["teaching_validation"] = validation
            state["teaching_qc"] = qc
            if prompt is not None:
                state["teaching_prompt"] = prompt
            if raw is not None:
                state["teaching_raw"] = raw
            review = dict(state.get("teaching_review") or {})
            review["status"] = "pending"
            review["revision"] = int(review.get("revision") or 1)
            state["teaching_review"] = review
            if not isinstance(state.get("execution"), dict):
                state["execution"] = empty_execution_meta()
            current = str(generation.status or "").strip() or "pending"
            if current in LEGAL_TRANSITIONS and stage in LEGAL_TRANSITIONS.get(
                current, frozenset()
            ):
                assert_legal_transition(current, stage)
            generation.status = stage
            if stage == "awaiting_teaching_approval":
                clear_generation_error_state(generation, state)

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def save_teaching_review(
        self,
        *,
        status: str,
        expected_revision: int,
        reviewed_by: str | None = None,
        teacher_note: str | None = None,
        queue: bool = False,
    ) -> dict[str, Any]:
        post_approval = {
            "queued",
            "planning_forms",
            "writing_sections",
            "writing_blocks",
            "assembling",
            "awaiting_visuals",
            "ready",
            "completed",
        }
        boxed: list[dict[str, Any]] = []

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            review = dict(state.get("teaching_review") or {})
            current_rev = int(review.get("revision") or 1)
            if expected_revision != current_rev:
                raise ValueError(
                    f"stale teaching revision: expected {expected_revision}, current {current_rev}"
                )
            gen_status = str(generation.status or "")
            if status == "approved" and queue and gen_status in post_approval:
                boxed.append(state)
                return
            review["status"] = status
            review["reviewed_by"] = reviewed_by
            review["reviewed_at"] = _now()
            review["teacher_note"] = teacher_note
            if status == "approved":
                review["revision"] = current_rev + 1
            state["teaching_review"] = review
            if status == "approved" and queue:
                current = str(generation.status or "")
                assert_legal_transition(current, "queued")
                generation.status = "queued"
                clear_generation_error_state(generation, state)
                execution = dict(state.get("execution") or empty_execution_meta())
                execution["heartbeat_at"] = _now()
                state["execution"] = execution
                events = list(state.get("events") or [])
                events.append(
                    {
                        **make_event(
                            "teaching_plan_approved",
                            generation_id=self.generation_id,
                            status="queued",
                        ),
                        "at": _now(),
                    }
                )
                state["events"] = events[-500:]
                boxed.append(state)
                return
            if status == "rejected":
                current = str(generation.status or "")
                # Rejection is terminal alias outside the main graph.
                generation.status = "rejected_by_teacher"
            elif status == "approved":
                # Non-queue legacy path should not be used for Phase 02.
                raise ValueError("approved teaching review requires queue=True")
            boxed.append(state)

        await self.mutate_state(mutation=_mut)
        return boxed[-1] if boxed else await self.load_page_generation_state()

    async def save_form_plan(
        self,
        *,
        plan: dict[str, Any],
        validation: dict[str, Any],
        qc: list[dict[str, Any]],
        catalogue_version: str | None = None,
        form_projection_hash: str | None = None,
        prompt: str | None = None,
        raw: str | None = None,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        """Persist form-plan artifacts only; stage transitions use transition()."""

        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            state["form_plan"] = plan
            state["form_validation"] = validation
            state["form_qc"] = qc
            if catalogue_version is not None or form_projection_hash is not None:
                catalogue = dict(state.get("catalogue") or {})
                if catalogue_version is not None:
                    catalogue["version"] = catalogue_version
                if form_projection_hash is not None:
                    catalogue["form_projection_hash"] = form_projection_hash
                state["catalogue"] = catalogue
            if prompt is not None:
                state["form_prompt"] = prompt
            if raw is not None:
                state["form_raw"] = raw

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def save_block_result(self, block_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Legacy helper: store under bare block_id (prefer save_block_outcome)."""
        return await self.save_block_outcome(block_id, result)

    async def save_qc_report(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            state["advisory_qc"] = findings

        return await self.mutate_state(mutation=_mut)

    async def append_event(
        self,
        event: dict[str, Any],
        *,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            events = list(state.get("events") or [])
            events.append({**event, "at": _now()})
            state["events"] = events[-500:]

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def bump_document_revision(
        self,
        *,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> int:
        box: list[int] = []

        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            revision = int(state.get("document_revision") or 0) + 1
            state["document_revision"] = revision
            box.append(revision)

        await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )
        return box[0] if box else 0

    async def persist_reload_proof(
        self,
        *,
        document_sha256: str,
        reloaded_sha256: str,
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["document_sha256"] = document_sha256
            execution["reloaded_sha256"] = reloaded_sha256
            execution["reload_verified"] = document_sha256 == reloaded_sha256
            state["execution"] = execution

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def persist_document_candidate(
        self,
        document: dict[str, Any],
        *,
        document_sha256: str,
        worker_id: str,
        lease_token: int,
    ) -> dict[str, Any]:
        """Lease-fenced write of document_json as a non-terminal candidate."""
        from generation.page_objects.document_assembly import persist_document_json

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            generation.document_json = persist_document_json(
                generation.document_json, document
            )
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["candidate_document_sha256"] = document_sha256
            execution["candidate_lease_token"] = int(lease_token)
            execution["candidate_written_at"] = _now()
            execution["heartbeat_at"] = _now()
            state["execution"] = execution

        return await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def persist_streaming_snapshot(
        self,
        document: dict[str, Any],
        *,
        document_sha256: str,
        section_ids: list[str],
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any]:
        """Persist a non-terminal partial LectioDocumentV2; bump revision only on change.

        Rejects non-monotonic shrinkage of streaming_section_ids (no revision bump).
        Does not set final SHA/reload fence fields.
        """
        return await self.assemble_and_persist_streaming_snapshot(
            assemble=lambda _generation, _stored: (
                document,
                list(section_ids),
                document_sha256,
            ),
            worker_id=worker_id,
            lease_token=lease_token,
        )

    async def assemble_and_persist_streaming_snapshot(
        self,
        *,
        assemble: Callable[
            [GenerationModel, dict[str, dict[str, Any]]],
            tuple[dict[str, Any], list[str], str] | None,
        ],
        worker_id: str | None = None,
        lease_token: int | None = None,
    ) -> dict[str, Any] | None:
        """Lock → re-read block_execution → assemble → monotonic gate → persist.

        Rejects if prior streaming_section_ids is not a subset of the new set.
        No-op (no revision bump) on shrinkage or identical sha.
        Does not set final SHA/reload fence fields.
        """
        from generation.page_objects.document_assembly import persist_document_json

        box: list[dict[str, Any] | None] = []

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            stored_raw = state.get("block_execution") or {}
            stored = {
                str(k): dict(v)
                for k, v in stored_raw.items()
                if isinstance(v, dict)
            }
            assembled = assemble(generation, stored)
            if assembled is None:
                box.append(None)
                return
            document, section_ids, document_sha256 = assembled
            execution = dict(state.get("execution") or empty_execution_meta())
            prior_ids = {
                str(sid)
                for sid in (execution.get("streaming_section_ids") or [])
                if sid
            }
            new_ids = {str(sid) for sid in section_ids if sid}
            revision = int(state.get("document_revision") or 0)
            prior_hash = str(execution.get("streaming_document_sha256") or "")

            if prior_ids and not prior_ids.issubset(new_ids):
                # Stale/partial assemble must not shrink a newer snapshot.
                state["execution"] = execution
                box.append(
                    {
                        "changed": False,
                        "rejected": "non_monotonic_section_set",
                        "document_revision": revision,
                        "document_sha256": prior_hash,
                        "section_ids": list(execution.get("streaming_section_ids") or []),
                    }
                )
                return

            changed = prior_hash != document_sha256
            if changed:
                generation.document_json = persist_document_json(
                    generation.document_json, document
                )
                revision += 1
                state["document_revision"] = revision
                execution["streaming_document_sha256"] = document_sha256
                execution["streaming_section_ids"] = list(section_ids)
                execution["streaming_updated_at"] = _now()
                # Explicitly not final: never set document_sha256 / reload_verified here.
                execution.pop("reload_verified", None)
            state["execution"] = execution
            if changed:
                events = list(state.get("events") or [])
                events.append(
                    {
                        **make_event(
                            "section_ready",
                            generation_id=self.generation_id,
                            status="streaming",
                            section_ids=section_ids,
                            document_revision=revision,
                        ),
                        "at": _now(),
                    }
                )
                state["events"] = events[-500:]
            box.append(
                {
                    "changed": changed,
                    "document_revision": revision,
                    "document_sha256": document_sha256 if changed else prior_hash or document_sha256,
                    "section_ids": list(
                        execution.get("streaming_section_ids") or section_ids
                    ),
                }
            )

        await self.mutate_state(
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )
        return box[0] if box else None

    async def finalize_verified_document(
        self,
        *,
        expected_document_sha256: str,
        reloaded_sha256: str,
        pending_visuals: bool,
        worker_id: str,
        lease_token: int,
    ) -> dict[str, Any]:
        """Atomic lease-fenced finalization after fresh-session hash verification."""
        from generation.page_objects.document_assembly import (
            canonical_document_sha256,
            reload_document,
        )

        target = "awaiting_visuals" if pending_visuals else "ready"
        event_name = "document_awaiting_visuals" if pending_visuals else "document_ready"

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("execution") or empty_execution_meta())
            candidate_sha = execution.get("candidate_document_sha256")
            candidate_token = execution.get("candidate_lease_token")
            if candidate_sha != expected_document_sha256:
                raise DocumentFenceError(
                    f"candidate sha mismatch: have {candidate_sha!r}, "
                    f"want {expected_document_sha256!r}"
                )
            if candidate_token is None or int(candidate_token) != int(lease_token):
                raise DocumentFenceError(
                    f"candidate lease token mismatch: have {candidate_token!r}, "
                    f"want {lease_token!r}"
                )
            if reloaded_sha256 != expected_document_sha256:
                raise DocumentFenceError(
                    f"reloaded sha mismatch: have {reloaded_sha256!r}, "
                    f"want {expected_document_sha256!r}"
                )
            try:
                persisted = reload_document(generation.document_json or {})
            except Exception as exc:  # noqa: BLE001
                raise DocumentFenceError(f"cannot reload persisted document: {exc}") from exc
            locked_sha = canonical_document_sha256(persisted)
            if locked_sha != expected_document_sha256:
                raise DocumentFenceError(
                    f"locked document tamper: have {locked_sha!r}, "
                    f"want {expected_document_sha256!r}"
                )
            current = str(generation.status or "")
            assert_legal_transition(current, target)
            generation.status = target
            if pending_visuals:
                # The candidate still contains unresolved visual assets. Keep it
                # non-terminal and require a fresh post-patch verification before
                # exposing final hash proof or transitioning to ready.
                _invalidate_reload_proof(execution)
            else:
                execution["document_sha256"] = expected_document_sha256
                execution["reloaded_sha256"] = reloaded_sha256
                execution["reload_verified"] = True
            execution["heartbeat_at"] = _now()
            state["execution"] = execution
            state["document_revision"] = int(state.get("document_revision") or 0) + 1
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        event_name,
                        generation_id=self.generation_id,
                        status=target,
                    ),
                    "at": _now(),
                }
            )
            state["events"] = events[-500:]

        return await self.mutate_state(
            expected_statuses={"assembling", "writing_sections", "writing_blocks"},
            worker_id=worker_id,
            lease_token=lease_token,
            mutation=_mut,
        )

    async def finalize_visual_reload_proof(
        self,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        """Fresh-session verify and finalize a visual-patched document.

        Visual callbacks commit their patch while remaining ``awaiting_visuals``.
        Only this method may promote that generation to ``ready`` after reloading
        the persisted document from a separate session and comparing canonical
        hashes for the current document revision.
        """
        from core.database.session import async_session_factory
        from generation.page_objects.document_assembly import (
            canonical_document_sha256,
            reload_document,
        )
        from contracts.lectio_page import validate_document

        async with async_session_factory() as fresh:
            generation = await fresh.get(GenerationModel, self.generation_id)
            if generation is None:
                raise KeyError(self.generation_id)
            reloaded = reload_document(generation.document_json or {})
            errors = validate_document(reloaded)
            if errors:
                raise DocumentFenceError(
                    f"fresh-session validation failed after visual patch: {errors[:5]}"
                )
            digest = canonical_document_sha256(reloaded)

        result: list[dict[str, Any]] = []

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            if str(generation.status or "") != "awaiting_visuals":
                raise VisualCompletionStateError(
                    f"visual reload finalization requires awaiting_visuals, got {generation.status!r}"
                )
            current_revision = int(state.get("document_revision") or 0)
            if current_revision != int(expected_revision):
                raise VisualCompletionConflict(
                    f"visual revision changed during reload: have {current_revision}, want {expected_revision}"
                )
            persisted = reload_document(generation.document_json or {})
            locked_digest = canonical_document_sha256(persisted)
            if locked_digest != digest:
                raise DocumentFenceError(
                    f"visual reload hash mismatch: fresh {digest!r}, locked {locked_digest!r}"
                )
            assert_legal_transition("awaiting_visuals", "ready")
            generation.status = "ready"
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["document_sha256"] = digest
            execution["reloaded_sha256"] = digest
            execution["reload_verified"] = True
            execution["heartbeat_at"] = _now()
            state["execution"] = execution
            # A successful replacement clears the active QC/retry warning;
            # visual_qc_history on the block remains the audit trail.
            clear_generation_error_state(generation, state)
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["document_sha256"] = digest
            execution["reloaded_sha256"] = digest
            execution["reload_verified"] = True
            execution["heartbeat_at"] = _now()
            state["execution"] = execution
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        "visual_document_ready",
                        generation_id=self.generation_id,
                        status="ready",
                        document_revision=current_revision,
                    ),
                    "at": _now(),
                }
            )
            state["events"] = events[-500:]
            result.append(
                {
                    "status": "ready",
                    "document_revision": current_revision,
                    "document_sha256": digest,
                    "reloaded_sha256": digest,
                    "reload_verified": True,
                }
            )

        await self.mutate_state(
            expected_statuses={"awaiting_visuals"},
            mutation=_mut,
        )
        return result[0]

    async def apply_visual_completion(
        self,
        *,
        request_id: str,
        asset: dict[str, Any],
        supplied_block_id: str | None = None,
        visual_qc: dict[str, Any] | None = None,
    ) -> VisualCompletionResult:
        """Atomically apply figure asset completion keyed by request_id."""
        from generation.page_objects.document_assembly import (
            persist_document_json,
            reload_document,
        )
        from generation.page_objects.visual_completion import apply_figure_asset_update

        box: list[VisualCompletionResult] = []
        verify_after_mutation = False
        verified_revision: list[int] = []

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            nonlocal verify_after_mutation
            current = str(generation.status or "")
            if current not in _VISUAL_CALLBACK_STATUSES:
                raise VisualCompletionStateError(
                    f"visual callback rejected in status {current!r}"
                )

            try:
                document = reload_document(generation.document_json or {})
            except Exception as exc:  # noqa: BLE001
                raise VisualRequestNotFound("Document not found") from exc

            block_execution = dict(state.get("block_execution") or {})
            target_block_id: str | None = None
            existing_asset: dict[str, Any] = {}
            for section in document.get("sections") or []:
                for block in section.get("blocks") or []:
                    if block.get("object") != "figure":
                        continue
                    block_asset = dict((block.get("content") or {}).get("asset") or {})
                    if str(block_asset.get("request_id") or "") != request_id:
                        continue
                    target_block_id = str(block.get("id") or "")
                    existing_asset = block_asset
                    break
                if target_block_id:
                    break

            if not target_block_id:
                # A restarted worker may reload a candidate envelope whose
                # figure asset lost request_id while block_execution retained
                # the authoritative mapping. Fence fallback by supplied block
                # id (or the matching execution outcome) and restore the id
                # during the atomic patch instead of dropping a successful
                # provider result.
                fallback_block_id = str(supplied_block_id or "")
                if not fallback_block_id:
                    for raw_outcome in block_execution.values():
                        if (
                            isinstance(raw_outcome, dict)
                            and str(raw_outcome.get("request_id") or "") == request_id
                        ):
                            fallback_block_id = str(raw_outcome.get("block_id") or "")
                            if fallback_block_id:
                                break
                if fallback_block_id:
                    for section in document.get("sections") or []:
                        for block in section.get("blocks") or []:
                            if (
                                block.get("object") == "figure"
                                and str(block.get("id") or "") == fallback_block_id
                            ):
                                candidate_asset = dict(
                                    (block.get("content") or {}).get("asset") or {}
                                )
                                if str(candidate_asset.get("request_id") or "") not in {
                                    "",
                                    request_id,
                                }:
                                    continue
                                target_block_id = fallback_block_id
                                existing_asset = candidate_asset
                                break
                        if target_block_id:
                            break
            if not target_block_id:
                raise VisualRequestNotFound(f"figure request_id {request_id!r} not found")

            if supplied_block_id and str(supplied_block_id) != target_block_id:
                raise VisualCompletionConflict(
                    f"block_id mismatch: supplied {supplied_block_id!r}, "
                    f"found {target_block_id!r} for request_id {request_id!r}"
                )

            matched_key = None
            for key, outcome in list(block_execution.items()):
                if not isinstance(outcome, dict):
                    continue
                if str(outcome.get("request_id") or "") == request_id:
                    matched_key = key
                    break
            if matched_key is None:
                raise VisualCompletionInvariantError(
                    f"no block_execution outcome for request_id {request_id!r}"
                )
            previous_outcome = dict(block_execution.get(matched_key) or {})
            previous_qc = previous_outcome.get("visual_qc")

            asset_payload = dict(asset)
            asset_payload["request_id"] = request_id
            for optional_key in ("src", "svg"):
                if asset_payload.get(optional_key) is None:
                    asset_payload.pop(optional_key, None)
            visual_qc_payload = dict(visual_qc) if visual_qc is not None else None
            if (
                isinstance(visual_qc_payload, dict)
                and str(visual_qc_payload.get("status") or "") == "flagged_quality"
                and str(asset_payload.get("status") or "") == "ready"
            ):
                # QC-flagged output is retryable, never a ready/hash proof.
                asset_payload["status"] = "failed"
            outcome_status = visual_outcome_status(
                str(asset_payload.get("status") or "")
            )

            already = (
                str(existing_asset.get("status") or "")
                == str(asset_payload.get("status") or "")
                and str(existing_asset.get("request_id") or "") == request_id
                and str(existing_asset.get("src") or "")
                == str(asset_payload.get("src") or "")
                and str(existing_asset.get("svg") or "")
                == str(asset_payload.get("svg") or "")
            )

            if current == "ready" and not already:
                raise VisualCompletionConflict(
                    "material asset replacement rejected on ready document"
                )

            revision = int(state.get("document_revision") or 0)
            if not already:
                document = apply_figure_asset_update(
                    document,
                    block_id=target_block_id,
                    asset=asset_payload,
                )
                generation.document_json = persist_document_json(
                    generation.document_json, document
                )
                revision += 1
                state["document_revision"] = revision

                outcome = previous_outcome
                content = dict(outcome.get("content") or {})
                content["asset"] = asset_payload
                history = [
                    item
                    for item in (outcome.get("visual_qc_history") or [])
                    if isinstance(item, dict)
                ]
                if isinstance(previous_qc, dict):
                    history.append({**previous_qc, "archived_at": _now()})
                outcome["visual_qc_history"] = history[-5:]
                if outcome_status == "ready":
                    # Keep an accepted QC verdict active on the current asset.
                    # History is the audit trail for superseded verdicts; the
                    # current field proves this ready asset passed its final gate.
                    if (
                        isinstance(visual_qc_payload, dict)
                        and str(visual_qc_payload.get("status") or "")
                        in {"accept", "accepted", "ready"}
                    ):
                        outcome["visual_qc"] = visual_qc_payload
                    else:
                        outcome.pop("visual_qc", None)
                    # A successful replacement/finalization clears the active
                    # retry error; the event and QC history remain the audit
                    # record of the earlier failed attempt.
                    outcome.pop("error", None)
                elif visual_qc_payload is not None:
                    outcome["visual_qc"] = visual_qc_payload
                block_execution[matched_key] = {
                    **outcome,
                    "status": outcome_status,
                    "request_id": request_id,
                    "block_id": target_block_id,
                    "content": content,
                }
                state["block_execution"] = block_execution
                execution = dict(state.get("execution") or empty_execution_meta())
                _invalidate_reload_proof(execution)
                state["execution"] = execution
            elif visual_qc_payload is not None:
                outcome = previous_outcome
                if outcome.get("visual_qc") != visual_qc_payload:
                    outcome["visual_qc"] = visual_qc_payload
                    block_execution[matched_key] = outcome
                    state["block_execution"] = block_execution
                if str(visual_qc_payload.get("status") or "") == "flagged_quality":
                    execution = dict(state.get("execution") or empty_execution_meta())
                    _invalidate_reload_proof(execution)
                    state["execution"] = execution

            unresolved = False
            for section in document.get("sections") or []:
                for block in section.get("blocks") or []:
                    if block.get("object") != "figure":
                        continue
                    status = str(
                        ((block.get("content") or {}).get("asset") or {}).get("status")
                        or ""
                    )
                    if status in _UNRESOLVED_ASSET_STATUSES:
                        unresolved = True
                        break
                if unresolved:
                    break

            terminal = current
            if current == "awaiting_visuals" and not unresolved:
                # Do not transition directly to ready: the patched document must
                # be reloaded in a fresh session and hashed before finalization.
                # Re-run the fresh-session fence even when the asset payload is
                # byte-for-byte idempotent. A prior callback may have persisted
                # the ready asset but failed during finalization; treating that
                # retry as a no-op would strand the generation in
                # `awaiting_visuals` forever.
                verify_after_mutation = True
                verified_revision.append(revision)

            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        "visual_callback",
                        generation_id=self.generation_id,
                        block_id=target_block_id,
                        status=str(asset_payload.get("status") or ""),
                        request_id=request_id,
                        idempotent=already,
                    ),
                    "at": _now(),
                }
            )
            state["events"] = events[-500:]
            box.append(
                VisualCompletionResult(
                    generation_id=self.generation_id,
                    block_id=target_block_id,
                    request_id=request_id,
                    status=terminal,
                    document_revision=revision,
                    idempotent=already,
                )
            )

        await self.mutate_state(mutation=_mut)
        result = box[0]
        if verify_after_mutation:
            verified = await self.finalize_visual_reload_proof(
                expected_revision=verified_revision[0],
            )
            return VisualCompletionResult(
                generation_id=result.generation_id,
                block_id=result.block_id,
                request_id=result.request_id,
                status=str(verified.get("status") or "ready"),
                document_revision=result.document_revision,
                idempotent=result.idempotent,
            )
        return result

    async def reopen_flagged_visuals(self) -> dict[str, Any]:
        """Reopen only a ready document carrying persisted QC-flagged visuals.

        This is intentionally narrower than a general ready retry: the persisted
        ``visual_qc.status=flagged_quality`` marker is the fence. Only affected
        figure assets are changed to failed/retryable, the document revision and
        reload proof are invalidated, and all upstream outcomes remain untouched.
        """
        from generation.page_objects.document_assembly import persist_document_json, reload_document
        from generation.page_objects.visual_completion import apply_figure_asset_update

        box: list[dict[str, Any]] = []

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            if str(generation.status or "") != "ready":
                raise VisualCompletionStateError(
                    f"flagged visual reopen requires ready, got {generation.status!r}"
                )
            block_execution = dict(state.get("block_execution") or {})
            flagged_ids: set[str] = set()
            for outcome in block_execution.values():
                if not isinstance(outcome, dict) or str(outcome.get("object") or "") != "figure":
                    continue
                qc = outcome.get("visual_qc")
                if not isinstance(qc, dict):
                    history = outcome.get("visual_qc_history")
                    if isinstance(history, list):
                        for candidate in reversed(history):
                            if isinstance(candidate, dict):
                                qc = candidate
                                break
                error = outcome.get("error")
                has_visual_error = isinstance(error, dict) and str(
                    error.get("code") or ""
                ) in {"VISUAL_DISPATCH", "VISUAL_COMPLETION"}
                if (
                    isinstance(qc, dict)
                    and str(qc.get("status") or "") == "flagged_quality"
                ) or has_visual_error:
                    request_id = str(outcome.get("request_id") or "")
                    if request_id:
                        flagged_ids.add(request_id)
            if not flagged_ids:
                raise VisualCompletionStateError(
                    "ready generation has no persisted flagged_quality visual"
                )

            document = reload_document(generation.document_json or {})
            touched_ids: list[str] = []
            for section in list(document.get("sections") or []):
                for block in list(section.get("blocks") or []):
                    if block.get("object") != "figure":
                        continue
                    content = dict(block.get("content") or {})
                    asset = dict(content.get("asset") or {})
                    request_id = str(asset.get("request_id") or "")
                    if request_id not in flagged_ids:
                        continue
                    failed_asset = {
                        "status": "failed",
                        "request_id": request_id,
                        "kind": str(asset.get("kind") or "image"),
                    }
                    if asset.get("src"):
                        failed_asset["src"] = asset["src"]
                    if asset.get("svg"):
                        failed_asset["svg"] = asset["svg"]
                    document = apply_figure_asset_update(
                        document, block_id=str(block.get("id") or ""), asset=failed_asset
                    )
                    touched_ids.append(request_id)
                    for key, outcome in list(block_execution.items()):
                        if not isinstance(outcome, dict) or str(outcome.get("request_id") or "") != request_id:
                            continue
                        updated = dict(outcome)
                        updated["status"] = "failed_recoverable"
                        updated_content = dict(updated.get("content") or {})
                        updated_content["asset"] = failed_asset
                        updated["content"] = updated_content
                        block_execution[key] = updated
            if not touched_ids:
                raise VisualCompletionStateError(
                    "persisted flagged visual request is missing from document"
                )

            assert_legal_transition("ready", "awaiting_visuals")
            generation.status = "awaiting_visuals"
            generation.document_json = persist_document_json(generation.document_json, document)
            state["document_revision"] = int(state.get("document_revision") or 0) + 1
            state["block_execution"] = block_execution
            execution = dict(state.get("execution") or empty_execution_meta())
            _invalidate_reload_proof(execution)
            execution["last_error"] = {
                "type": "VisualQualityFlagged",
                "code": "VISUAL_QUALITY_FLAGGED",
                "message": "Visual quality review flagged one or more images; retry visuals.",
                "stage": "awaiting_visuals",
                "retryable": True,
                "repairable": True,
                "request_ids": sorted(touched_ids),
                "recorded_at": _now(),
            }
            state["execution"] = execution
            apply_generation_error_aliases(generation, execution["last_error"])
            events = list(state.get("events") or [])
            events.append({
                **make_event(
                    "flagged_visuals_reopened",
                    generation_id=self.generation_id,
                    status="awaiting_visuals",
                    request_ids=sorted(touched_ids),
                    document_revision=state["document_revision"],
                ),
                "at": _now(),
            })
            state["events"] = events[-500:]
            box.append({
                "generation_id": self.generation_id,
                "status": "awaiting_visuals",
                "request_ids": sorted(touched_ids),
                "document_revision": state["document_revision"],
            })

        await self.mutate_state(expected_statuses={"ready"}, mutation=_mut)
        return box[0]

    async def persist_visual_dispatch_failure(
        self,
        *,
        exc: BaseException | None = None,
        message: str | None = None,
        failed_request_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Record a retryable visual failure while remaining in awaiting_visuals.

        Does not transition to failed_recoverable (which would requeue writers).
        Marks unresolved figure assets as failed when request ids are provided or
        when no ids are given (mark all unresolved pending/generating figures).
        """
        from generation.page_objects.document_assembly import (
            persist_document_json,
            reload_document,
        )
        from generation.page_objects.visual_completion import apply_figure_asset_update
        from planning.whole_lesson.failure_policy import structured_error_from_exc

        error_message = (message or (str(exc).strip() if exc else "") or "visual dispatch failed")[
            :500
        ]
        if exc is not None:
            error = structured_error_from_exc(
                exc=exc,
                stage="visual_generation",
                attempt=1,
            )
            error["retryable"] = True
            error["stage"] = "awaiting_visuals"
            error["code"] = str(error.get("code") or "VISUAL_DISPATCH")
            error["message"] = error_message
        else:
            error = {
                "type": "VisualDispatchError",
                "code": "VISUAL_DISPATCH",
                "message": error_message,
                "stage": "awaiting_visuals",
                "retryable": True,
                "repairable": False,
                "recorded_at": _now(),
            }

        target_ids = {str(rid) for rid in (failed_request_ids or []) if rid}

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            current = str(generation.status or "")
            if current != "awaiting_visuals":
                raise IllegalTransitionError(
                    f"visual dispatch failure requires awaiting_visuals, got {current!r}"
                )

            try:
                document = reload_document(generation.document_json or {})
            except Exception:  # noqa: BLE001
                document = {}

            revision = int(state.get("document_revision") or 0)
            block_execution = dict(state.get("block_execution") or {})
            touched = False

            for section in list(document.get("sections") or []):
                for block in list(section.get("blocks") or []):
                    if block.get("object") != "figure":
                        continue
                    content = dict(block.get("content") or {})
                    asset = dict(content.get("asset") or {})
                    request_id = str(asset.get("request_id") or "")
                    asset_status = str(asset.get("status") or "pending")
                    if asset_status not in {"pending", "generating", "failed", ""}:
                        continue
                    if target_ids and request_id not in target_ids:
                        continue
                    if not request_id:
                        continue
                    failed_asset = {
                        "status": "failed",
                        "request_id": request_id,
                        "kind": str(asset.get("kind") or "image"),
                    }
                    if asset.get("src"):
                        failed_asset["src"] = asset.get("src")
                    if asset.get("svg"):
                        failed_asset["svg"] = asset.get("svg")
                    document = apply_figure_asset_update(
                        document,
                        block_id=str(block.get("id") or ""),
                        asset=failed_asset,
                    )
                    touched = True
                    for key, outcome in list(block_execution.items()):
                        if not isinstance(outcome, dict):
                            continue
                        if str(outcome.get("request_id") or "") != request_id:
                            continue
                        outcome_content = dict(outcome.get("content") or {})
                        outcome_content["asset"] = failed_asset
                        block_execution[key] = {
                            **outcome,
                            "status": "failed_recoverable",
                            "content": outcome_content,
                            "error": error,
                        }

            if touched:
                generation.document_json = persist_document_json(
                    generation.document_json, document
                )
                revision += 1
                state["document_revision"] = revision
                state["block_execution"] = block_execution

            # Stay in awaiting_visuals — never requeue writers via failed_recoverable.
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["last_error"] = error
            execution["heartbeat_at"] = _now()
            # A failed/retried visual mutation invalidates any proof for the
            # previous document revision, even when the asset was already marked
            # failed by a prior callback.
            _invalidate_reload_proof(execution)
            state["execution"] = execution
            apply_generation_error_aliases(generation, error)
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        "visual_dispatch_failed",
                        generation_id=self.generation_id,
                        status="awaiting_visuals",
                        request_ids=sorted(target_ids) if target_ids else None,
                    ),
                    "at": _now(),
                    "error": error,
                }
            )
            state["events"] = events[-500:]

        return await self.mutate_state(
            expected_statuses={"awaiting_visuals"},
            mutation=_mut,
        )

    async def clear_visual_last_error(self) -> dict[str, Any]:
        """Clear execution.last_error after a successful visuals-only redispath."""

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("execution") or empty_execution_meta())
            last = execution.get("last_error")
            if isinstance(last, dict) and str(last.get("stage") or "") in {
                "awaiting_visuals",
                "visual_generation",
            }:
                clear_generation_error_state(generation, state)
            else:
                state["execution"] = execution

        return await self.mutate_state(
            expected_statuses={"awaiting_visuals", "ready"},
            mutation=_mut,
        )


async def claim_next_native_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> ExecutionLease | None:
    """Claim oldest pre-worker retry or post-approval native job."""
    pre_result = await session.execute(
        select(GenerationModel.id)
        .where(GenerationModel.status.in_(sorted(PRE_WORKER_RETRY_STATUSES)))
        .order_by(GenerationModel.created_at.asc())
        .limit(20)
    )
    for generation_id in list(pre_result.scalars().all()):
        repo = PageDocumentRepository(session, str(generation_id))
        state = await repo.load_page_generation_state()
        work_kind = (state.get("execution") or {}).get("work_kind")
        if work_kind not in PRE_WORKER_WORK_KINDS:
            continue
        lease = await repo.claim_pre_worker_retry(
            worker_id=worker_id, lease_seconds=lease_seconds
        )
        if lease is not None:
            return lease

    result = await session.execute(
        select(GenerationModel.id)
        .where(
            GenerationModel.status.in_(
                sorted(CLAIMABLE_STATUSES | ACTIVE_STATUSES)
            )
        )
        .order_by(GenerationModel.created_at.asc())
        .limit(20)
    )
    for generation_id in list(result.scalars().all()):
        gid = str(generation_id)
        repo = PageDocumentRepository(session, gid)
        state = await repo.load_page_generation_state()
        if not state.get("teaching_plan") or not state.get("lesson_packet"):
            continue
        # Refuse pre-teaching / unapproved checkpoints — worker must not steal them.
        review = state.get("teaching_review") if isinstance(state.get("teaching_review"), dict) else {}
        review_status = str((review or {}).get("status") or "")
        generation = await session.get(GenerationModel, gid)
        if generation is None:
            continue
        generation_status = str(generation.status or "")
        if generation_status in CLAIMABLE_STATUSES | ACTIVE_STATUSES:
            if review_status and review_status not in {"approved", "queued"}:
                # Legacy paths may omit review; require approved when present.
                if review_status in {"pending", "rejected"}:
                    continue
            if generation_status == "awaiting_teaching_approval":
                continue
        lease = await repo.claim_execution(worker_id=worker_id, lease_seconds=lease_seconds)
        if lease is not None:
            return lease
    return None


async def persist_native_failure_for_generation(
    generation_id: str,
    *,
    exc: BaseException,
    stage: str,
    event: str = "pre_worker_failure",
    attempt: int = 1,
) -> dict[str, Any]:
    """Session-scoped helper for pre-worker native failure sync (items/teaching)."""
    from core.database.session import async_session_factory

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        return await repo.persist_native_failure(
            exc=exc,
            stage=stage,
            event=event,
            attempt=attempt,
        )
