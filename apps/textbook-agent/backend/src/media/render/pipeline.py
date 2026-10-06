"""Figure request -> spec -> validate -> repair -> draw.

Once a family is chosen the figure is code-rendered or unavailable; it never
falls back to an image model. Only "no family chosen" outcomes are Fallback.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from media.generation.contracts import VisualGeneratorWorkOrder
from media.render.contracts import RenderLayoutError, RenderSpecError
from media.render.export import RenderedFigure, render_spec
from media.render.families import RENDERERS
from media.render.spec_builder import SpecBuilder
from media.render.validate import cross_check_numbers, validate_spec

logger = logging.getLogger(__name__)

MAX_REPAIRS = 2


@dataclass(frozen=True)
class Rendered:
    figure: RenderedFigure
    spec: object
    warnings: list[str]
    attempts: int


@dataclass(frozen=True)
class Fallback:
    reason: str


@dataclass(frozen=True)
class Unavailable:
    code: str
    errors: list[dict[str, str]]
    attempts: int


RenderOutcome = Rendered | Fallback | Unavailable


def _fallback(order: VisualGeneratorWorkOrder, reason: str) -> Fallback:
    logger.info(
        "render_family_fallback",
        extra={
            "event": "render_family_fallback",
            "work_order_id": order.work_order_id,
            "purpose": order.visual.purpose,
            "reason": reason,
        },
    )
    return Fallback(reason)


def _unavailable(
    order: VisualGeneratorWorkOrder,
    code: str,
    errors: list[dict[str, str]],
    attempts: int,
) -> Unavailable:
    logger.warning(
        "render_unavailable",
        extra={
            "event": "render_unavailable",
            "work_order_id": order.work_order_id,
            "code": code,
            "attempts": attempts,
        },
    )
    return Unavailable(code, errors, attempts)


async def render_figure(order: VisualGeneratorWorkOrder, *, builder: SpecBuilder) -> RenderOutcome:
    try:
        result = await builder.build(order)
    except Exception as exc:
        return _fallback(order, f"spec_builder_failed: {type(exc).__name__}")

    if result.family == "none" or result.spec is None:
        return _fallback(order, f"no_family: {result.reason}")
    if result.family not in RENDERERS:
        return _fallback(order, f"family_not_implemented: {result.family}")

    family = result.family
    attempts = 1
    repairs = 0
    while True:
        spec = result.spec
        errors = validate_spec(spec)
        if not errors:
            try:
                figure = await asyncio.to_thread(render_spec, spec)
            except RenderLayoutError as exc:
                return _unavailable(
                    order,
                    "render_layout_failed",
                    [RenderSpecError("render_layout_failed", "spec", str(exc)).as_dict()],
                    attempts,
                )
            warnings = cross_check_numbers(spec, [e.text for e in order.source_of_truth])
            logger.info(
                "render_figure_rendered",
                extra={
                    "event": "render_figure_rendered",
                    "work_order_id": order.work_order_id,
                    "family": family,
                    "attempts": attempts,
                    "warnings": len(warnings),
                },
            )
            return Rendered(figure=figure, spec=spec, warnings=warnings, attempts=attempts)

        error_dicts = [e.as_dict() for e in errors]
        if repairs >= MAX_REPAIRS:
            return _unavailable(order, "render_spec_invalid", error_dicts, attempts)
        repairs += 1
        try:
            repaired = await builder.repair(order, result, errors)
        except Exception:
            return _unavailable(order, "render_spec_invalid", error_dicts, attempts)
        attempts += 1
        if repaired.family == "none" or repaired.spec is None or repaired.family != family:
            return _unavailable(order, "render_spec_invalid", error_dicts, attempts)
        result = repaired


__all__ = [
    "MAX_REPAIRS",
    "Fallback",
    "RenderOutcome",
    "Rendered",
    "Unavailable",
    "render_figure",
]
