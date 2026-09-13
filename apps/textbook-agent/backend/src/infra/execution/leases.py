"""Shared lease / resume primitives (domain-neutral; P03/P05 boundary fix).

Print whole-lesson states re-export these for compatibility. Learn fencing and
infra checkpoints import from here so learn↛print and infra↛product hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DEFAULT_LEASE_SECONDS = 90


class LeaseLostError(RuntimeError):
    """Raised when a worker no longer owns the generation lease."""


@dataclass(frozen=True)
class ExecutionLease:
    generation_id: str
    worker_id: str
    lease_token: int
    stage: str


class ResumeDecision(str, Enum):
    SKIP_READY = "skip_ready"
    SKIP_IN_FLIGHT = "skip_in_flight"
    RUN_MISSING = "run_missing"
    RETRY_FAILED = "retry_failed"
    RETRY_ABANDONED = "retry_abandoned"
    BLOCK_TERMINAL = "block_terminal"


__all__ = [
    "DEFAULT_LEASE_SECONDS",
    "ExecutionLease",
    "LeaseLostError",
    "ResumeDecision",
]
