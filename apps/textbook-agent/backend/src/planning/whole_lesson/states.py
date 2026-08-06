"""Canonical native whole-lesson execution states and transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# writing_sections is the preferred writing stage; writing_blocks remains a
# compatibility alias for in-flight leases and resume.
_WRITING_TARGETS = frozenset(
    {"assembling", "failed_recoverable", "failed_terminal", "cancelled"}
)

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "awaiting_teaching_approval": frozenset({"queued", "cancelled"}),
    "queued": frozenset({"planning_forms", "cancelled", "failed_terminal"}),
    "planning_forms": frozenset(
        {
            "writing_sections",
            "writing_blocks",  # compatibility
            "failed_recoverable",
            "failed_terminal",
            "cancelled",
        }
    ),
    "writing_sections": _WRITING_TARGETS,
    "writing_blocks": _WRITING_TARGETS,
    "assembling": frozenset(
        {
            "awaiting_visuals",
            "ready",
            "failed_recoverable",
            "failed_terminal",
            "cancelled",
        }
    ),
    "awaiting_visuals": frozenset({"ready", "cancelled", "failed_terminal"}),
    "ready": frozenset(),
    "failed_recoverable": frozenset({"queued", "cancelled"}),
    "failed_terminal": frozenset(),
    "cancelled": frozenset(),
    # Compatibility aliases treated as nonterminal peers of ready/completed.
    "completed": frozenset(),
    "rejected_by_teacher": frozenset(),
}

CLAIMABLE_STATUSES = frozenset({"queued", "failed_recoverable"})
ACTIVE_STATUSES = frozenset(
    {"planning_forms", "writing_sections", "writing_blocks", "assembling"}
)
WRITING_STATUSES = frozenset({"writing_sections", "writing_blocks"})
TERMINAL_STATUSES = frozenset(
    {"ready", "completed", "failed_terminal", "cancelled", "rejected_by_teacher"}
)
NATIVE_STATUSES = frozenset(
    {
        "awaiting_teaching_approval",
        "queued",
        "planning_forms",
        "writing_sections",
        "writing_blocks",
        "assembling",
        "awaiting_visuals",
        "ready",
        "failed_recoverable",
        "failed_terminal",
        "rejected_by_teacher",
    }
)

DEFAULT_VARIANT_ID = "everyone"
DEFAULT_LEASE_SECONDS = 90
HEARTBEAT_INTERVAL_SECONDS = 25
MAX_SECTION_CONCURRENCY = 4
# Within a single section, bound concurrent block writers.
MAX_WRITER_CONCURRENCY = 3
DEFAULT_WORKER_POLL_SECONDS = 2.0


class IllegalTransitionError(ValueError):
    pass


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


def assert_legal_transition(current: str, target: str) -> None:
    allowed = LEGAL_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise IllegalTransitionError(
            f"illegal transition {current!r} → {target!r}; allowed={sorted(allowed)}"
        )


def execution_key(section_id: str, block_id: str, variant_id: str = DEFAULT_VARIANT_ID) -> str:
    return f"{section_id}:{block_id}:{variant_id}"


def parse_execution_key(key: str) -> tuple[str, str, str]:
    parts = key.split(":")
    if len(parts) != 3:
        raise ValueError(f"invalid execution key {key!r}")
    return parts[0], parts[1], parts[2]


def decide_resume(
    outcome: dict | None,
    *,
    current_lease_token: int | None,
) -> ResumeDecision:
    if not outcome:
        return ResumeDecision.RUN_MISSING
    status = str(outcome.get("status") or "")
    if status in {"ready", "visual_pending"}:
        return ResumeDecision.SKIP_READY
    if status == "failed_terminal":
        return ResumeDecision.BLOCK_TERMINAL
    if status in {"failed", "failed_recoverable"}:
        return ResumeDecision.RETRY_FAILED
    if status == "started":
        token = outcome.get("lease_token")
        if token is None:
            return ResumeDecision.RETRY_ABANDONED
        if current_lease_token is not None and int(token) == int(current_lease_token):
            return ResumeDecision.SKIP_IN_FLIGHT
        return ResumeDecision.RETRY_ABANDONED
    return ResumeDecision.RUN_MISSING
