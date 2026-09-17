"""Revision-bound Smart Lesson artifacts stored in existing generation state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from v3_blueprint.planning.persistence import persist_chunked_state

from .models import CoherenceReport, RepairEvent


def smart_artifact_payload(
    *,
    flow_choice: Mapping[str, Any] | None = None,
    sourcebook: Any | None = None,
    shared_tasks: Sequence[Any] = (),
    bindings: Sequence[Any] = (),
    print_report: CoherenceReport | None = None,
    learn_report: CoherenceReport | None = None,
    repair_events: Sequence[RepairEvent] = (),
) -> dict[str, Any]:
    """Serialize all A–H evidence without creating another persistence table."""
    return {
        "flow_choice": dict(flow_choice or {}),
        "lesson_sourcebook": sourcebook.model_dump(mode="json") if hasattr(sourcebook, "model_dump") else sourcebook,
        "shared_tasks": [item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item) for item in shared_tasks],
        "teaching_content_bindings": [item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item) for item in bindings],
        "coherence_reports": {
            "print": print_report.model_dump(mode="json") if print_report else None,
            "learn": learn_report.model_dump(mode="json") if learn_report else None,
        },
        "repair_events": [item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item) for item in repair_events],
    }


def invalidate_stale_smart_artifacts(
    state: Mapping[str, Any],
    *,
    teaching_plan_id: str,
    teaching_plan_revision: int,
    teaching_plan_hash: str,
) -> dict[str, Any]:
    """Drop Smart artifacts from another approved revision while retaining other state."""
    out = dict(state)
    existing = out.get("smart_lesson")
    if not isinstance(existing, Mapping):
        return out
    identity = (
        str(existing.get("teaching_plan_id") or ""),
        int(existing.get("teaching_plan_revision") or 0),
        str(existing.get("teaching_plan_hash") or ""),
    )
    wanted = (teaching_plan_id, int(teaching_plan_revision), teaching_plan_hash)
    if identity != wanted:
        out.pop("smart_lesson", None)
    return out


async def persist_smart_lesson_artifacts(
    generation_id: str,
    *,
    teaching_plan_id: str,
    teaching_plan_revision: int,
    teaching_plan_hash: str,
    session: Any | None = None,
    **artifacts: Any,
) -> None:
    payload = smart_artifact_payload(**artifacts)
    payload.update({
        "teaching_plan_id": teaching_plan_id,
        "teaching_plan_revision": teaching_plan_revision,
        "teaching_plan_hash": teaching_plan_hash,
    })
    await persist_chunked_state(generation_id, {"smart_lesson": payload}, session=session)


__all__ = ["invalidate_stale_smart_artifacts", "persist_smart_lesson_artifacts", "smart_artifact_payload"]
