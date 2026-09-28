"""Units-owned dispatch seam for persisted Learn generations.

The ordinary component Lectio execution path is retired. Active Learn unit
generation realizes a verified, read-only SharedLessonDocument through
``learn.generation.shared_document_execution.execute_learn_realization_from_shared_document``
after shared teaching approval; it never authors ordinary content or selects
an interaction via an LLM. This module rejects retired markers and refuses to
launch the deleted package.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from learn.generation.pipeline_dispatch import (
    COMPONENT_LECTIO_RETIRED,
    resolve_generation_pipeline,
)

_tasks: dict[str, asyncio.Task[None]] = {}
log = logging.getLogger(__name__)


async def dispatch_units_generation(
    *, generation_id: str, user_id: str, state: dict[str, Any]
) -> str:
    """Refuse retired Component Lectio launches; document path is elsewhere."""
    _ = user_id
    pipeline = resolve_generation_pipeline(state, generation_id=generation_id)
    if pipeline is None:
        raise ValueError(COMPONENT_LECTIO_RETIRED)
    # Active markers admit identity only; production runs through the
    # verified SharedLessonDocument Learn realization after teaching
    # approval, not this launcher.
    raise ValueError(
        "Use the SharedLessonDocument Learn realization path "
        "(execute_learn_realization_from_shared_document); "
        "direct Units component execution is retired"
    )


def units_dispatch_task(generation_id: str) -> asyncio.Task[None] | None:
    return _tasks.get(generation_id)


__all__ = ["dispatch_units_generation", "units_dispatch_task"]
