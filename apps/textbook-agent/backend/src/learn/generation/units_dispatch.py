"""Units-owned dispatch seam for persisted Learn generations.

The ordinary component Lectio execution path is retired. Active Learn unit
generation uses the LearnDocument v2 / native_learn document path via
``produce_learn_from_approved_teaching`` after shared teaching approval.
This module rejects retired markers and refuses to launch the deleted package.
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
    # Active markers admit identity only; production runs through native
    # document execution after teaching approval, not this launcher.
    raise ValueError(
        "Use the learn document path (produce_learn_from_approved_teaching); "
        "direct Units component execution is retired"
    )


def units_dispatch_task(generation_id: str) -> asyncio.Task[None] | None:
    return _tasks.get(generation_id)


__all__ = ["dispatch_units_generation", "units_dispatch_task"]
