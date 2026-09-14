"""Persisted concurrency / deadline / cost reservation helpers (P03 G14)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class ResourceLimitError(RuntimeError):
    """Concurrency, deadline, or cost budget exhausted."""


@dataclass
class ResourceLimits:
    max_concurrency: int = 4
    deadline_at: datetime | None = None
    max_cost_units: float | None = None
    reserved_cost_units: float = 0.0
    unknown_usage: bool = False
    _active: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def reserve_slot(self) -> None:
        with self._lock:
            self._assert_deadline()
            if self._active >= self.max_concurrency:
                raise ResourceLimitError(
                    f"concurrency exhausted: {self._active}/{self.max_concurrency}"
                )
            self._active += 1

    def release_slot(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)

    def reserve_cost(self, units: float | None) -> None:
        with self._lock:
            self._assert_deadline()
            if units is None:
                self.unknown_usage = True
                return
            if self.max_cost_units is not None and (
                self.reserved_cost_units + float(units) > self.max_cost_units
            ):
                raise ResourceLimitError(
                    f"cost budget exhausted: "
                    f"{self.reserved_cost_units + float(units)}/{self.max_cost_units}"
                )
            self.reserved_cost_units += float(units)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "max_concurrency": self.max_concurrency,
                "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
                "max_cost_units": self.max_cost_units,
                "reserved_cost_units": self.reserved_cost_units,
                "unknown_usage": self.unknown_usage,
                "active": self._active,
            }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> ResourceLimits:
        deadline_raw = data.get("deadline_at")
        deadline = None
        if isinstance(deadline_raw, str) and deadline_raw:
            deadline = datetime.fromisoformat(deadline_raw)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
        limits = cls(
            max_concurrency=int(data.get("max_concurrency") or 4),
            deadline_at=deadline,
            max_cost_units=(
                float(data["max_cost_units"])
                if data.get("max_cost_units") is not None
                else None
            ),
            reserved_cost_units=float(data.get("reserved_cost_units") or 0.0),
            unknown_usage=bool(data.get("unknown_usage")),
        )
        limits._active = int(data.get("active") or 0)
        return limits

    def _assert_deadline(self) -> None:
        if self.deadline_at is None:
            return
        now = datetime.now(UTC)
        deadline = (
            self.deadline_at
            if self.deadline_at.tzinfo
            else self.deadline_at.replace(tzinfo=UTC)
        )
        if now >= deadline:
            raise ResourceLimitError("deadline exceeded")


__all__ = ["ResourceLimitError", "ResourceLimits"]
