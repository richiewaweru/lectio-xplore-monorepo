"""Adapt the existing visual executor to SharedDocument media work."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from media.generation.contracts import (
    GeneratedVisualBlock,
    VisualGeneratorWorkOrder,
    diagram_visual_style,
)
from media.generation.executor import VisualStageError, execute_visual
from media.render.data_spec import is_data_figure, readable_key, spec_from_data
from media.render.number_guard import format_number, label_numbers_outside_data
from media.render.pipeline import Rendered, Unavailable, render_figure
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
NUMBERS_UNVERIFIED = "figure_numbers_unverified"


def _plain(value: object) -> str:
    return str(value)


def data_value_labels(labels: list[str], data: dict | None) -> list[str]:
    """``labels`` plus one closed label per data point when no label carries a data value.

    The first series is read as the x axis when there are two or more ("Day 7: 12");
    a single series is numbered by position.
    """
    labels = list(labels)
    series = {
        key: values
        for key, values in (data or {}).items()
        if isinstance(values, list) and len(values) >= 2 and all(_is_num(v) for v in values)
    }
    if not series:
        return labels
    values_text = {_plain(v) for values in series.values() for v in values}
    seen = {tok for label in labels for tok in re.findall(r"-?\d+(?:\.\d+)?", label)}
    if seen & values_text:
        return labels
    keys = list(series)
    added: list[str] = []
    if len(keys) == 1:
        name = readable_key(keys[0])
        added = [f"{name} {i + 1}: {_plain(v)}" for i, v in enumerate(series[keys[0]])]
    else:
        x_name = readable_key(keys[0])
        for key in keys[1:]:
            prefix = "" if len(keys) == 2 else f"{readable_key(key)}, "
            for x, y in zip(series[keys[0]], series[key], strict=False):
                added.append(f"{prefix}{x_name} {_plain(x)}: {_plain(y)}")
    return [*labels, *added]


def _is_num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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
    """Route a figure on its plan ``mode``: ``render``, ``diagram`` or ``image``.

    * ``diagram`` and ``image``: straight to the image-model delegate (routes
      ``diagram`` / ``image``); the spec builder is never called.
    * ``render``: drawn by code. (1) the LLM spec builder picks the family
      (``llm_family:<name>``); (2) if it fails, returns none or is invalid and the
      figure has series data that forms a table, a code table is drawn
      (``render_table_fallback``); (3) otherwise the delegate draws it as a
      ``diagram`` order: ``render_fallback_diagram`` without series data, and
      ``render_fallback_diagram_unverified`` (with a ``figure_numbers_unverified``
      warning, the data values added as closed labels) with series data.
    * Series data on a non-render mode (old plans) is routed as ``render``.
    """

    delegate: SharedFigureExecutorAdapter
    builder_factory: SpecBuilderFactory = _default_builder_factory

    async def _delegate(
        self,
        order: VisualGeneratorWorkOrder,
        route: str,
        reason: str,
        *,
        as_diagram: bool = False,
        warnings: tuple[str, ...] = (),
    ) -> list[GeneratedVisualBlock]:
        _log_route(order, route, reason)
        send = order
        if as_diagram:
            visual = order.visual
            labels = data_value_labels(visual.labels_required, visual.data)
            send = order.model_copy(
                update={
                    "visual": visual.model_copy(
                        update={
                            "mode": "diagram",
                            "labels_required": labels,
                            "visual_style": diagram_visual_style(labels),
                        }
                    )
                }
            )
        blocks = await self.delegate.execute_figure(send)
        # Blocks keep the plan's mode so the media result matches the frozen order.
        return [
            block.model_copy(
                update={
                    "render_route": route,
                    "mode": order.visual.mode,
                    "render_warnings": [*block.render_warnings, *warnings],
                }
            )
            for block in blocks
        ]

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

        if not data_figure and visual.mode in {"diagram", "image"}:
            return await self._delegate(order, visual.mode, f"mode_{visual.mode}")

        # Render path (mode "render", or series data whatever the mode).
        if data_figure:
            outside = label_numbers_outside_data(order)
            if outside:
                shown = ", ".join(format_number(n) for n in outside[:5])
                return self._data_failure(
                    order,
                    f"label_number_not_in_data:{shown}",
                    f"labels or must_show carry numbers not in the figure data: {shown}",
                )

        outcome = await render_figure(order, builder=self.builder_factory(trace_id, generation_id))
        if isinstance(outcome, Rendered):
            return await self._stored(
                order,
                outcome,
                generation_id=generation_id,
                route=f"llm_family:{outcome.figure.family}",
                reason="spec_builder",
            )
        if isinstance(outcome, Unavailable):
            reason = f"builder_unavailable: {outcome.code}"
        else:
            reason = outcome.reason

        if data_figure:
            spec = spec_from_data(data, visual.labels_required, visual.must_show)
            if spec is not None:
                table = await render_figure(order, prebuilt=spec)
                if isinstance(table, Rendered):
                    return await self._stored(
                        order,
                        table,
                        generation_id=generation_id,
                        route="render_table_fallback",
                        reason=reason,
                    )
                if isinstance(table, Unavailable):
                    reason = f"{reason}; table_rejected: {table.code}"
            else:
                reason = f"{reason}; data_not_a_series_table"
            return await self._delegate(
                order,
                "render_fallback_diagram_unverified",
                reason,
                as_diagram=True,
                warnings=(NUMBERS_UNVERIFIED,),
            )

        return await self._delegate(order, "render_fallback_diagram", reason, as_diagram=True)


__all__ = [
    "EmitEvent",
    "RoutingFigureExecutor",
    "SharedFigureExecutorAdapter",
]
