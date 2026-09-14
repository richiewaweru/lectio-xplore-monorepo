"""Durable per-work-item provider call budget (P03 G11/G14).

Default policy: 3 actual provider dispatches per logical work item
(initial + up to two additional), including transport/schema/quality
repairs and budgeted fallback calls. Nested SDK retries must not multiply
this counter — reserve atomically before each real dispatch.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Literal

DEFAULT_MAX_PROVIDER_CALLS = 3

AttemptStatus = Literal["reserved", "dispatched", "ambiguous", "released"]


class BudgetExhaustedError(RuntimeError):
    """No remaining call slots for this work item."""

    def __init__(self, work_item_id: str, *, consumed: int, max_calls: int) -> None:
        self.work_item_id = work_item_id
        self.consumed = consumed
        self.max_calls = max_calls
        super().__init__(
            f"call budget exhausted for {work_item_id!r}: "
            f"{consumed}/{max_calls} slots used"
        )


@dataclass
class CallAttempt:
    attempt: int
    status: AttemptStatus


@dataclass
class CallBudget:
    """Thread-safe work-item attempt counter.

    ``consumed`` counts reserved + dispatched + ambiguous slots. A crash after
    reserve but before a confirmed dispatch leaves the slot as ``ambiguous`` —
    resume must not treat that as a free retry or as an exactly-once success.
    """

    work_item_id: str
    max_calls: int = DEFAULT_MAX_PROVIDER_CALLS
    attempts: list[CallAttempt] = field(default_factory=list)
    fallback_declared: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @property
    def consumed(self) -> int:
        return sum(1 for a in self.attempts if a.status != "released")

    @property
    def dispatched_count(self) -> int:
        return sum(1 for a in self.attempts if a.status == "dispatched")

    @property
    def ambiguous_count(self) -> int:
        return sum(1 for a in self.attempts if a.status in {"reserved", "ambiguous"})

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.consumed)

    def reserve(self) -> int:
        """Atomically reserve one slot before provider dispatch. Returns attempt #."""
        with self._lock:
            if self.consumed >= self.max_calls:
                raise BudgetExhaustedError(
                    self.work_item_id,
                    consumed=self.consumed,
                    max_calls=self.max_calls,
                )
            attempt = len(self.attempts) + 1
            self.attempts.append(CallAttempt(attempt=attempt, status="reserved"))
            return attempt

    def mark_dispatched(self, attempt: int) -> None:
        """Confirm the reserved slot performed a real provider dispatch."""
        with self._lock:
            row = self._require(attempt)
            if row.status == "released":
                raise RuntimeError(f"attempt {attempt} was released; cannot mark dispatched")
            row.status = "dispatched"

    def mark_ambiguous(self, attempt: int) -> None:
        """Crash / unknown outcome after reserve — never claim exactly-once."""
        with self._lock:
            row = self._require(attempt)
            if row.status == "dispatched":
                return
            row.status = "ambiguous"

    def release_unused(self, attempt: int) -> None:
        """Release a reservation that never dispatched (cancel before call)."""
        with self._lock:
            row = self._require(attempt)
            if row.status == "dispatched":
                raise RuntimeError(f"attempt {attempt} already dispatched")
            row.status = "released"

    def declare_fallback(self) -> int:
        """Reserve and consume one budgeted slot for a declared non-LLM fallback.

        Heuristic / policy fallbacks remain visible via ``fallback_declared`` and
        cannot bypass an exhausted work-item cap.
        """
        with self._lock:
            if self.consumed >= self.max_calls:
                raise BudgetExhaustedError(
                    self.work_item_id,
                    consumed=self.consumed,
                    max_calls=self.max_calls,
                )
            attempt = len(self.attempts) + 1
            self.attempts.append(CallAttempt(attempt=attempt, status="dispatched"))
            self.fallback_declared = True
            return attempt

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "work_item_id": self.work_item_id,
                "max_calls": self.max_calls,
                "fallback_declared": self.fallback_declared,
                "attempts": [
                    {"attempt": a.attempt, "status": a.status} for a in self.attempts
                ],
                "consumed": self.consumed,
                "dispatched_count": self.dispatched_count,
                "ambiguous_count": self.ambiguous_count,
            }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> CallBudget:
        budget = cls(
            work_item_id=str(data["work_item_id"]),
            max_calls=int(data.get("max_calls") or DEFAULT_MAX_PROVIDER_CALLS),
            fallback_declared=bool(data.get("fallback_declared")),
        )
        for raw in data.get("attempts") or []:
            budget.attempts.append(
                CallAttempt(attempt=int(raw["attempt"]), status=str(raw["status"]))  # type: ignore[arg-type]
            )
        return budget

    def _require(self, attempt: int) -> CallAttempt:
        for row in self.attempts:
            if row.attempt == attempt:
                return row
        raise KeyError(f"unknown attempt {attempt} for {self.work_item_id!r}")


class CallBudgetLedger:
    """Process-local durable ledger keyed by work_item_id (survives logical resume)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}

    def get_or_create(
        self,
        work_item_id: str,
        *,
        max_calls: int = DEFAULT_MAX_PROVIDER_CALLS,
    ) -> CallBudget:
        with self._lock:
            existing = self._items.get(work_item_id)
            if existing is not None:
                return CallBudget.from_snapshot(existing)
            budget = CallBudget(work_item_id=work_item_id, max_calls=max_calls)
            self._items[work_item_id] = budget.snapshot()
            return budget

    def persist(self, budget: CallBudget) -> None:
        with self._lock:
            self._items[budget.work_item_id] = budget.snapshot()

    def load(self, work_item_id: str) -> CallBudget | None:
        with self._lock:
            raw = self._items.get(work_item_id)
            return CallBudget.from_snapshot(raw) if raw else None

    def export_state(self) -> dict[str, Any]:
        with self._lock:
            return {k: dict(v) for k, v in self._items.items()}

    def import_state(self, state: dict[str, Any]) -> None:
        with self._lock:
            self._items = {str(k): dict(v) for k, v in state.items()}


__all__ = [
    "DEFAULT_MAX_PROVIDER_CALLS",
    "BudgetExhaustedError",
    "CallAttempt",
    "CallBudget",
    "CallBudgetLedger",
]
