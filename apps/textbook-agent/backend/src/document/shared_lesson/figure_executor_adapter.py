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
from media.render.data_spec import is_data_figure, spec_from_data
from media.render.number_guard import format_number, label_numbers_outside_data
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
    """``LECTIO_RENDER_FIGURES``: "auto" (default) or "off" (the kill switch)."""

    raw = (os.environ.get("LECTIO_RENDER_FIGURES") or "auto").strip().lower()
    return "off" if raw in {"off", "0", "false", "no"} else "auto"


SpecBuilderFactory = Callable[[str, str], SpecBuilder]


def _default_builder_factory(trace_id: str, generation_id: str) -> SpecBuilder:
    return LlmSpecBuilder(trace_id=trace_id, generation_id=generation_id)


def _summarize_errors(errors: list[dict[str, str]], limit: int = 3) -> str:
    parts = [
        f"{e.get('code', 'error')}@{e.get('path', '?')}: {e.get('message', '')}"
        for e in errors[:limit]
    ]
    return "; ".join(parts)[:500] or "render spec invalid"


DATA_NOT_RENDERED = "figure_data_not_rendered"


def _log_route(order: VisualGeneratorWorkOrder, route: str, reason: str) -> None:
    logger.info(
        "figure_route",
        extra={
            "event": "figure_route",
            "figure_id": order.visual.id,
            "section_id": order.visual.attaches_to or None,
            "work_order_id": order.work_order_id,
            "route": route,
            "reason": reason,
            "data_present": bool(order.visual.data),
        },
    )


def _failed_block(
    order: VisualGeneratorWorkOrder, code: str, message: str
) -> list[GeneratedVisualBlock]:
    return [
        GeneratedVisualBlock(
            visual_id=order.visual.id,
            attaches_to=order.visual.attaches_to,
            mode=order.visual.mode,
            caption=order.visual.purpose,
            source_work_order_id=order.work_order_id,
            component_id=order.visual.component_id,
            status="failed",
            error_code=code,
            error_message=message,
            render_route="failed",
        )
    ]


@dataclass(frozen=True)
class RoutingFigureExecutor:
    """Code-render data figures and exact ``diagram`` figures; delegate the rest.

    Order of attempts:

    1. figure data that forms a clean set of series: a table built by code
       (route ``data_table``), whatever ``LECTIO_RENDER_FIGURES`` says;
    2. a data figure (a series of two or more numbers): the LLM spec builder
       (route ``llm_family:<name>``), whatever the flag or mode says;
    3. a data figure still not drawn FAILS (``figure_data_not_rendered``) and is
       never delegated to the image model, which would invent numbers;
    4. anything else follows the old rules: the flag and mode gate the spec
       builder, and "no family fits" falls back to the delegate (route
       ``image_label_only`` for scalar-only data, ``image`` otherwise).

    A figure whose family was chosen but stayed invalid fails (never falls
    back to an image model).
    """

    delegate: SharedFigureExecutorAdapter
    builder_factory: SpecBuilderFactory = _default_builder_factory

    async def _delegate(
        self, order: VisualGeneratorWorkOrder, reason: str
    ) -> list[GeneratedVisualBlock]:
        route = "image_label_only" if order.visual.data else "image"
        _log_route(order, route, reason)
        blocks = await self.delegate.execute_figure(order)
        return [block.model_copy(update={"render_route": route}) for block in blocks]

    async def _stored(
        self,
        order: VisualGeneratorWorkOrder,
        outcome: Rendered,
        *,
        generation_id: str,
        route: str,
        reason: str,
    ) -> list[GeneratedVisualBlock]:
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
        _log_route(order, route, reason)
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
                render_route=route,
            )
        ]

    def _data_failure(
        self, order: VisualGeneratorWorkOrder, reason: str, detail: str
    ) -> list[GeneratedVisualBlock]:
        _log_route(order, "failed", f"{DATA_NOT_RENDERED}: {reason}")
        return _failed_block(order, DATA_NOT_RENDERED, detail[:500] or reason)

    async def execute_figure(self, order: VisualGeneratorWorkOrder) -> list[GeneratedVisualBlock]:
        if not isinstance(order, VisualGeneratorWorkOrder):
            raise TypeError("SharedDocument media requires a VisualGeneratorWorkOrder")

        visual = order.visual
        data = visual.data
        data_figure = is_data_figure(data)
        canonical_run_id = str(UUID(self.delegate.run_id))
        generation_id = f"shared-document-{canonical_run_id}"
        trace_id = f"shared-document:{canonical_run_id}:media:{order.work_order_id}"

        if data_figure:
            outside = label_numbers_outside_data(order)
            if outside:
                shown = ", ".join(format_number(n) for n in outside[:5])
                return self._data_failure(
                    order,
                    f"label_number_not_in_data:{shown}",
                    f"labels or must_show carry numbers not in the figure data: {shown}",
                )

        reason = "no_data"
        if data:
            spec = spec_from_data(data, visual.labels_required, visual.must_show)
            if spec is not None:
                outcome = await render_figure(order, prebuilt=spec)
                if isinstance(outcome, Rendered):
                    return await self._stored(
                        order,
                        outcome,
                        generation_id=generation_id,
                        route="data_table",
                        reason="spec_from_data",
                    )
                reason = (
                    f"prebuilt_table_rejected: {outcome.code}"
                    if isinstance(outcome, Unavailable)
                    else "prebuilt_table_rejected"
                )
            else:
                reason = "data_not_a_series_table"

        if data_figure:
            outcome = await render_figure(
                order, builder=self.builder_factory(trace_id, generation_id)
            )
            if isinstance(outcome, Rendered):
                return await self._stored(
                    order,
                    outcome,
                    generation_id=generation_id,
                    route=f"llm_family:{outcome.figure.family}",
                    reason=reason,
                )
            if isinstance(outcome, Unavailable):
                return self._data_failure(order, outcome.code, _summarize_errors(outcome.errors))
            return self._data_failure(order, outcome.reason, f"no drawing: {outcome.reason}")

        if render_figures_mode() != "auto":
            return await self._delegate(order, "render_figures_off")
        if visual.mode != "diagram":
            return await self._delegate(order, f"mode_{visual.mode}")

        outcome = await render_figure(order, builder=self.builder_factory(trace_id, generation_id))
        if isinstance(outcome, Fallback):
            return await self._delegate(order, outcome.reason)
        if isinstance(outcome, Unavailable):
            _log_route(order, "failed", outcome.code)
            return _failed_block(order, outcome.code, _summarize_errors(outcome.errors))

        assert isinstance(outcome, Rendered)
        return await self._stored(
            order,
            outcome,
            generation_id=generation_id,
            route=f"llm_family:{outcome.figure.family}",
            reason=reason,
        )


__all__ = [
    "EmitEvent",
    "RoutingFigureExecutor",
    "SharedFigureExecutorAdapter",
    "render_figures_mode",
]
