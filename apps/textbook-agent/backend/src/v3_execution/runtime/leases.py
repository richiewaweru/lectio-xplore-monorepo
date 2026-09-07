"""DB-shaped worker leases / fencing (Phase 07). Minimal in-process model of durable claims."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


class LeaseLostError(RuntimeError):
    pass


@dataclass
class LeaseRecord:
    generation_id: str
    owner_token: str
    expires_at: datetime
    heartbeat_at: datetime


@dataclass
class LeaseStore:
    ttl_seconds: int = 30
    leases: dict[str, LeaseRecord] = field(default_factory=dict)
    now: datetime | None = None

    def _clock(self) -> datetime:
        return self.now or datetime.now(timezone.utc)

    def claim(self, generation_id: str) -> LeaseRecord:
        current = self.leases.get(generation_id)
        clock = self._clock()
        if current is not None and current.expires_at > clock:
            raise LeaseLostError(f"generation {generation_id} already claimed")
        token = str(uuid4())
        record = LeaseRecord(
            generation_id=generation_id,
            owner_token=token,
            expires_at=clock + timedelta(seconds=self.ttl_seconds),
            heartbeat_at=clock,
        )
        self.leases[generation_id] = record
        return record

    def heartbeat(self, generation_id: str, owner_token: str) -> LeaseRecord:
        record = self._require_owner(generation_id, owner_token)
        clock = self._clock()
        record.heartbeat_at = clock
        record.expires_at = clock + timedelta(seconds=self.ttl_seconds)
        return record

    def _require_owner(self, generation_id: str, owner_token: str) -> LeaseRecord:
        record = self.leases.get(generation_id)
        clock = self._clock()
        if record is None or record.expires_at <= clock:
            raise LeaseLostError("lease expired or missing")
        if record.owner_token != owner_token:
            raise LeaseLostError("ownership token mismatch")
        return record

    def mutating_write(
        self,
        generation_id: str,
        owner_token: str,
        *,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_owner(generation_id, owner_token)
        return {"ok": True, "payload": payload}

    def reclaim_expired(self) -> list[str]:
        clock = self._clock()
        expired = [
            generation_id
            for generation_id, record in self.leases.items()
            if record.expires_at <= clock
        ]
        for generation_id in expired:
            del self.leases[generation_id]
        return expired
