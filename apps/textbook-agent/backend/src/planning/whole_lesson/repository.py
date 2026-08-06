"""Persist whole-lesson planning artifacts in GenerationModel.chunked_state_json."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel
from planning.whole_lesson.events import make_event
from planning.whole_lesson.states import (
    ACTIVE_STATUSES,
    CLAIMABLE_STATUSES,
    DEFAULT_LEASE_SECONDS,
    IllegalTransitionError,
    assert_legal_transition,
    execution_key,
)
from v3_blueprint.planning.persistence import load_chunked_state, persist_chunked_state

PAGE_DOCUMENT_KEY = "page_document_v2"
_PAGE_STATE_LOCKS: dict[str, asyncio.Lock] = {}


def _page_state_lock(generation_id: str) -> asyncio.Lock:
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


def empty_execution_meta() -> dict[str, Any]:
    return {
        "worker_id": None,
        "attempt": 0,
        "claimed_at": None,
        "heartbeat_at": None,
        "lease_seconds": DEFAULT_LEASE_SECONDS,
        "last_error": None,
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


class PageDocumentRepository:
    def __init__(self, session: AsyncSession, generation_id: str) -> None:
        self.session = session
        self.generation_id = generation_id

    async def _load_generation(self) -> GenerationModel:
        generation = await self.session.get(GenerationModel, self.generation_id)
        if generation is None:
            raise KeyError(f"generation {self.generation_id!r} not found")
        return generation

    async def load_page_generation_state(self) -> dict[str, Any]:
        chunked = await load_chunked_state(self.generation_id, self.session)
        state = chunked.get(PAGE_DOCUMENT_KEY)
        if not isinstance(state, dict):
            state = empty_page_document_state()
        else:
            state = deepcopy(state)
        if not isinstance(state.get("execution"), dict):
            state["execution"] = empty_execution_meta()
        if not isinstance(state.get("block_execution"), dict):
            state["block_execution"] = {}
        return state

    async def _save(self, state: dict[str, Any], *, stage: str | None = None) -> dict[str, Any]:
        state = deepcopy(state)
        state["last_heartbeat"] = _now()
        patch: dict[str, Any] = {PAGE_DOCUMENT_KEY: state}
        if stage is not None:
            patch["stage"] = stage
        await persist_chunked_state(self.generation_id, patch, self.session)
        await self.session.commit()
        return state

    async def transition(
        self,
        *,
        expected: set[str],
        target: str,
        event: str,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        generation = await self._load_generation()
        current = str(generation.status or "")
        if current not in expected:
            raise IllegalTransitionError(
                f"expected status in {sorted(expected)}, got {current!r}"
            )
        assert_legal_transition(current, target)
        state = await self.load_page_generation_state()
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
        return await self._save(state, stage=target)

    async def claim_execution(self, *, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
        from sqlalchemy import update

        generation = await self._load_generation()
        status = str(generation.status or "")
        state = await self.load_page_generation_state()
        execution = dict(state.get("execution") or empty_execution_meta())
        now = datetime.now(timezone.utc)
        heartbeat = _parse_iso(execution.get("heartbeat_at"))
        lease = int(execution.get("lease_seconds") or lease_seconds)
        stale = heartbeat is None or heartbeat + timedelta(seconds=lease) < now

        if status in CLAIMABLE_STATUSES:
            if status == "failed_recoverable":
                assert_legal_transition("failed_recoverable", "queued")
                step = await self.session.execute(
                    update(GenerationModel)
                    .where(GenerationModel.id == self.generation_id)
                    .where(GenerationModel.status == "failed_recoverable")
                    .values(status="queued")
                )
                if step.rowcount != 1:
                    await self.session.rollback()
                    return False
                status = "queued"
            assert_legal_transition(status, "planning_forms")
            result = await self.session.execute(
                update(GenerationModel)
                .where(GenerationModel.id == self.generation_id)
                .where(GenerationModel.status == "queued")
                .values(status="planning_forms")
            )
            if result.rowcount != 1:
                await self.session.rollback()
                return False
            await self.session.refresh(generation)
            target_stage = "planning_forms"
            event_name = "execution_claimed"
        elif status in ACTIVE_STATUSES and stale:
            # Reclaim stale active work without changing stage.
            # Guard: only if still same status (another worker may have finished).
            result = await self.session.execute(
                update(GenerationModel)
                .where(GenerationModel.id == self.generation_id)
                .where(GenerationModel.status == status)
                .values(status=status)
            )
            if result.rowcount != 1:
                await self.session.rollback()
                return False
            # Also require lease still stale after reload of execution meta.
            if not stale:
                return False
            target_stage = status
            event_name = "execution_reclaimed"
        else:
            return False

        execution["worker_id"] = worker_id
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
                ),
                "at": _now(),
            }
        )
        state["events"] = events[-500:]
        await self._save(state, stage=target_stage)
        return True

    async def heartbeat(self, *, worker_id: str) -> None:
        state = await self.load_page_generation_state()
        execution = dict(state.get("execution") or empty_execution_meta())
        if execution.get("worker_id") != worker_id:
            raise PermissionError("heartbeat rejected: worker does not own lease")
        execution["heartbeat_at"] = _now()
        state["execution"] = execution
        await self._save(state)

    async def release_execution(self, *, worker_id: str) -> None:
        state = await self.load_page_generation_state()
        execution = dict(state.get("execution") or empty_execution_meta())
        if execution.get("worker_id") not in {None, worker_id}:
            raise PermissionError("release rejected: worker does not own lease")
        execution["worker_id"] = None
        execution["claimed_at"] = None
        state["execution"] = execution
        await self._save(state)

    async def load_block_results(self) -> dict[str, dict[str, Any]]:
        state = await self.load_page_generation_state()
        raw = state.get("block_execution") or {}
        return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}

    async def save_block_outcome(self, key: str, outcome: dict[str, Any]) -> dict[str, Any]:
        # Serialize merges so concurrent writers cannot clobber sibling outcomes.
        async with _page_state_lock(self.generation_id):
            state = await self.load_page_generation_state()
            execution = dict(state.get("block_execution") or {})
            previous = dict(execution.get(key) or {})
            merged = {**previous, **outcome, "updated_at": _now()}
            if "created_at" not in merged:
                merged["created_at"] = previous.get("created_at") or _now()
            execution[key] = merged
            state["block_execution"] = execution
            return await self._save(state)

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
        state = await self.load_page_generation_state()
        state["lesson_packet"] = packet
        return await self._save(state)

    async def save_catalogue_meta(
        self,
        *,
        version: str,
        teaching_projection_hash: str | None = None,
        form_projection_hash: str | None = None,
    ) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        catalogue = dict(state.get("catalogue") or {})
        catalogue["version"] = version
        if teaching_projection_hash is not None:
            catalogue["teaching_projection_hash"] = teaching_projection_hash
        if form_projection_hash is not None:
            catalogue["form_projection_hash"] = form_projection_hash
        state["catalogue"] = catalogue
        return await self._save(state)

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
        state = await self.load_page_generation_state()
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
        generation = await self._load_generation()
        generation.status = "awaiting_teaching_approval"
        return await self._save(state, stage=stage)

    async def save_teaching_review(
        self,
        *,
        status: str,
        expected_revision: int,
        reviewed_by: str | None = None,
        teacher_note: str | None = None,
        queue: bool = False,
    ) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        review = dict(state.get("teaching_review") or {})
        current_rev = int(review.get("revision") or 1)
        if expected_revision != current_rev:
            raise ValueError(
                f"stale teaching revision: expected {expected_revision}, current {current_rev}"
            )
        generation = await self._load_generation()
        gen_status = str(generation.status or "")
        post_approval = {
            "queued",
            "planning_forms",
            "writing_blocks",
            "assembling",
            "awaiting_visuals",
            "ready",
            "completed",
        }
        if status == "approved" and queue and gen_status in post_approval:
            # Idempotent re-approve: do not bump revision or re-queue.
            return state
        review["status"] = status
        review["reviewed_by"] = reviewed_by
        review["reviewed_at"] = _now()
        review["teacher_note"] = teacher_note
        if status == "approved":
            review["revision"] = current_rev + 1
        state["teaching_review"] = review
        if status == "approved" and queue:
            await self._save(state)
            return await self.transition(
                expected={"awaiting_teaching_approval"},
                target="queued",
                event="teaching_plan_approved",
            )
        stage = "planning_forms" if status == "approved" else "rejected_by_teacher"
        generation.status = stage
        return await self._save(state, stage=stage)

    async def save_form_plan(
        self,
        *,
        plan: dict[str, Any],
        validation: dict[str, Any],
        qc: list[dict[str, Any]],
        prompt: str | None = None,
        raw: str | None = None,
    ) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        state["form_plan"] = plan
        state["form_validation"] = validation
        state["form_qc"] = qc
        if prompt is not None:
            state["form_prompt"] = prompt
        if raw is not None:
            state["form_raw"] = raw
        return await self._save(state, stage="writing_blocks")

    async def save_block_result(self, block_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Legacy helper: store under bare block_id (prefer save_block_outcome)."""
        return await self.save_block_outcome(block_id, result)

    async def save_qc_report(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        state["advisory_qc"] = findings
        return await self._save(state)

    async def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        async with _page_state_lock(self.generation_id):
            state = await self.load_page_generation_state()
            events = list(state.get("events") or [])
            events.append({**event, "at": _now()})
            state["events"] = events[-500:]
            return await self._save(state)

    async def bump_document_revision(self) -> int:
        state = await self.load_page_generation_state()
        revision = int(state.get("document_revision") or 0) + 1
        state["document_revision"] = revision
        await self._save(state)
        return revision


async def claim_next_native_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> str | None:
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
        claimed = await repo.claim_execution(worker_id=worker_id, lease_seconds=lease_seconds)
        if claimed:
            return generation.id
    return None
