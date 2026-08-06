"""Canonical native whole-lesson execution states and transitions."""

from __future__ import annotations

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "awaiting_teaching_approval": frozenset({"queued", "cancelled"}),
    "queued": frozenset({"planning_forms", "cancelled", "failed_terminal"}),
    "planning_forms": frozenset(
        {"writing_blocks", "failed_recoverable", "failed_terminal", "cancelled"}
    ),
    "writing_blocks": frozenset(
        {"assembling", "failed_recoverable", "failed_terminal", "cancelled"}
    ),
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
ACTIVE_STATUSES = frozenset({"planning_forms", "writing_blocks", "assembling"})
TERMINAL_STATUSES = frozenset(
    {"ready", "completed", "failed_terminal", "cancelled", "rejected_by_teacher"}
)

DEFAULT_VARIANT_ID = "everyone"
DEFAULT_LEASE_SECONDS = 90
HEARTBEAT_INTERVAL_SECONDS = 25
MAX_WRITER_CONCURRENCY = 3
DEFAULT_WORKER_POLL_SECONDS = 2.0


class IllegalTransitionError(ValueError):
    pass


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
