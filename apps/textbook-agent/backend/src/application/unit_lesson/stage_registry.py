"""Domain-owned generation stage graphs (P02 G05).

Print worker transitions live in ``print.generation.whole_lesson.states``.
Learn uses a smaller explicit graph. Approval waits are teacher gates, not
worker leases — they appear in the graph but are never claimable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PathName = Literal["print", "learn"]

# Teacher gate — never leased by a worker.
APPROVAL_WAIT_STAGES: frozenset[str] = frozenset(
    {
        "awaiting_teaching_approval",
        "awaiting_review",
    }
)


@dataclass(frozen=True, slots=True)
class StageDefinition:
    """One registered stage in a path-owned graph."""

    stage_id: str
    path: PathName
    worker_claimable: bool
    approval_wait: bool
    terminal: bool
    allowed_next: frozenset[str]


def _print_stages() -> dict[str, StageDefinition]:
    from print.generation.whole_lesson.states import LEGAL_TRANSITIONS

    terminal = frozenset({"failed_terminal", "cancelled", "completed", "rejected_by_teacher"})
    # ready is nearly terminal but may reopen visuals under repository fence.
    out: dict[str, StageDefinition] = {}
    for stage_id, nxt in LEGAL_TRANSITIONS.items():
        approval = stage_id in APPROVAL_WAIT_STAGES
        claimable = not approval and stage_id not in terminal and stage_id != "ready"
        # failed_recoverable is resume-eligible but not claimable until re-queued.
        if stage_id == "failed_recoverable":
            claimable = False
        out[stage_id] = StageDefinition(
            stage_id=stage_id,
            path="print",
            worker_claimable=claimable,
            approval_wait=approval,
            terminal=stage_id in terminal,
            allowed_next=frozenset(nxt),
        )
    return out


# Learn path after admission: queued → running → ready|failed.
# Composition/write checkpoints are work-item local (P03), not separate leased stages.
LEARN_LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "cancelled", "failed"}),
    "running": frozenset({"ready", "failed", "cancelled"}),
    "ready": frozenset(),
    "failed": frozenset({"queued", "cancelled"}),
    "cancelled": frozenset(),
}


def _learn_stages() -> dict[str, StageDefinition]:
    terminal = frozenset({"ready", "cancelled"})
    out: dict[str, StageDefinition] = {}
    for stage_id, nxt in LEARN_LEGAL_TRANSITIONS.items():
        out[stage_id] = StageDefinition(
            stage_id=stage_id,
            path="learn",
            worker_claimable=stage_id in {"queued", "running"},
            approval_wait=False,
            terminal=stage_id in terminal and stage_id != "failed",
            allowed_next=frozenset(nxt),
        )
    return out


_PRINT = _print_stages()
_LEARN = _learn_stages()
_BY_PATH: dict[PathName, dict[str, StageDefinition]] = {
    "print": _PRINT,
    "learn": _LEARN,
}


class UnknownStageError(ValueError):
    """Stage id is not registered for the path."""


class IllegalStageTransitionError(ValueError):
    """Transition is not in the path-owned graph."""


def get_stage(path: PathName, stage_id: str) -> StageDefinition:
    graph = _BY_PATH.get(path)
    if graph is None:
        raise UnknownStageError(f"Unknown path: {path}")
    stage = graph.get(stage_id)
    if stage is None:
        raise UnknownStageError(f"Unknown stage '{stage_id}' for path '{path}'")
    return stage


def assert_transition(path: PathName, current: str, nxt: str) -> None:
    stage = get_stage(path, current)
    if nxt not in stage.allowed_next:
        # Allow identity lookup of target so unknown next also raises UnknownStage.
        get_stage(path, nxt)
        raise IllegalStageTransitionError(
            f"Illegal {path} transition {current!r} -> {nxt!r}"
        )


def is_approval_wait(path: PathName, stage_id: str) -> bool:
    return get_stage(path, stage_id).approval_wait


def is_worker_claimable(path: PathName, stage_id: str) -> bool:
    return get_stage(path, stage_id).worker_claimable


def list_stages(path: PathName) -> tuple[StageDefinition, ...]:
    return tuple(_BY_PATH[path].values())


def active_entrypoint_map() -> dict[str, tuple[str, ...]]:
    """Map product entrypoints to the stages they may start or resume."""
    return {
        "realize_print_from_preparation": ("queued", "awaiting_teaching_approval"),
        "realize_learn_from_preparation": ("queued", "running", "ready"),
        "print_worker_claim": tuple(
            s.stage_id for s in _PRINT.values() if s.worker_claimable
        ),
        "learn_produce": ("queued", "running"),
    }


__all__ = [
    "APPROVAL_WAIT_STAGES",
    "LEARN_LEGAL_TRANSITIONS",
    "IllegalStageTransitionError",
    "StageDefinition",
    "UnknownStageError",
    "active_entrypoint_map",
    "assert_transition",
    "get_stage",
    "is_approval_wait",
    "is_worker_claimable",
    "list_stages",
]
