"""Durable checkpoint / resume helpers on generation_steps fold semantics (Phase 06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockState = Literal["pending", "running", "ready", "repairing", "failed"]
GenState = Literal[
    "queued",
    "running",
    "waiting_for_teacher",
    "complete",
    "failed",
    "cancelled",
]


@dataclass
class BlockCheckpoint:
    block_id: str
    plan_revision: int
    plan_hash: str
    state: BlockState
    payload: dict[str, Any] = field(default_factory=dict)
    last_error: dict[str, Any] | None = None


@dataclass
class GenerationControlState:
    generation_id: str
    state: GenState
    plan_revision: int
    plan_hash: str
    desired_work: list[str] = field(default_factory=list)


@dataclass
class CheckpointStore:
    """In-memory stand-in mirroring append-only generation_steps fold semantics."""

    control: GenerationControlState
    blocks: dict[str, BlockCheckpoint] = field(default_factory=dict)
    _seq: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def append_step(self, step_type: str, payload: dict[str, Any]) -> None:
        self._seq += 1
        self.events.append({"seq": self._seq, "type": step_type, "payload": payload})

    def mark_block_ready(
        self,
        block_id: str,
        *,
        plan_revision: int,
        plan_hash: str,
        payload: dict[str, Any],
    ) -> None:
        existing = self.blocks.get(block_id)
        if existing and existing.state == "ready" and existing.plan_hash == plan_hash:
            # Idempotent: duplicate ready is a no-op.
            self.append_step("block_ready_duplicate", {"block_id": block_id})
            return
        if existing and existing.plan_revision > plan_revision:
            raise ValueError("stale plan revision rejected")
        self.blocks[block_id] = BlockCheckpoint(
            block_id=block_id,
            plan_revision=plan_revision,
            plan_hash=plan_hash,
            state="ready",
            payload=payload,
        )
        self.append_step("block_ready", {"block_id": block_id, "plan_hash": plan_hash})

    def mark_terminal(self, state: GenState, *, error: dict[str, Any] | None = None) -> None:
        if state not in {"complete", "failed", "cancelled"}:
            raise ValueError("terminal state required")
        self.control.state = state
        self.append_step("generation_terminal", {"state": state, "error": error})

    def missing_or_retryable(self) -> list[str]:
        missing: list[str] = []
        for block_id in self.control.desired_work:
            checkpoint = self.blocks.get(block_id)
            if checkpoint is None or checkpoint.state in {"pending", "failed", "repairing"}:
                missing.append(block_id)
        return missing

    def reconstruct(self) -> dict[str, Any]:
        """Reconstruct progress from append-only events + folded block map."""
        return {
            "generation_id": self.control.generation_id,
            "state": self.control.state,
            "plan_revision": self.control.plan_revision,
            "plan_hash": self.control.plan_hash,
            "ready_blocks": sorted(
                block_id
                for block_id, checkpoint in self.blocks.items()
                if checkpoint.state == "ready"
            ),
            "pending_blocks": self.missing_or_retryable(),
            "event_count": len(self.events),
        }


def resume_after_crash(store: CheckpointStore) -> list[str]:
    """Only schedule missing/retryable work — never regenerate ready siblings."""
    if store.control.state in {"complete", "cancelled"}:
        return []
    store.control.state = "running"
    return store.missing_or_retryable()
