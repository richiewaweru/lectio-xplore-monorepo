"""Adapt the existing visual executor to SharedDocument media work."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from media.generation.contracts import GeneratedVisualBlock, VisualGeneratorWorkOrder
from media.generation.executor import VisualStageError, execute_visual
from media.render.pipeline import Fallback, Rendered, Unavailable, render_figure
from media.render.spec_builder import LlmSpecBuilder, SpecBuilder

logger = logging.getLogger(__name__)

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
        try:
            UUID(self.run_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("run_id must be a UUID") from exc

    async def execute_figure(self, order: VisualGeneratorWorkOrder) -> list[GeneratedVisualBlock]:
        """Execute one durable work order with stable Run/work trace IDs."""

        if not isinstance(order, VisualGeneratorWorkOrder):
            raise TypeError("SharedDocument media requires a VisualGeneratorWorkOrder")
        canonical_run_id = str(UUID(self.run_id))
        generation_id = f"shared-document-{canonical_run_id}"
        trace_id = f"shared-document:{canonical_run_id}:media:{order.work_order_id}"
        return await execute_visual(
            order,
            self.emit_event,
            trace_id=trace_id,
            generation_id=generation_id,
        )


def render_figures_mode() -> str:
    """``LECTIO_RENDER_FIGURES``: "off" (default) or "auto"; unknown -> "off"."""

    raw = (os.environ.get("LECTIO_RENDER_FIGURES") or "off").strip().lower()
    return raw if raw == "auto" else "off"


SpecBuilderFactory = Callable[[str, str], SpecBuilder]


def _default_builder_factory(trace_id: str, generation_id: str) -> SpecBuilder:
    return LlmSpecBuilder(trace_id=trace_id, generation_id=generation_id)


def _summarize_errors(errors: list[dict[str, str]], limit: int = 3) -> str:
    parts = [
        f"{e.get('code', 'error')}@{e.get('path', '?')}: {e.get('message', '')}"
        for e in errors[:limit]
    ]
    return "; ".join(parts)[:500] or "render spec invalid"


@dataclass(frozen=True)
class RoutingFigureExecutor:
    """Code-render exact ``diagram`` figures; delegate everything else.

    A figure whose family was chosen but stayed invalid fails (never falls
    back to an image model). "No family fits" falls back to the delegate.
    """

    delegate: SharedFigureExecutorAdapter
    builder_factory: SpecBuilderFactory = _default_builder_factory

    async def execute_figure(self, order: VisualGeneratorWorkOrder) -> list[GeneratedVisualBlock]:
        if render_figures_mode() != "auto" or order.visual.mode != "diagram":
            return await self.delegate.execute_figure(order)
        if not isinstance(order, VisualGeneratorWorkOrder):
            raise TypeError("SharedDocument media requires a VisualGeneratorWorkOrder")

        canonical_run_id = str(UUID(self.delegate.run_id))
        generation_id = f"shared-document-{canonical_run_id}"
        trace_id = f"shared-document:{canonical_run_id}:media:{order.work_order_id}"
        outcome = await render_figure(order, builder=self.builder_factory(trace_id, generation_id))

        if isinstance(outcome, Fallback):
            return await self.delegate.execute_figure(order)
        if isinstance(outcome, Unavailable):
            return [
                GeneratedVisualBlock(
                    visual_id=order.visual.id,
                    attaches_to=order.visual.attaches_to,
                    mode=order.visual.mode,
                    caption=order.visual.purpose,
                    source_work_order_id=order.work_order_id,
                    component_id=order.visual.component_id,
                    status="failed",
                    error_code=outcome.code,
                    error_message=_summarize_errors(outcome.errors),
                )
            ]

        assert isinstance(outcome, Rendered)
        from media.storage.image_store import get_image_store

        figure = outcome.figure
        stem = f"{generation_id}/{order.visual.attaches_to or 'visuals'}/{order.visual.id}"
        try:
            store = get_image_store()
            svg_url = await store.store_image_key(
                key=f"{stem}.svg", image_bytes=figure.svg, content_type="image/svg+xml"
            )
            png_url = await store.store_image_key(
                key=f"{stem}.png", image_bytes=figure.png, content_type="image/png"
            )
        except Exception as exc:
            raise VisualStageError.from_exception(stage="gcs_upload", exc=exc) from exc
        warnings = list(outcome.warnings)
        logger.info(
            "shared_figure_code_rendered",
            extra={
                "event": "shared_figure_code_rendered",
                "work_order_id": order.work_order_id,
                "family": figure.family,
                "warnings": len(warnings),
            },
        )
        return [
            GeneratedVisualBlock(
                visual_id=order.visual.id,
                attaches_to=order.visual.attaches_to,
                mode=order.visual.mode,
                image_url=svg_url,
                fallback_image_url=png_url,
                alt_text=figure.alt_text,
                caption=order.visual.purpose,
                source_work_order_id=order.work_order_id,
                component_id=order.visual.component_id,
                status="ready_with_quality_warning" if warnings else "ready",
                qc_state="unreviewed",
                qc_reasons=warnings,
                # Binding only trusts alt text carried on a single ``ALT:`` line.
                provider_text=f"ALT: {' '.join(figure.alt_text.split())}"
                if figure.alt_text
                else None,
            )
        ]


__all__ = [
    "EmitEvent",
    "RoutingFigureExecutor",
    "SharedFigureExecutorAdapter",
    "render_figures_mode",
]
