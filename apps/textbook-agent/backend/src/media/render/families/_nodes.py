"""Shared box-and-arrow drawing for the ``flow`` and ``cycle`` families.

Boxes are sized from measured text, so a label can never spill out of its box.
Coordinates are inches: a family builds its figure with an axes that spans the
whole figure and limits equal to the figure size in inches.
"""

from __future__ import annotations

import textwrap
from collections.abc import Sequence

from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.patches import Polygon as PolygonPatch
from matplotlib.path import Path
from matplotlib.patches import Patch
from matplotlib.text import Text

from media.render.style import FONT_SIZE, INK, LINE, THIN

MAX_LINES = 3
# Widest wrap a box may need before validation rejects the text.
STEP_WRAP = 16
DECISION_WRAP = 15
# A single unbreakable word may overrun the wrap width by this much.
_WORD_SLACK = 4

Pt = tuple[float, float]


def wrap_lines(text: str, width: int) -> list[str]:
    lines = textwrap.wrap(text.strip(), width=width, break_long_words=False, break_on_hyphens=False)
    return lines or [text.strip()]


def fits(text: str, width: int) -> bool:
    lines = wrap_lines(text, width)
    return len(lines) <= MAX_LINES and all(len(line) <= width + _WORD_SLACK for line in lines)


def choose_width(texts: Sequence[str], candidates: Sequence[int]) -> int:
    """Narrowest wrap in ``candidates`` at which every text fits, else the widest."""
    for width in candidates:
        if all(fits(text, width) for text in texts):
            return width
    return candidates[-1]


def text_size(lines: Sequence[str], size: float = FONT_SIZE, weight: str = "normal") -> Pt:
    """Rendered width and height of a text block, in inches."""
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    text = fig.text(0, 0, "\n".join(lines), fontsize=size, fontweight=weight)
    box = text.get_window_extent(canvas.get_renderer())
    return box.width / fig.dpi, box.height / fig.dpi


def box_size(kind: str, blocks: Sequence[Pt]) -> Pt:
    """Uniform node size for ``kind`` given the measured text blocks of that kind."""
    tw = max(w for w, _ in blocks)
    th = max(h for _, h in blocks)
    if kind == "decision":
        # Text corners sit inside the diamond: tw / W + th / H <= 0.85.
        height = max(1.6 * th + 0.5, 0.9)
        width = tw / (0.85 - th / height)
        return width, height
    pad_x = 0.75 if kind == "terminal" else 0.55
    return max(tw + pad_x, 1.2), max(th + 0.36, 0.55)


def add_node(
    ax: Axes,
    kind: str,
    center: Pt,
    size: Pt,
    lines: Sequence[str],
    font_size: float,
) -> tuple[Patch, Text]:
    cx, cy = center
    w, h = size
    if kind == "decision":
        patch: Patch = PolygonPatch(
            [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)],
            closed=True,
            facecolor="white",
            edgecolor=INK,
            linewidth=LINE,
            joinstyle="miter",
            zorder=2,
        )
        ax.add_patch(patch)
    else:
        rounding = h / 2 if kind == "terminal" else 0.12
        patch = FancyBboxPatch(
            (cx - w / 2, cy - h / 2),
            w,
            h,
            boxstyle=f"round,pad=0,rounding_size={rounding}",
            facecolor="white",
            edgecolor=INK,
            linewidth=LINE,
            zorder=2,
        )
        ax.add_patch(patch)
    text = ax.text(
        cx,
        cy,
        "\n".join(lines),
        ha="center",
        va="center",
        multialignment="center",
        fontsize=font_size,
        color=INK,
        zorder=4,
    )
    return patch, text


def add_arrow(ax: Axes, points: Sequence[Pt]) -> Line2D:
    """Draw a polyline ending in an arrowhead; return an invisible stand-in for clash checks."""
    path = Path(list(points), [Path.MOVETO] + [Path.LINETO] * (len(points) - 1))
    ax.add_patch(
        FancyArrowPatch(
            path=path,
            arrowstyle="-|>",
            mutation_scale=15,
            shrinkA=0,
            shrinkB=0.5,
            color=INK,
            linewidth=THIN * 1.25,
            joinstyle="miter",
            capstyle="butt",
            zorder=3,
        )
    )
    return Line2D([p[0] for p in points], [p[1] for p in points], transform=ax.transData)


__all__ = [
    "DECISION_WRAP",
    "MAX_LINES",
    "STEP_WRAP",
    "Pt",
    "add_arrow",
    "add_node",
    "box_size",
    "choose_width",
    "fits",
    "text_size",
    "wrap_lines",
]
