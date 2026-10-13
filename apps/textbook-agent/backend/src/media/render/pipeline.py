"""Figure request -> spec -> validate -> repair -> draw.

Once a family is chosen the figure is code-rendered or unavailable; it never
falls back to an image model. Only "no family chosen" outcomes are Fallback.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from media.generation.contracts import VisualGeneratorWorkOrder
from media.render.contracts import RenderLayoutError, RenderSpec, RenderSpecError
from media.render.export import RenderedFigure, render_spec
from media.render.families import RENDERERS
from media.render.number_guard import allowed_numbers, format_number, unsupported_numbers
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


def _spec_errors(order: VisualGeneratorWorkOrder, spec: object) -> list[RenderSpecError]:
    """Structural errors, then numbers that neither the data nor an approved fact holds."""
    errors = validate_spec(spec)
    if errors:
        return errors
    renderer = RENDERERS.get(str(getattr(spec, "family", "")))
    if renderer is None:
        return []
    bad = unsupported_numbers(renderer.numbers(spec), allowed_numbers(order))
    return [
        RenderSpecError(
            f"number_not_in_data:{format_number(value)}",
            "spec",
            f"{format_number(value)} is not in the figure's data or approved facts",
        )
        for value in bad
    ]


async def _draw(
    order: VisualGeneratorWorkOrder, spec: object, family: str, attempts: int
) -> Rendered | Unavailable:
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


async def render_figure(
    order: VisualGeneratorWorkOrder,
    *,
    builder: SpecBuilder | None = None,
    prebuilt: RenderSpec | None = None,
) -> RenderOutcome:
    """Render one figure.

    A ``prebuilt`` spec (built by code from the figure's data) is tried first and
    never repaired: if it fails validation or the number guard the figure is
    ``Unavailable``. Otherwise ``builder`` writes the spec and the repair loop
    applies. Every spec passes the number guard before it is drawn.
    """
    if prebuilt is not None:
        errors = _spec_errors(order, prebuilt)
        if errors:
            return _unavailable(order, "render_spec_invalid", [e.as_dict() for e in errors], 1)
        return await _draw(order, prebuilt, str(prebuilt.family), 1)
    if builder is None:
        return _fallback(order, "no_spec_builder")

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
        errors = _spec_errors(order, spec)
        if not errors:
            return await _draw(order, spec, family, attempts)

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
