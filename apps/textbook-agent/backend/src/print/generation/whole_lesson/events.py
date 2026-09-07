"""Native whole-lesson progress events."""

from __future__ import annotations

from typing import Any

TOPOLOGY_STARTED = "topology_started"
TOPOLOGY_VALIDATED = "topology_validated"
TOPOLOGY_PERSISTED = "topology_persisted"
TOPOLOGY_DETERMINISTIC_RENDERED = "topology_deterministic_rendered"
TOPOLOGY_QC = "topology_qc"


def make_event(
    event_type: str,
    *,
    generation_id: str,
    section_id: str | None = None,
    block_id: str | None = None,
    position: int | None = None,
    object_id: str | None = None,
    status: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": event_type,
        "generation_id": generation_id,
    }
    if section_id is not None:
        payload["section_id"] = section_id
    if block_id is not None:
        payload["block_id"] = block_id
    if position is not None:
        payload["position"] = position
    if object_id is not None:
        payload["object"] = object_id
    if status is not None:
        payload["status"] = status
    payload.update(extra)
    return payload
