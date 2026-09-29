"""Persist whole-lesson planning artifacts in GenerationModel.chunked_state_json."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel
from print.generation.whole_lesson.events import make_event
from print.generation.whole_lesson.states import (
    ACTIVE_STATUSES,
    DEFAULT_LEASE_SECONDS,
    LEGAL_TRANSITIONS,
    PRE_WORKER_RETRY_STATUSES,
    WORK_KIND_POST_APPROVAL,
    IllegalTransitionError,
    LeaseLostError,
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
    return datetime.now(UTC).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
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

    async def mutate_state(
        self,
        *,
        expected_statuses: set[str] | None = None,
        worker_id: str | None = None,
        lease_token: int | None = None,
        commit: bool = True,
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
            if commit:
                await self.session.commit()
            else:
                await self.session.flush()
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

    async def write_shared_document_output(
        self,
        document: dict[str, Any],
        *,
        document_sha256: str,
    ) -> dict[str, Any]:
        """Option D (4A): lease-free, idempotent write of the realized Print document.

        The RealizationWorker holds the shared-runtime work-item lease; this
        only persists the deterministic SharedLessonDocument lowering and
        marks the output generation ``ready`` with its hash proof.  It flushes
        (``commit=False``): the worker commits together with the work-item and
        Run completion so the output and its Run can never disagree.
        """
        from print.rendering.page_objects.document_assembly import persist_document_json

        def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
            generation.document_json = persist_document_json(generation.document_json, document)
            generation.status = "ready"
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["candidate_document_sha256"] = document_sha256
            execution["candidate_written_at"] = _now()
            execution["document_sha256"] = document_sha256
            execution["reloaded_sha256"] = document_sha256
            execution["reload_verified"] = True
            execution["heartbeat_at"] = _now()
            state["execution"] = execution
            state["document_revision"] = int(state.get("document_revision") or 0) + 1
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        "document_ready",
                        generation_id=self.generation_id,
                        status="ready",
                    ),
                    "at": _now(),
                }
            )
            state["events"] = events[-500:]

        return await self.mutate_state(commit=False, mutation=_mut)

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
        from print.generation.whole_lesson.legality import (
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
        except Exception as exc:
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
            from curriculum.teaching_plan.revisions import TeachingRevisionStore

            state["teaching_plan"] = plan
            state["teaching_validation"] = validation
            state["teaching_qc"] = qc
            if prompt is not None:
                state["teaching_prompt"] = prompt
            if raw is not None:
                state["teaching_raw"] = raw
            preparation_hash = str(
                (state.get("lesson_packet") or {}).get("preparation_hash")
                or (state.get("catalogue") or {}).get("teaching_projection_hash")
                or "unhashed"
            )
            store = TeachingRevisionStore(state)
            store.record_draft(plan, preparation_hash=preparation_hash)
            review = dict(state.get("teaching_review") or {})
            review["status"] = "pending"
            review.setdefault("revision", int(review.get("revision") or 1))
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
        expected_content_hash: str | None = None,
        reviewed_by: str | None = None,
        teacher_note: str | None = None,
        queue: bool = False,
        allow_retry_from_failure: bool = False,
        commit: bool = True,
    ) -> dict[str, Any]:
        # writing_sections/writing_blocks are unreachable for a new row (P12B
        # removed the only transitions into them); kept here purely so a
        # re-approval request against a legacy row already parked there is
        # still recognized as "already past approval" instead of raising.
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
            from curriculum.teaching_plan.consumers import accept_approved_teaching_revision
            from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
            from curriculum.teaching_plan.revisions import (
                TeachingRevisionConflictError,
                TeachingRevisionStore,
            )

            review = dict(state.get("teaching_review") or {})
            current_rev = int(review.get("revision") or 1)
            approved_rev = review.get("approved_revision")
            already_approved = (
                str(review.get("status") or "") == "approved" and approved_rev is not None
            )
            if status == "approved" and queue and already_approved:
                if expected_revision != current_rev:
                    raise TeachingRevisionConflictError(
                        f"stale teaching revision: expected {expected_revision}, current {current_rev}"
                    )
                approved_plan = accept_approved_teaching_revision(
                    deepcopy(state), consumer="print"
                )
                actual_hash = teaching_plan_content_hash(approved_plan)
                if expected_content_hash is not None and expected_content_hash != actual_hash:
                    raise TeachingRevisionConflictError(
                        "displayed Teaching Plan content changed; reload the review before queuing"
                    )
            # After Learn (or a prior Print) approval, review.revision is the
            # next pending slot, not the approved teaching revision. Queuing
            # Print must not require a new draft.
            if status == "approved" and queue and already_approved:
                pass
            elif expected_revision != current_rev:
                raise TeachingRevisionConflictError(
                    f"stale teaching revision: expected {expected_revision}, current {current_rev}"
                )
            gen_status = str(generation.status or "")
            if status == "approved" and queue and gen_status in post_approval:
                boxed.append(state)
                return
            if (
                status == "approved"
                and queue
                and allow_retry_from_failure
                and already_approved
                and gen_status in {"failed_recoverable", "failed_terminal"}
            ):
                # A path realization may fail after the shared Teaching Plan
                # was approved. Reopen only the explicitly requested Print
                # worker from that immutable approval; Learn output and plan
                # revision remain untouched.
                generation.status = "queued"
                state["stage"] = "queued"
                prior_error = dict((state.get("execution") or {}).get("last_error") or {})
                clear_generation_error_state(generation, state)
                execution = dict(state.get("execution") or empty_execution_meta())
                execution["heartbeat_at"] = _now()
                execution["work_kind"] = WORK_KIND_POST_APPROVAL
                state["execution"] = execution
                block_execution = dict(state.get("block_execution") or {})
                # A whole-document assembly failure can leave individually
                # ready-looking block outputs that are no longer trustworthy
                # (for example, an answer entry that violates the assembled
                # choices contract).  Clear that stale snapshot on an
                # explicit retry so the corrected writers rerun from the same
                # immutable Teaching Plan.  Ordinary block/visual failures
                # retain successful siblings and reopen only failed blocks.
                if str(prior_error.get("type") or "") == "DocumentAssemblyError":
                    state["block_execution"] = {}
                else:
                    state["block_execution"] = {
                        key: value
                        for key, value in block_execution.items()
                        if str((value or {}).get("status") or "")
                        not in {"failed", "failed_recoverable", "failed_terminal"}
                    }
                events = list(state.get("events") or [])
                events.append(
                    {
                        **make_event(
                            "print_realization_retry_queued",
                            generation_id=self.generation_id,
                            status="queued",
                        ),
                        "at": _now(),
                    }
                )
                state["events"] = events[-500:]
                boxed.append(state)
                return
            if status == "approved" and not (queue and already_approved):
                store = TeachingRevisionStore(state)
                store.approve(
                    expected_revision=expected_revision,
                    expected_content_hash=expected_content_hash,
                    reviewed_by=reviewed_by,
                    teacher_note=teacher_note,
                )
            else:
                review["status"] = status
                review["reviewed_by"] = reviewed_by
                review["reviewed_at"] = _now()
                review["teacher_note"] = teacher_note
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
                # Learn (and other non-Print) approval: persist the teaching
                # revision without queuing the Print whole-lesson worker.
                events = list(state.get("events") or [])
                events.append(
                    {
                        **make_event(
                            "teaching_plan_approved",
                            generation_id=self.generation_id,
                            status="teaching_approved",
                        ),
                        "at": _now(),
                    }
                )
                state["events"] = events[-500:]
            boxed.append(state)

        await self.mutate_state(mutation=_mut, commit=commit)
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
        from print.rendering.page_objects.document_assembly import persist_document_json

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
        from print.contracts.lectio_page import validate_document
        from print.rendering.page_objects.document_assembly import (
            canonical_document_sha256,
            reload_document,
        )

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
        from print.rendering.page_objects.document_assembly import (
            persist_document_json,
            reload_document,
        )
        from print.rendering.page_objects.visual_completion import apply_figure_asset_update

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
            except Exception as exc:
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
            # Quality flags are advisory after a concrete asset has been
            # rendered. Keep the image ready and preserve the QC verdict for a
            # future replacement flow; only missing/broken assets are failed.
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
                    # Preserve every QC verdict on the asset, including an
                    # advisory flag/reject and its trace/reasons. The current
                    # field is the verdict for this exact source; history is
                    # retained for superseded sources and future replacement.
                    if isinstance(visual_qc_payload, dict):
                        outcome["visual_qc"] = visual_qc_payload
                    else:
                        outcome.pop("visual_qc", None)
                    # A successful delivery clears the active retry error; QC
                    # warnings remain durable metadata, not delivery failures.
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
