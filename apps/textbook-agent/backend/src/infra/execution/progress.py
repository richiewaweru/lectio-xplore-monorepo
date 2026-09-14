"""Durable run progress, ordered events, and model-call traces (P04 G16–G18).

Process-local ledger keyed by run_id (typically a realization_id). Callers
mirror authoritative DB fields into the store so GET status agrees with the
realization row. Event retention supports reconnect replay and snapshot
recovery when the requested sequence falls outside the retained window.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)

DEFAULT_EVENT_RETENTION = 200

SECRET_KEY_FRAGMENTS: frozenset[str] = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "cookie",
        "bearer",
        "raw_learner",
        "learner_response",
    }
)

ReplayMode = Literal["replay", "snapshot"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def prompt_hash_for(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact_secrets(value: Any) -> Any:
    """Recursively redact secret-looking keys; never raise."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for raw_key, raw_val in value.items():
            key = str(raw_key)
            lowered = key.casefold()
            if any(frag in lowered for frag in SECRET_KEY_FRAGMENTS):
                out[key] = "***"
            else:
                out[key] = redact_secrets(raw_val)
        return out
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class RunEvent:
    seq: int
    event_type: str
    at: datetime
    run_id: str
    path: str | None = None
    stage: str | None = None
    item_id: str | None = None
    attempt: int | None = None
    error_category: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "event_type": self.event_type,
            "at": self.at.isoformat(),
            "run_id": self.run_id,
            "path": self.path,
            "stage": self.stage,
            "item_id": self.item_id,
            "attempt": self.attempt,
            "error_category": self.error_category,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class ModelCallTrace:
    """One actual provider dispatch. Unknown usage stays None (never coerced to 0)."""

    run_id: str
    path: str
    stage: str
    item_id: str
    attempt: int
    model: str | None
    prompt_hash: str | None
    policy_hash: str | None = None
    composition_mode: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    provider_request_id: str | None = None
    at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "path": self.path,
            "stage": self.stage,
            "item_id": self.item_id,
            "attempt": self.attempt,
            "model": self.model,
            "prompt_hash": self.prompt_hash,
            "policy_hash": self.policy_hash,
            "composition_mode": self.composition_mode,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "provider_request_id": self.provider_request_id,
            "at": self.at.isoformat(),
            "usage_known": self.tokens_in is not None or self.tokens_out is not None,
        }


@dataclass(frozen=True, slots=True)
class ActiveItem:
    item_id: str
    stage: str
    attempt: int
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "stage": self.stage,
            "attempt": self.attempt,
            "state": self.state,
        }


@dataclass(frozen=True, slots=True)
class RetryScheduleEntry:
    item_id: str
    attempt: int
    next_retry_at: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "attempt": self.attempt,
            "next_retry_at": self.next_retry_at,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RunStatusView:
    run_id: str
    path: str
    status: str
    stage: str
    active_items: list[ActiveItem]
    completed: int
    total: int
    retry_schedule: list[RetryScheduleEntry]
    allowed_actions: list[str]
    revisions: dict[str, int]
    latest_seq: int
    owner_user_id: str
    links: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "path": self.path,
            "status": self.status,
            "stage": self.stage,
            "active_items": [item.to_dict() for item in self.active_items],
            "completed": self.completed,
            "total": self.total,
            "retry_schedule": [entry.to_dict() for entry in self.retry_schedule],
            "allowed_actions": list(self.allowed_actions),
            "revisions": dict(self.revisions),
            "latest_seq": self.latest_seq,
            "links": dict(self.links),
        }


@dataclass(frozen=True, slots=True)
class ReplayResult:
    mode: ReplayMode
    events: list[RunEvent]
    snapshot: dict[str, Any] | None
    oldest_retained_seq: int
    latest_seq: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "events": [event.to_dict() for event in self.events],
            "snapshot": self.snapshot,
            "oldest_retained_seq": self.oldest_retained_seq,
            "latest_seq": self.latest_seq,
        }


