"""Persist whole-lesson planning artifacts in GenerationModel.chunked_state_json."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

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
    LeaseLostError,
    assert_legal_transition,
    execution_key,
)

PAGE_DOCUMENT_KEY = "page_document_v2"
_PAGE_STATE_LOCKS: dict[str, asyncio.Lock] = {}
_PAGE_STATE_LOCK_GUARD = asyncio.Lock()


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


def empty_execution_meta() -> dict[str, Any]:
    return {
        "worker_id": None,
        "lease_token": 0,
        "attempt": 0,
        "claimed_at": None,
        "heartbeat_at": None,
        "lease_seconds": DEFAULT_LEASE_SECONDS,
        "last_error": None,
        "document_sha256": None,
        "reloaded_sha256": None,
        "reload_verified": False,
    }


def empty_page_document_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "lesson_packet": None,
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
        return state

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
            elif target in {"ready", "queued", "planning_forms"}:
                execution["last_error"] = None
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
                if status == "failed_recoverable":
                    assert_legal_transition("failed_recoverable", "queued")
                    generation.status = "queued"
                    status = "queued"
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
            for block in section.get("blocks") or []:
                if not isinstance(block, dict):
                    continue
                block_id = str(block.get("id") or "")
                key = execution_key(section_id, block_id, variant_id)
                expected[key] = stored.get(key) or {}
        return expected

    async def save_lesson_packet(self, packet: dict[str, Any]) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            state["lesson_packet"] = packet

        return await self.mutate_state(mutation=_mut)

    async def save_catalogue_meta(
        self,
        *,
        version: str,
        teaching_projection_hash: str | None = None,
        form_projection_hash: str | None = None,
    ) -> dict[str, Any]:
        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            catalogue = dict(state.get("catalogue") or {})
            catalogue["version"] = version
            if teaching_projection_hash is not None:
                catalogue["teaching_projection_hash"] = teaching_projection_hash
            if form_projection_hash is not None:
                catalogue["form_projection_hash"] = form_projection_hash
            state["catalogue"] = catalogue

        return await self.mutate_state(mutation=_mut)

    async def save_teaching_plan(
        self,
        *,
        plan: dict[str, Any],
        validation: dict[str, Any],
        qc: list[dict[str, Any]],
        prompt: str | None = None,
        raw: str | None = None,
        stage: str = "awaiting_teaching_approval",
    ) -> dict[str, Any]:
        """Initialize teaching-plan artifacts and enter awaiting_teaching_approval.

        Direct status assignment is allowed only for this pre-state-machine init.
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
            generation.status = stage

        return await self.mutate_state(mutation=_mut)

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
                execution = dict(state.get("execution") or empty_execution_meta())
                execution["heartbeat_at"] = _now()
                execution["last_error"] = None
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


async def claim_next_native_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> ExecutionLease | None:
    """Atomically claim the oldest queued/stale native generation."""
    result = await session.execute(
        select(GenerationModel)
        .where(
            GenerationModel.status.in_(
                sorted(CLAIMABLE_STATUSES | ACTIVE_STATUSES)
            )
        )
        .order_by(GenerationModel.created_at.asc())
        .limit(20)
    )
    candidates = list(result.scalars().all())
    for generation in candidates:
        repo = PageDocumentRepository(session, generation.id)
        state = await repo.load_page_generation_state()
        if not state.get("teaching_plan") or not state.get("lesson_packet"):
            continue
        lease = await repo.claim_execution(worker_id=worker_id, lease_seconds=lease_seconds)
        if lease is not None:
            return lease
    return None
