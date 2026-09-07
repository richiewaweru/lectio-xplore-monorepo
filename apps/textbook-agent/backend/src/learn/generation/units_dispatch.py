"""Units-owned dispatch seam for persisted Component Lectio generations."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from generation.pipeline_dispatch import resolve_generation_pipeline
from generation.component_lectio.launcher import launch_component_lectio
from generation.component_lectio.service import (
    persist_component_lectio_failure,
    persist_component_lectio_start,
)

_tasks: dict[str, asyncio.Task[None]] = {}
log = logging.getLogger(__name__)


async def _run_units_generation(generation_id: str) -> None:
    try:
        await launch_component_lectio(generation_id=generation_id)
    except Exception as exc:  # noqa: BLE001
        log.error(
            "units_component_lectio_failed generation_id=%s error_type=%s",
            generation_id,
            type(exc).__name__,
        )
        try:
            await persist_component_lectio_failure(generation_id, exc)
        except Exception:  # noqa: BLE001
            log.exception(
                "units_component_lectio_failure_persist_failed generation_id=%s", generation_id
            )


async def dispatch_units_generation(
    *, generation_id: str, user_id: str, state: dict[str, Any]
) -> str:
    """Start the persisted pipeline without allowing a Studio fallback."""
    pipeline = resolve_generation_pipeline(state, generation_id=generation_id)
    if pipeline != "component_lectio":
        raise ValueError("This Units generation is not admitted to Component Lectio")
    existing = _tasks.get(generation_id)
    if existing is None or existing.done():
        await persist_component_lectio_start(generation_id)
        _tasks[generation_id] = asyncio.create_task(_run_units_generation(generation_id))
    return pipeline


def units_dispatch_task(generation_id: str) -> asyncio.Task[None] | None:
    return _tasks.get(generation_id)


__all__ = ["dispatch_units_generation", "units_dispatch_task"]