class TraceExporter(Protocol):
    def export(self, traces: list[ModelCallTrace]) -> None: ...


def allowed_actions_for(*, path: str, status: str, stage: str) -> list[str]:
    """Derive UI-safe actions from authoritative run status (server owns transitions)."""
    _ = path
    actions: list[str] = ["refresh"]
    normalized = status.casefold()
    stage_cf = stage.casefold()
    if normalized in {"failed", "failed_recoverable"} or stage_cf in {
        "failed",
        "failed_recoverable",
        "native_learn_error",
        "assembly_blocked",
        "stage2_error",
    }:
        actions.append("retry")
    if normalized in {"queued", "running", "writing", "selecting"}:
        actions.append("cancel")
    if normalized in {"ready", "published", "editing", "completed"}:
        actions.append("open")
    if normalized == "stale":
        actions.append("regenerate")
    if normalized == "read_only":
        actions.append("regenerate")
    return actions


@dataclass
class _RunRecord:
    run_id: str
    path: str
    owner_user_id: str
    status: str = "queued"
    stage: str = "queued"
    realization_revision: int = 1
    teaching_plan_revision: int = 1
    document_revision: int = 0
    completed: int = 0
    total: int = 0
    active: dict[str, ActiveItem] = field(default_factory=dict)
    retries: dict[str, RetryScheduleEntry] = field(default_factory=dict)
    events: list[RunEvent] = field(default_factory=list)
    traces: list[ModelCallTrace] = field(default_factory=list)
    next_seq: int = 1


