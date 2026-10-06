"""``cycle``: stages arranged on a circle, joined by arcs that close the loop."""

from __future__ import annotations

import math
from dataclasses import dataclass

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.text import Text

from media.render.contracts import CycleSpec, RenderSpecError
from media.render.families import _nodes as n
from media.render.layout import fit_labels
from media.render.style import INK, LABEL_FONT_SIZE

_MIN_ARC_IN = 0.55
_ARC_PAD = 0.07
_PAD = 0.3
_CENTER_WRAP = 14


def validate(spec: CycleSpec) -> list[RenderSpecError]:
    errors: list[RenderSpecError] = []
    seen: dict[str, int] = {}
    for i, text in enumerate(spec.nodes):
        key = " ".join(text.lower().split())
        if key in seen:
            errors.append(
                RenderSpecError(
                    "duplicate_node_text",
                    f"nodes[{i}]",
                    f"stage {text!r} repeats nodes[{seen[key]}]; every stage needs its own wording",
                )
            )
        seen.setdefault(key, i)
        if not n.fits(text, n.STEP_WRAP):
            errors.append(
                RenderSpecError(
                    "node_text_too_long",
                    f"nodes[{i}]",
                    f"{text!r} needs more than {n.MAX_LINES} lines in a box; shorten it to "
                    f"about {n.STEP_WRAP * n.MAX_LINES - 6} characters or fewer",
                )
            )
    return errors


def node_angles(spec: CycleSpec) -> list[float]:
    """Angle of each node in degrees: the first at the top, then around the circle."""
    count = len(spec.nodes)
    step = -360.0 / count if spec.clockwise else 360.0 / count
    return [90.0 + i * step for i in range(count)]


@dataclass(frozen=True)
class _Plan:
    lines: list[list[str]]
    size: n.Pt
    centers: list[n.Pt]
    arcs: list[list[n.Pt]]
    center_lines: list[str]
    half: float


def _inside(p: n.Pt, c: n.Pt, size: n.Pt, pad: float) -> bool:
    return abs(p[0] - c[0]) < size[0] / 2 + pad and abs(p[1] - c[1]) < size[1] / 2 + pad


def _arc(radius: float, angles: list[float], centers: list[n.Pt], size: n.Pt, i: int, delta: float) -> list[n.Pt]:
    """Points along the circle from node ``i`` to the next, clear of both boxes."""
    j = (i + 1) % len(angles)
    samples = 400
    pts = [
        (
            radius * math.cos(math.radians(angles[i] + delta * t / samples)),
            radius * math.sin(math.radians(angles[i] + delta * t / samples)),
        )
        for t in range(samples + 1)
    ]
    first = next((t for t, p in enumerate(pts) if not _inside(p, centers[i], size, _ARC_PAD)), None)
    last = next(
        (t for t in range(samples, -1, -1) if not _inside(pts[t], centers[j], size, _ARC_PAD)), None
    )
    if first is None or last is None or last <= first:
        return []
    return pts[first : last + 1]


def _arc_length(points: list[n.Pt]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False))


def _plan(spec: CycleSpec) -> _Plan:
    width = n.choose_width(spec.nodes, (12, 14, 16))
    lines = [n.wrap_lines(text, width) for text in spec.nodes]
    blocks = [n.text_size(block) for block in lines]
    size = n.box_size("step", blocks)
    angles = node_angles(spec)
    count = len(spec.nodes)
    delta = -360.0 / count if spec.clockwise else 360.0 / count
    center_lines: list[str] = []
    center_rect = (0.0, 0.0)
    if spec.center_label:
        center_lines = n.wrap_lines(spec.center_label, _CENTER_WRAP)
        center_rect = n.text_size(center_lines, LABEL_FONT_SIZE, "bold")

    radius = 1.2
    while True:
        centers = [
            (radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a))) for a in angles
        ]
        arcs = [_arc(radius, angles, centers, size, i, delta) for i in range(count)]
        arcs_ok = all(a and _arc_length(a) >= _MIN_ARC_IN for a in arcs)
        label_ok = all(
            not (
                abs(c[0]) < size[0] / 2 + center_rect[0] / 2 + 0.2
                and abs(c[1]) < size[1] / 2 + center_rect[1] / 2 + 0.2
            )
            for c in centers
        ) if spec.center_label else True
        if (arcs_ok and label_ok) or radius > 6:
            break
        radius += 0.1
    half = max(max(abs(c[0]) + size[0] / 2, abs(c[1]) + size[1] / 2) for c in centers) + _PAD
    return _Plan(lines, size, centers, arcs, center_lines, half)


def draw(spec: CycleSpec) -> Figure:
    plan = _plan(spec)

    def build(font_size: float) -> tuple[Figure, list[Text], list[Artist]]:
        fig = Figure(figsize=(2 * plan.half, 2 * plan.half))
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(-plan.half, plan.half)
        ax.set_ylim(-plan.half, plan.half)
        ax.axis("off")
        texts: list[Text] = []
        obstacles: list[Artist] = []
        for center, block in zip(plan.centers, plan.lines, strict=True):
            patch, text = n.add_node(ax, "step", center, plan.size, block, font_size)
            texts.append(text)
            obstacles.append(patch)
        for points in plan.arcs:
            obstacles.append(n.add_arrow(ax, points))
        if plan.center_lines:
            texts.append(
                ax.text(
                    0,
                    0,
                    "\n".join(plan.center_lines),
                    ha="center",
                    va="center",
                    multialignment="center",
                    fontsize=LABEL_FONT_SIZE,
                    fontweight="bold",
                    color=INK,
                    zorder=4,
                )
            )
        return fig, texts, obstacles

    return fit_labels(build)


def describe(spec: CycleSpec) -> str:
    stages = " → ".join(spec.nodes)
    way = "" if spec.clockwise else " (anticlockwise)"
    title = f" titled {spec.center_label}" if spec.center_label else ""
    return f"Cycle{title} of {len(spec.nodes)} stages{way}: {stages} → back to {spec.nodes[0]}."


def numbers(spec: CycleSpec) -> list[float]:
    return []


GALLERY: dict[str, dict] = {
    "cycle_water": {
        "family": "cycle",
        "nodes": ["Evaporation", "Condensation", "Precipitation", "Collection"],
        "center_label": "Water cycle",
    },
    "cycle_butterfly": {
        "family": "cycle",
        "nodes": ["Egg", "Caterpillar", "Chrysalis", "Butterfly"],
        "center_label": "Life cycle",
    },
    "cycle_six_anticlockwise": {
        "family": "cycle",
        "nodes": ["Plan", "Do", "Check", "Reflect", "Adjust", "Share"],
        "clockwise": False,
    },
}

__all__ = ["GALLERY", "describe", "draw", "node_angles", "numbers", "validate"]
