"""Spec -> SVG (master) + PNG (fallback), deterministically."""

from __future__ import annotations

import io
from dataclasses import dataclass

from matplotlib.figure import Figure

from media.render.contracts import RenderSpecError
from media.render.families import renderer_for
from media.render.style import PNG_DPI, RENDERER_VERSION, drawing
from media.render.validate import validate_spec


class InvalidRenderSpec(ValueError):
    def __init__(self, errors: list[RenderSpecError]) -> None:
        self.errors = errors
        super().__init__("; ".join(str(error) for error in errors))


@dataclass(frozen=True)
class RenderedFigure:
    family: str
    svg: bytes
    png: bytes
    alt_text: str
    renderer_version: str = RENDERER_VERSION


def _save(fig: Figure, fmt: str) -> bytes:
    out = io.BytesIO()
    if fmt == "svg":
        fig.savefig(out, format="svg", metadata={"Date": None}, bbox_inches="tight", pad_inches=0.12)
    else:
        fig.savefig(
            out,
            format="png",
            dpi=PNG_DPI,
            metadata={"Software": None},
            bbox_inches="tight",
            pad_inches=0.12,
        )
    return out.getvalue()


def render_spec(spec: object) -> RenderedFigure:
    """Validate and draw. Raises ``InvalidRenderSpec`` or ``RenderLayoutError``."""
    errors = validate_spec(spec)
    if errors:
        raise InvalidRenderSpec(errors)
    family = str(getattr(spec, "family"))
    renderer = renderer_for(family)
    assert renderer is not None  # validate_spec rejects unknown families
    with drawing():
        fig = renderer.draw(spec)
        svg = _save(fig, "svg")
        png = _save(fig, "png")
    return RenderedFigure(family=family, svg=svg, png=png, alt_text=renderer.describe(spec))


__all__ = ["InvalidRenderSpec", "RenderedFigure", "render_spec"]
