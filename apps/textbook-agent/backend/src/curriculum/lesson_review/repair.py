"""Bounded targeted repair helpers for named lesson nodes/tasks/figures."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from curriculum.agents import _run_structured
from curriculum.prompts import targeted_lesson_repair_prompt
from infra.authoring.model_policy import V3_TARGETED_LESSON_REPAIR

from .models import RepairEvent, RepairTarget


class TargetedRepairDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]


async def run_targeted_repair(
    *,
    path: str,
    target: RepairTarget,
    current_payload: dict[str, Any],
    issue_codes: list[str],
    trace_id: str | None = None,
) -> tuple[dict[str, Any], RepairEvent]:
    """Repair one named target and return an auditable event."""
    try:
        draft = await _run_structured(
            node=V3_TARGETED_LESSON_REPAIR,
            caller="v3_targeted_lesson_repair",
            output_type=TargetedRepairDraft,
            system_prompt=targeted_lesson_repair_prompt(),
            user_payload={
                "path": path,
                "target": target.model_dump(mode="json"),
                "issue_codes": issue_codes,
                "current_payload": current_payload,
            },
            trace_id=trace_id,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        return current_payload, RepairEvent(
            path=path, attempt=1, target=target, issue_codes=issue_codes,
            status="failed", message=str(exc),
        )
    return draft.payload, RepairEvent(
        path=path, attempt=1, target=target, issue_codes=issue_codes,
        status="completed", message="targeted repair returned a replacement payload",
    )


def enforce_repair_cap(targets: list[RepairTarget], *, max_targets: int = 3) -> list[RepairTarget]:
    if max_targets < 0:
        raise ValueError("max_targets must be non-negative")
    return targets[:max_targets]


__all__ = ["TargetedRepairDraft", "enforce_repair_cap", "run_targeted_repair"]
