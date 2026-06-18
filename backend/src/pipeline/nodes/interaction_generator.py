"""
interaction_generator node.

Graph-visible compatibility shim delegating to the media simulation executor.
"""

from __future__ import annotations

import core.events as core_events  # noqa: F401

from pipeline.media.executors.simulation_generator import (
    build_interaction_spec,
    simulation_generator as execute_simulation_generator,
)
from pipeline.state import TextbookPipelineState

__all__ = ["build_interaction_spec", "interaction_generator", "core_events"]


async def interaction_generator(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
) -> dict:
    return await execute_simulation_generator(
        state,
        model_overrides=model_overrides,
    )
