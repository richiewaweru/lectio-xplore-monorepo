"""Adapt the existing visual executor to SharedDocument media work."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from media.generation.contracts import GeneratedVisualBlock, VisualGeneratorWorkOrder
from media.generation.executor import execute_visual

EmitEvent = Callable[[str, dict[str, Any]], Awaitable[None]]


async def _noop_emit(_event_type: str, _payload: dict[str, Any]) -> None:
    """Ignore provider-internal progress; WorkItem lifecycle stays durable."""


@dataclass(frozen=True)
class SharedFigureExecutorAdapter:
    """Use the existing visual provider for one SharedDocument Run.

    The generic media runtime persists claim, checkpoint, completion, and
    failure events.  ``emit_event`` is optional provider-internal progress;
    callers that already have a progress sink may supply it without changing
    provider or retry behavior.
    """

    run_id: str
    emit_event: EmitEvent = _noop_emit

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must be non-empty")

    async def execute_figure(self, order: VisualGeneratorWorkOrder) -> list[GeneratedVisualBlock]:
        """Execute one durable work order with stable Run/work trace IDs."""

        if not isinstance(order, VisualGeneratorWorkOrder):
            raise TypeError("SharedDocument media requires a VisualGeneratorWorkOrder")
        generation_id = f"shared-document:{self.run_id}"
        trace_id = f"{generation_id}:media:{order.work_order_id}"
        return await execute_visual(
            order,
            self.emit_event,
            trace_id=trace_id,
            generation_id=generation_id,
        )


__all__ = ["EmitEvent", "SharedFigureExecutorAdapter"]