class ProgressStore:
    """Durable progress ledger for realization/run observability."""

    def __init__(self, *, event_retention: int = DEFAULT_EVENT_RETENTION) -> None:
        self.event_retention = max(1, int(event_retention))
        self._lock = threading.Lock()
        self._runs: dict[str, _RunRecord] = {}

    def ensure_run(
        self,
        run_id: str,
        *,
        path: str,
        owner_user_id: str,
        status: str = "queued",
        stage: str | None = None,
        realization_revision: int = 1,
        teaching_plan_revision: int = 1,
        document_revision: int = 0,
        total: int = 0,
    ) -> None:
        with self._lock:
            existing = self._runs.get(run_id)
            if existing is not None:
                existing.path = path
                existing.owner_user_id = owner_user_id
                existing.status = status
                if stage is not None:
                    existing.stage = stage
                existing.realization_revision = realization_revision
                existing.teaching_plan_revision = teaching_plan_revision
                existing.document_revision = document_revision
                if total:
                    existing.total = total
                return
            self._runs[run_id] = _RunRecord(
                run_id=run_id,
                path=path,
                owner_user_id=owner_user_id,
                status=status,
                stage=stage or status,
                realization_revision=realization_revision,
                teaching_plan_revision=teaching_plan_revision,
                document_revision=document_revision,
                total=total,
            )

    def sync_from_db(
        self,
        run_id: str,
        *,
        path: str,
        owner_user_id: str,
        status: str,
        realization_revision: int,
        teaching_plan_revision: int,
        document_revision: int = 0,
        stage: str | None = None,
    ) -> None:
        """Mirror authoritative DB realization fields into the progress projection."""
        self.ensure_run(
            run_id,
            path=path,
            owner_user_id=owner_user_id,
            status=status,
            stage=stage or status,
            realization_revision=realization_revision,
            teaching_plan_revision=teaching_plan_revision,
            document_revision=document_revision,
        )

    def owner_user_id(self, run_id: str) -> str | None:
        with self._lock:
            row = self._runs.get(run_id)
            return row.owner_user_id if row else None

    def append_event(
        self,
        run_id: str,
        *,
        event_type: str,
        path: str | None = None,
        stage: str | None = None,
        item_id: str | None = None,
        attempt: int | None = None,
        error_category: str | None = None,
        payload: Mapping[str, Any] | None = None,
        at: datetime | None = None,
    ) -> RunEvent:
        with self._lock:
            row = self._require(run_id)
            event = RunEvent(
                seq=row.next_seq,
                event_type=event_type,
                at=at or _utcnow(),
                run_id=run_id,
                path=path or row.path,
                stage=stage if stage is not None else row.stage,
                item_id=item_id,
                attempt=attempt,
                error_category=error_category,
                payload=dict(redact_secrets(payload or {})),
            )
            row.next_seq += 1
            row.events.append(event)
            self._trim_events(row)
            if stage is not None:
                row.stage = stage
            return event

    def set_item_state(
        self,
        run_id: str,
        *,
        item_id: str,
        stage: str,
        attempt: int,
        state: str,
    ) -> None:
        with self._lock:
            row = self._require(run_id)
            if state in {"completed", "ready", "skipped"}:
                row.active.pop(item_id, None)
                row.completed += 1
                row.total = max(row.total, row.completed)
            elif state in {"failed", "cancelled"}:
                row.active.pop(item_id, None)
            else:
                row.active[item_id] = ActiveItem(
                    item_id=item_id,
                    stage=stage,
                    attempt=attempt,
                    state=state,
                )

    def set_counts(self, run_id: str, *, completed: int, total: int) -> None:
        with self._lock:
            row = self._require(run_id)
            row.completed = max(0, int(completed))
            row.total = max(0, int(total))

    def schedule_retry(
        self,
        run_id: str,
        *,
        item_id: str,
        attempt: int,
        next_retry_at: datetime | str,
        reason: str | None = None,
    ) -> None:
        when = (
            next_retry_at
            if isinstance(next_retry_at, str)
            else next_retry_at.astimezone(UTC).isoformat()
        )
        with self._lock:
            row = self._require(run_id)
            row.retries[item_id] = RetryScheduleEntry(
                item_id=item_id,
                attempt=attempt,
                next_retry_at=when,
                reason=reason,
            )

    def clear_retry(self, run_id: str, *, item_id: str) -> None:
        with self._lock:
            row = self._require(run_id)
            row.retries.pop(item_id, None)

    def record_model_call(
        self,
        run_id: str,
        *,
        path: str,
        stage: str,
        item_id: str,
        attempt: int,
        model: str | None,
        prompt_hash: str | None,
        policy_hash: str | None = None,
        composition_mode: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cost_usd: float | None = None,
        provider_request_id: str | None = None,
        emit_event: bool = True,
    ) -> ModelCallTrace:
        """Record an actual model call. Pass None for unknown usage — never coerce to 0."""
        trace = ModelCallTrace(
            run_id=run_id,
            path=path,
            stage=stage,
            item_id=item_id,
            attempt=attempt,
            model=model,
            prompt_hash=prompt_hash,
            policy_hash=policy_hash,
            composition_mode=composition_mode,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            provider_request_id=provider_request_id,
        )
        with self._lock:
            row = self._require(run_id)
            row.traces.append(trace)
        if emit_event:
            self.append_event(
                run_id,
                event_type="model_call",
                path=path,
                stage=stage,
                item_id=item_id,
                attempt=attempt,
                payload={
                    "model": model,
                    "prompt_hash": prompt_hash,
                    "policy_hash": policy_hash,
                    "composition_mode": composition_mode,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": cost_usd,
                    "provider_request_id": provider_request_id,
                    "usage_known": tokens_in is not None or tokens_out is not None,
                },
            )
        return trace

    def get_status(self, run_id: str) -> RunStatusView:
        with self._lock:
            row = self._require(run_id)
            return self._status_unlocked(row)

    def replay(self, run_id: str, *, after_seq: int = 0) -> ReplayResult:
        """Return ordered events after ``after_seq``.

        If ``after_seq`` is below the retained window, returns mode=snapshot with a
        status snapshot plus remaining retained events (reconnect recovery).
        Duplicate reconnects with the same after_seq are idempotent.
        """
        with self._lock:
            row = self._require(run_id)
            oldest = row.events[0].seq if row.events else row.next_seq
            latest = row.next_seq - 1
            if after_seq > 0 and after_seq < oldest:
                # Retention expired for the requested cursor — snapshot + retained tail.
                return ReplayResult(
                    mode="snapshot",
                    events=list(row.events),
                    snapshot=self._status_unlocked(row).to_dict(),
                    oldest_retained_seq=oldest if row.events else 0,
                    latest_seq=latest,
                )
            events = [event for event in row.events if event.seq > after_seq]
            return ReplayResult(
                mode="replay",
                events=events,
                snapshot=None,
                oldest_retained_seq=oldest if row.events else 0,
                latest_seq=latest,
            )

    def list_traces(self, run_id: str) -> list[ModelCallTrace]:
        with self._lock:
            row = self._require(run_id)
            return list(row.traces)

    def export_traces(
        self,
        run_id: str,
        exporter: TraceExporter | Callable[[list[ModelCallTrace]], None],
    ) -> bool:
        """Push traces to an exporter. Exporter failures never propagate."""
        traces = self.list_traces(run_id)
        try:
            if hasattr(exporter, "export"):
                exporter.export(traces)  # type: ignore[union-attr]
            else:
                exporter(traces)  # type: ignore[operator]
            return True
        except Exception:
            logger.exception(
                "trace exporter failed for run_id=%s; generation continues",
                run_id,
            )
            return False

    def snapshot(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._require(run_id)
            return {
                "run_id": row.run_id,
                "path": row.path,
                "owner_user_id": row.owner_user_id,
                "status": row.status,
                "stage": row.stage,
                "realization_revision": row.realization_revision,
                "teaching_plan_revision": row.teaching_plan_revision,
                "document_revision": row.document_revision,
                "completed": row.completed,
                "total": row.total,
                "next_seq": row.next_seq,
                "active": {k: v.to_dict() for k, v in row.active.items()},
                "retries": {k: v.to_dict() for k, v in row.retries.items()},
                "events": [event.to_dict() for event in row.events],
                "traces": [trace.to_dict() for trace in row.traces],
            }

    def import_run_snapshot(self, data: Mapping[str, Any]) -> None:
        """Hydrate/replace a run from a persisted snapshot (worker restart)."""
        run_id = str(data.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("progress snapshot missing run_id")
        with self._lock:
            events: list[RunEvent] = []
            for raw in list(data.get("events") or []):
                if not isinstance(raw, Mapping):
                    continue
                at_raw = raw.get("at")
                if isinstance(at_raw, datetime):
                    at = at_raw if at_raw.tzinfo else at_raw.replace(tzinfo=UTC)
                elif isinstance(at_raw, str) and at_raw:
                    at = datetime.fromisoformat(at_raw)
                else:
                    at = _utcnow()
                events.append(
                    RunEvent(
                        seq=int(raw.get("seq") or 0),
                        event_type=str(raw.get("event_type") or "event"),
                        at=at,
                        run_id=run_id,
                        path=raw.get("path"),
                        stage=raw.get("stage"),
                        item_id=raw.get("item_id"),
                        attempt=(
                            int(raw["attempt"])
                            if raw.get("attempt") is not None
                            else None
                        ),
                        error_category=raw.get("error_category"),
                        payload=dict(raw.get("payload") or {}),
                    )
                )
            traces: list[ModelCallTrace] = []
            for raw in list(data.get("traces") or []):
                if not isinstance(raw, Mapping):
                    continue
                at_raw = raw.get("at")
                if isinstance(at_raw, datetime):
                    at = at_raw if at_raw.tzinfo else at_raw.replace(tzinfo=UTC)
                elif isinstance(at_raw, str) and at_raw:
                    at = datetime.fromisoformat(at_raw)
                else:
                    at = _utcnow()
                traces.append(
                    ModelCallTrace(
                        run_id=run_id,
                        path=str(raw.get("path") or data.get("path") or ""),
                        stage=str(raw.get("stage") or ""),
                        item_id=str(raw.get("item_id") or ""),
                        attempt=int(raw.get("attempt") or 1),
                        model=raw.get("model"),
                        prompt_hash=raw.get("prompt_hash"),
                        policy_hash=raw.get("policy_hash"),
                        composition_mode=raw.get("composition_mode"),
                        tokens_in=raw.get("tokens_in"),
                        tokens_out=raw.get("tokens_out"),
                        cost_usd=raw.get("cost_usd"),
                        provider_request_id=raw.get("provider_request_id"),
                        at=at,
                    )
                )
            active: dict[str, ActiveItem] = {}
            for key, raw in dict(data.get("active") or {}).items():
                if not isinstance(raw, Mapping):
                    continue
                active[str(key)] = ActiveItem(
                    item_id=str(raw.get("item_id") or key),
                    stage=str(raw.get("stage") or ""),
                    attempt=int(raw.get("attempt") or 1),
                    state=str(raw.get("state") or "active"),
                )
            retries: dict[str, RetryScheduleEntry] = {}
            for key, raw in dict(data.get("retries") or {}).items():
                if not isinstance(raw, Mapping):
                    continue
                retries[str(key)] = RetryScheduleEntry(
                    item_id=str(raw.get("item_id") or key),
                    attempt=int(raw.get("attempt") or 1),
                    next_retry_at=str(raw.get("next_retry_at") or ""),
                    reason=raw.get("reason"),
                )
            self._runs[run_id] = _RunRecord(
                run_id=run_id,
                path=str(data.get("path") or ""),
                owner_user_id=str(data.get("owner_user_id") or ""),
                status=str(data.get("status") or "queued"),
                stage=str(data.get("stage") or data.get("status") or "queued"),
                realization_revision=int(data.get("realization_revision") or 1),
                teaching_plan_revision=int(data.get("teaching_plan_revision") or 1),
                document_revision=int(data.get("document_revision") or 0),
                completed=int(data.get("completed") or 0),
                total=int(data.get("total") or 0),
                active=active,
                retries=retries,
                events=events,
                traces=traces,
                next_seq=int(data.get("next_seq") or (max((e.seq for e in events), default=0) + 1)),
            )
            self._trim_events(self._runs[run_id])

    def _status_unlocked(self, row: _RunRecord) -> RunStatusView:
        return RunStatusView(
            run_id=row.run_id,
            path=row.path,
            status=row.status,
            stage=row.stage,
            active_items=list(row.active.values()),
            completed=row.completed,
            total=row.total,
            retry_schedule=list(row.retries.values()),
            allowed_actions=allowed_actions_for(
                path=row.path, status=row.status, stage=row.stage
            ),
            revisions={
                "realization_revision": row.realization_revision,
                "teaching_plan_revision": row.teaching_plan_revision,
                "document_revision": row.document_revision,
            },
            latest_seq=row.next_seq - 1,
            owner_user_id=row.owner_user_id,
            links={
                "status": f"/api/v1/realizations/{row.run_id}/status",
                "events": f"/api/v1/realizations/{row.run_id}/events",
                "events_stream": f"/api/v1/realizations/{row.run_id}/events/stream",
            },
        )

    def _trim_events(self, row: _RunRecord) -> None:
        if len(row.events) > self.event_retention:
            row.events = row.events[-self.event_retention :]

    def _require(self, run_id: str) -> _RunRecord:
        row = self._runs.get(run_id)
        if row is None:
            raise KeyError(f"unknown progress run {run_id!r}")
        return row


# Process-wide default used by HTTP routes and authoring hooks.
default_progress_store = ProgressStore()


__all__ = [
    "DEFAULT_EVENT_RETENTION",
    "ActiveItem",
    "ModelCallTrace",
    "ProgressStore",
    "ReplayResult",
    "RetryScheduleEntry",
    "RunEvent",
    "RunStatusView",
    "TraceExporter",
    "allowed_actions_for",
    "default_progress_store",
    "prompt_hash_for",
    "redact_secrets",
]
