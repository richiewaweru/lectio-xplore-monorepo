"""Content-hash keyed checkpoints for composition/node outputs (P03 G09/G10/G15)."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Literal

from print.generation.whole_lesson.states import ResumeDecision

CHECKPOINT_SCHEMA_VERSION = 1

CheckpointStatus = Literal["started", "ready", "failed", "ambiguous"]


def content_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CheckpointCompatibility:
    """Inputs that must match for safe resume reuse."""

    teaching_revision: int
    input_hash: str
    definition_hash: str
    schema_version: int = CHECKPOINT_SCHEMA_VERSION
    composition_identity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "teaching_revision": self.teaching_revision,
            "input_hash": self.input_hash,
            "definition_hash": self.definition_hash,
            "schema_version": self.schema_version,
            "composition_identity": self.composition_identity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointCompatibility:
        return cls(
            teaching_revision=int(data.get("teaching_revision") or 0),
            input_hash=str(data.get("input_hash") or ""),
            definition_hash=str(data.get("definition_hash") or ""),
            schema_version=int(data.get("schema_version") or CHECKPOINT_SCHEMA_VERSION),
            composition_identity=(
                str(data["composition_identity"])
                if data.get("composition_identity") is not None
                else None
            ),
        )


class IncompatibleCheckpointError(RuntimeError):
    """Resume rejected because compatibility keys diverged."""


# Dependency order for selective recovery (G10). Downstream depends on upstream.
STAGE_DEPENDENCY_ORDER: tuple[str, ...] = (
    "composition",
    "node",
    "interaction",
    "media",
    "assembly",
    "export",
)


def selective_recovery_keys(
    *,
    failed_stage: str,
    ready_keys: set[str],
    all_keys: set[str],
) -> set[str]:
    """Return work-item keys that must re-run given a failed stage.

    Ready siblings whose stage is independent of the failure (same or upstream of
    the failed stage's dependency frontier and not the failed key) are skipped.
    Downstream stages of the failed stage always re-run when present.
    """
    if failed_stage not in STAGE_DEPENDENCY_ORDER:
        raise ValueError(f"unknown recovery stage: {failed_stage}")
    fail_idx = STAGE_DEPENDENCY_ORDER.index(failed_stage)
    must_run: set[str] = set()
    for key in all_keys:
        stage = key.split(":", 1)[0]
        if stage not in STAGE_DEPENDENCY_ORDER:
            # Unknown prefix: treat as must-run when not ready.
            if key not in ready_keys:
                must_run.add(key)
            continue
        idx = STAGE_DEPENDENCY_ORDER.index(stage)
        if idx > fail_idx or idx == fail_idx and key not in ready_keys:
            must_run.add(key)
        elif idx < fail_idx and key not in ready_keys:
            # Upstream missing: must run before failed stage can succeed.
            must_run.add(key)
    return must_run


@dataclass
class CheckpointRecord:
    key: str
    status: CheckpointStatus
    compatibility: CheckpointCompatibility
    content_hash: str | None = None
    payload: dict[str, Any] | None = None
    lease_token: int | None = None
    outcome: str | None = None  # e.g. composition_mode

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status,
            "compatibility": self.compatibility.to_dict(),
            "content_hash": self.content_hash,
            "payload": dict(self.payload) if self.payload is not None else None,
            "lease_token": self.lease_token,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointRecord:
        return cls(
            key=str(data["key"]),
            status=str(data["status"]),  # type: ignore[arg-type]
            compatibility=CheckpointCompatibility.from_dict(
                dict(data.get("compatibility") or {})
            ),
            content_hash=data.get("content_hash"),
            payload=dict(data["payload"]) if isinstance(data.get("payload"), dict) else None,
            lease_token=data.get("lease_token"),
            outcome=data.get("outcome"),
        )


@dataclass
class CheckpointStore:
    """In-memory / serializable checkpoint map (composition, nodes, interactions)."""

    records: dict[str, CheckpointRecord] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def get(self, key: str) -> CheckpointRecord | None:
        with self._lock:
            row = self.records.get(key)
            return CheckpointRecord.from_dict(row.to_dict()) if row else None

    def begin(
        self,
        key: str,
        *,
        compatibility: CheckpointCompatibility,
        lease_token: int | None = None,
    ) -> CheckpointRecord:
        with self._lock:
            existing = self.records.get(key)
            if existing is not None and existing.status == "ready":
                self._assert_compatible(existing.compatibility, compatibility)
                return CheckpointRecord.from_dict(existing.to_dict())
            record = CheckpointRecord(
                key=key,
                status="started",
                compatibility=compatibility,
                lease_token=lease_token,
            )
            self.records[key] = record
            return CheckpointRecord.from_dict(record.to_dict())

    def commit(
        self,
        key: str,
        *,
        payload: dict[str, Any],
        compatibility: CheckpointCompatibility,
        lease_token: int | None = None,
        outcome: str | None = None,
    ) -> CheckpointRecord:
        digest = content_hash(payload)
        with self._lock:
            existing = self.records.get(key)
            if existing is not None and existing.status == "ready":
                self._assert_compatible(existing.compatibility, compatibility)
                # Crash-after-commit reuse: identical payload must not rewrite.
                if existing.content_hash == digest:
                    return CheckpointRecord.from_dict(existing.to_dict())
                if existing.payload is not None:
                    raise RuntimeError(
                        f"checkpoint {key!r} already committed with different content"
                    )
            record = CheckpointRecord(
                key=key,
                status="ready",
                compatibility=compatibility,
                content_hash=digest,
                payload=dict(payload),
                lease_token=lease_token,
                outcome=outcome,
            )
            self.records[key] = record
            return CheckpointRecord.from_dict(record.to_dict())

    def mark_ambiguous(self, key: str) -> CheckpointRecord | None:
        with self._lock:
            existing = self.records.get(key)
            if existing is None:
                return None
            if existing.status == "ready":
                return CheckpointRecord.from_dict(existing.to_dict())
            existing.status = "ambiguous"
            return CheckpointRecord.from_dict(existing.to_dict())

    def decide_resume(
        self,
        key: str,
        *,
        compatibility: CheckpointCompatibility,
        current_lease_token: int | None = None,
    ) -> ResumeDecision:
        record = self.get(key)
        if record is None:
            return ResumeDecision.RUN_MISSING
        self._assert_compatible(record.compatibility, compatibility)
        if record.status == "ready":
            return ResumeDecision.SKIP_READY
        if record.status == "failed":
            return ResumeDecision.RETRY_FAILED
        if record.status == "ambiguous":
            # Honest: may re-run if budget remains; never claim exactly-once.
            return ResumeDecision.RETRY_ABANDONED
        if record.status == "started":
            if (
                record.lease_token is not None
                and current_lease_token is not None
                and int(record.lease_token) == int(current_lease_token)
            ):
                return ResumeDecision.SKIP_IN_FLIGHT
            return ResumeDecision.RETRY_ABANDONED
        return ResumeDecision.RUN_MISSING

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {k: v.to_dict() for k, v in self.records.items()}

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> CheckpointStore:
        store = cls()
        for key, raw in data.items():
            store.records[str(key)] = CheckpointRecord.from_dict(dict(raw))
        return store

    @staticmethod
    def _assert_compatible(
        stored: CheckpointCompatibility,
        expected: CheckpointCompatibility,
    ) -> None:
        if stored.schema_version != expected.schema_version:
            raise IncompatibleCheckpointError(
                f"checkpoint schema {stored.schema_version} != {expected.schema_version}"
            )
        if stored.teaching_revision != expected.teaching_revision:
            raise IncompatibleCheckpointError("teaching_revision mismatch")
        if stored.input_hash != expected.input_hash:
            raise IncompatibleCheckpointError("input_hash mismatch")
        if stored.definition_hash != expected.definition_hash:
            raise IncompatibleCheckpointError("definition_hash mismatch")
        if (
            stored.composition_identity is not None
            and expected.composition_identity is not None
            and stored.composition_identity != expected.composition_identity
        ):
            raise IncompatibleCheckpointError("composition_identity mismatch")


__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "STAGE_DEPENDENCY_ORDER",
    "CheckpointCompatibility",
    "CheckpointRecord",
    "CheckpointStore",
    "IncompatibleCheckpointError",
    "content_hash",
    "selective_recovery_keys",
]
