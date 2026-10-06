"""Registry of implemented render families.

Each family module provides ``validate`` (structural errors for repair),
``draw`` (spec -> matplotlib Figure), ``describe`` (alt text) and ``numbers``
(computed values that must appear in the lesson text).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from matplotlib.figure import Figure

from media.render.contracts import RenderSpecError
from media.render.families import polygon


@dataclass(frozen=True)
class FamilyRenderer:
    validate: Callable[[Any], list[RenderSpecError]]
    draw: Callable[[Any], Figure]
    describe: Callable[[Any], str]
    numbers: Callable[[Any], list[float]]


def _module_renderer(module: Any) -> FamilyRenderer:
    return FamilyRenderer(
        validate=module.validate,
        draw=module.draw,
        describe=module.describe,
        numbers=module.numbers,
    )


RENDERERS: dict[str, FamilyRenderer] = {
    "polygon_area": _module_renderer(polygon),
}


def renderer_for(family: str) -> FamilyRenderer | None:
    return RENDERERS.get(family)


__all__ = ["RENDERERS", "FamilyRenderer", "renderer_for"]
