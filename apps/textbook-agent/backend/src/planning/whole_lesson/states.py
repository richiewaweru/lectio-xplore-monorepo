"""Canonical native whole-lesson execution states and transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# writing_sections is the preferred writing stage; writing_blocks remains a
# compatibility alias for in-flight leases and resume.
_WRITING_TARGETS = frozenset(
    {"assembling", "failed_recoverable", "failed_terminal", "cancelled"}
)

_PRE_WORKER_FAIL_TARGETS = frozenset(
    {"failed_recoverable", "failed_terminal", "cancelled"}
)

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    # Pre-worker bootstrap statuses (items / teaching plan before teacher gate).
    "pending": _PRE_WORKER_FAIL_TARGETS | frozenset({"item_generation", "planning_teaching"}),
    "stage2_running": _PRE_WORKER_FAIL_TARGETS | frozenset({"item_generation", "planning_teaching"}),
    "plan_ready": _PRE_WORKER_FAIL_TARGETS,
    "awaiting_review": _PRE_WORKER_FAIL_TARGETS,
    "stage2_error": frozenset({"failed_recoverable", "failed_terminal", "cancelled"}),
    # Pre-worker retry checkpoints (not claimable by the post-approval worker).
    "item_generation": frozenset(
        {
            "planning_teaching",
            "failed_recoverable",
            "failed_terminal",
            "cancelled",
        }
    ),
    "planning_teaching": frozenset(
        {
            "awaiting_teaching_approval",
            "failed_recoverable",
            "failed_terminal",
            "cancelled",
        }
    ),
    "awaiting_teaching_approval": frozenset(
        {"queued", "cancelled", "failed_recoverable", "failed_terminal"}
    ),
    "queued": frozenset({"planning_forms", "cancelled", "failed_terminal", "failed_recoverable"}),
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
    "failed_recoverable": frozenset(
        {"queued", "item_generation", "planning_teaching", "cancelled"}
    ),
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
# Pre-worker retry checkpoints are leased separately; never forced through planning_forms.
PRE_WORKER_RETRY_STATUSES = frozenset({"item_generation", "planning_teaching"})
WRITING_STATUSES = frozenset({"writing_sections", "writing_blocks"})
TERMINAL_STATUSES = frozenset(
    {"ready", "completed", "failed_terminal", "cancelled", "rejected_by_teacher"}
)
NATIVE_STATUSES = frozenset(
    {
        "item_generation",
        "planning_teaching",
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

# Durable work_kind values stored on page_document_v2.execution
WORK_KIND_PRE_WORKER_ITEM = "pre_worker_item_retry"
WORK_KIND_PRE_WORKER_TEACHING = "pre_worker_teaching_retry"
WORK_KIND_POST_APPROVAL = "post_approval_execution"
PRE_WORKER_WORK_KINDS = frozenset(
    {WORK_KIND_PRE_WORKER_ITEM, WORK_KIND_PRE_WORKER_TEACHING}
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
