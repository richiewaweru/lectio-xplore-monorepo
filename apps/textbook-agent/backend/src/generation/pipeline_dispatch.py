"""Central active-pipeline selection and persisted identity handling.

Authority for:
- default selection from settings
- persist identity on generation admission
- resolve persisted identity for status/retry/resume
- historical markers are retained as inert metadata and never admitted
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from core.config import GenerationPipeline, settings
from v3_blueprint.planning.persistence import persist_chunked_state

log = logging.getLogger(__name__)

PIPELINE_VERSION = 1
GenerationPipelineName = GenerationPipeline
_HISTORICAL_PIPELINE_MARKERS = frozenset({"v3_studio"})

CONTROL_KEY = "control"


def select_default_pipeline() -> GenerationPipeline:
    return settings.generation_pipeline_default


def pipeline_control_payload(pipeline: GenerationPipeline) -> dict[str, Any]:
    if pipeline != "component_lectio":
        raise ValueError("Only Component Lectio generations can be admitted")
    return {
        "pipeline": pipeline,
        "pipeline_version": PIPELINE_VERSION,
        "selected_at": datetime.now(timezone.utc).isoformat(),
    }


def build_control_patch(pipeline: GenerationPipeline) -> dict[str, Any]:
    return {CONTROL_KEY: pipeline_control_payload(pipeline)}


async def persist_pipeline_identity(
    generation_id: str,
    pipeline: GenerationPipeline,
) -> dict[str, Any]:
    """Persist pipeline into chunked_state_json.control and emit selection event."""
    control = pipeline_control_payload(pipeline)
    await persist_chunked_state(generation_id, {CONTROL_KEY: control})
    log.info(
        "generation_pipeline_selected generation_id=%s pipeline=%s",
        generation_id,
        pipeline,
        extra={
            "event": "generation_pipeline_selected",
            "generation_id": generation_id,
            "pipeline": pipeline,
        },
    )
    return control


def _control_from_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return None
    control = state.get(CONTROL_KEY)
    return control if isinstance(control, dict) else None


def resolve_generation_pipeline(
    state: dict[str, Any] | None,
    *,
    generation_id: str | None = None,
) -> GenerationPipeline | None:
    """Resolve only an active marker; historical rows remain inert.

    A missing or retired marker is intentionally not mapped to the current
    pipeline.  This prevents an old row from being executed accidentally after
    the cutover while allowing callers to distinguish it from a new run.
    """
    control = _control_from_state(state)
    if control is not None:
        raw = control.get("pipeline")
        if raw == "component_lectio":
            return "component_lectio"
        if raw in _HISTORICAL_PIPELINE_MARKERS:
            log.info(
                "generation_pipeline_retired generation_id=%s pipeline=%s",
                generation_id or "unknown",
                raw,
                extra={
                    "event": "generation_pipeline_retired",
                    "generation_id": generation_id,
                    "pipeline": raw,
                },
            )
            return None
    log.info(
        "generation_pipeline_unresolved generation_id=%s reason=missing_marker",
        generation_id or "unknown",
        extra={
            "event": "generation_pipeline_unresolved",
            "generation_id": generation_id,
            "reason": "missing_marker",
        },
    )
    return None


def pipeline_from_state_or_default(state: dict[str, Any] | None) -> GenerationPipeline | None:
    """Return persisted pipeline without inference (None if unmarked)."""
    control = _control_from_state(state)
    if control is None:
        return None
    raw = control.get("pipeline")
    if raw == "component_lectio":
        return "component_lectio"
    return None
