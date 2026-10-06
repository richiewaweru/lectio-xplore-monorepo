"""``polygon_area``: any straight-edged shape by corner points.

Edge lengths are measured from the points, never taken from the model, so a
label cannot contradict the drawing. Split figures reuse the same points.
"""

from __future__ import annotations

from dataclasses import dataclass

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.patches import Polygon as PolygonPatch
from matplotlib.text import Text

from media.render import geometry as g
from media.render.contracts import Point, PolygonAreaSpec, RenderSpecError
from media.render.layout import fit_labels
from media.render.style import FILL, INK, LABEL_FONT_SIZE, LINE, SHADES, THIN

_MAX_FIGURE_IN = 5.5


@dataclass(frozen=True)
class PlacedLabel:
    text: str
    x: float
    y: float
    ha: str
    va: str
    kind: str  # "edge" | "segment" | "region"
    italic: bool = False


def _orientation(spec: PolygonAreaSpec) -> float:
    return 1.0 if g.signed_area(spec.points) > 0 else -1.0


def _extent(spec: PolygonAreaSpec) -> tuple[float, float, float, float]:
    xs = [p[0] for p in spec.points]
    ys = [p[1] for p in spec.points]
    return min(xs), max(xs), min(ys), max(ys)


def edge_label_text(spec: PolygonAreaSpec, edge: int) -> str | None:
    label = next((item for item in spec.edge_labels if item.edge == edge), None)
    if label is None or label.kind == "hidden":
        return None
    if label.kind == "symbol":
        return label.text
    a = spec.points[edge]
    b = spec.points[(edge + 1) % len(spec.points)]
    return f"{g.format_number(g.length(a, b))} {spec.unit}".strip()


def _align(nx: float, ny: float) -> tuple[str, str]:
    ha = "left" if nx > 0.5 else "right" if nx < -0.5 else "center"
    va = "bottom" if ny > 0.5 else "top" if ny < -0.5 else "center"
    return ha, va


def place_labels(spec: PolygonAreaSpec) -> list[PlacedLabel]:
    """Where every label goes, in data coordinates. Pure; used by draw and tests."""
    x0, x1, y0, y1 = _extent(spec)
    off = 0.03 * max(x1 - x0, y1 - y0)
    sign = _orientation(spec)
    placed: list[PlacedLabel] = []
    n = len(spec.points)
    for i in range(n):
        text = edge_label_text(spec, i)
        if not text:
            continue
        a, b = spec.points[i], spec.points[(i + 1) % n]
        ux, uy = g.unit(a, b)
        nx, ny = uy * sign, -ux * sign  # outward normal
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ha, va = _align(nx, ny)
        symbol = any(item.edge == i and item.kind == "symbol" for item in spec.edge_labels)
        placed.append(PlacedLabel(text, mx + nx * off, my + ny * off, ha, va, "edge", italic=symbol))
    for seg in spec.segments:
        if not seg.label:
            continue
        ux, uy = g.unit(seg.start, seg.end)
        mx, my = (seg.start[0] + seg.end[0]) / 2, (seg.start[1] + seg.end[1]) / 2
        # Label on whichever side of the line has more room inside the shape.
        probe = 0.12 * max(x1 - x0, y1 - y0)

        def room(nx: float, ny: float) -> float:
            p = (mx + nx * probe, my + ny * probe)
            return g.distance_to_boundary(p, spec.points) if g.inside_or_on(p, spec.points) else -1.0

        nx, ny = max(((-uy, ux), (uy, -ux)), key=lambda n: room(*n))
        ha, va = _align(nx, ny)
        placed.append(PlacedLabel(seg.label, mx + nx * off * 0.6, my + ny * off * 0.6, ha, va, "segment"))
    for region in spec.regions:
        if region.label:
            cx, cy = g.centroid(region.points)
            placed.append(PlacedLabel(region.label, cx, cy, "center", "center", "region"))
    return placed


def _square(corner: Point, u1: Point, u2: Point, size: float) -> list[Point]:
    return [
        corner,
        (corner[0] + u1[0] * size, corner[1] + u1[1] * size),
        (corner[0] + (u1[0] + u2[0]) * size, corner[1] + (u1[1] + u2[1]) * size),
        (corner[0] + u2[0] * size, corner[1] + u2[1] * size),
    ]


def _right_angle_marks(spec: PolygonAreaSpec, size: float) -> list[list[Point]]:
    marks: list[list[Point]] = []
    pts = spec.points
    n = len(pts)
    sign = _orientation(spec)
    if spec.mark_right_angles:
        for i in range(n):
            p, v, nxt = pts[i - 1], pts[i], pts[(i + 1) % n]
            u_next = g.unit(v, nxt)
            u_prev = g.unit(v, p)
            dot = u_next[0] * u_prev[0] + u_next[1] * u_prev[1]
            turn = (v[0] - p[0]) * (nxt[1] - v[1]) - (v[1] - p[1]) * (nxt[0] - v[0])
            if abs(dot) < 1e-6 and turn * sign > 0:  # convex 90° corner
                marks.append(_square(v, u_next, u_prev, size))
    for seg in spec.segments:
        if seg.right_angle_at is None:
            continue
        foot, other = (seg.start, seg.end) if seg.right_angle_at == "start" else (seg.end, seg.start)
        edge = next(((a, b) for a, b in g.edges(pts) if g.on_segment(foot, a, b)), None)
        if edge is None:
            continue
        along = g.unit(foot, other)
        e = g.unit(*edge)
        for cand in (e, (-e[0], -e[1])):
            square = _square(foot, along, cand, size)
            if g.inside_or_on(g.centroid(square), pts):
                marks.append(square)
                break
    return marks


def draw(spec: PolygonAreaSpec) -> Figure:
    x0, x1, y0, y1 = _extent(spec)
    w, h = x1 - x0, y1 - y0
    span = max(w, h)
    pad = 0.12 * span
    scale = _MAX_FIGURE_IN / (span + 2 * pad)
    labels = place_labels(spec)

    def build(font_size: float) -> tuple[Figure, list[Text], list[Artist]]:
        fig = Figure(figsize=((w + 2 * pad) * scale, (h + 2 * pad) * scale))
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(x0 - pad, x1 + pad)
        ax.set_ylim(y0 - pad, y1 + pad)
        ax.set_aspect("equal")
        ax.axis("off")
        shaded = [r for r in spec.regions if r.shade]
        ax.add_patch(
            PolygonPatch(spec.points, closed=True, facecolor="white" if shaded else FILL, edgecolor="none")
        )
        for index, region in enumerate(shaded):
            ax.add_patch(
                PolygonPatch(
                    region.points,
                    closed=True,
                    facecolor=SHADES[index % len(SHADES)],
                    edgecolor="none",
                )
            )
        obstacles: list[Artist] = []
        for seg in spec.segments:
            obstacles += ax.plot(
                [seg.start[0], seg.end[0]],
                [seg.start[1], seg.end[1]],
                color=INK,
                linewidth=THIN,
                linestyle=(0, (5, 3)) if seg.style == "dashed" else "solid",
                solid_capstyle="butt",
            )
        for mark in _right_angle_marks(spec, 0.035 * span):
            ax.plot(
                [mark[1][0], mark[2][0], mark[3][0]],
                [mark[1][1], mark[2][1], mark[3][1]],
                color=INK,
                linewidth=THIN,
            )
        outline = PolygonPatch(
            spec.points, closed=True, facecolor="none", edgecolor=INK, linewidth=LINE, joinstyle="miter"
        )
        ax.add_patch(outline)
        obstacles.append(outline)
        texts = [
            ax.text(
                label.x,
                label.y,
                label.text,
                ha=label.ha,
                va=label.va,
                fontsize=LABEL_FONT_SIZE + 1 if label.kind == "region" else font_size,
                fontweight="bold" if label.kind == "region" else "normal",
                fontstyle="italic" if label.italic else "normal",
                color=INK,
            )
            for label in labels
        ]
        return fig, texts, obstacles

    return fit_labels(build)


def validate(spec: PolygonAreaSpec) -> list[RenderSpecError]:
    errors: list[RenderSpecError] = []
    pts = spec.points
    n = len(pts)
    for i in range(n):
        if g.length(pts[i], pts[(i + 1) % n]) < 1e-9:
            errors.append(
                RenderSpecError("duplicate_point", f"points[{i}]", "consecutive points are identical")
            )
    if errors:
        return errors
    if g.collinear(pts):
        errors.append(RenderSpecError("degenerate_polygon", "points", "the points enclose no area"))
        return errors
    if not g.is_simple(pts):
        # Checked before area: a symmetric bow tie has zero signed area but
        # "edges cross" is the message a repair can act on.
        errors.append(
            RenderSpecError("self_intersecting", "points", "edges cross or touch; list corners in order around the shape")
        )
        return errors
    seen: set[int] = set()
    for index, label in enumerate(spec.edge_labels):
        path = f"edge_labels[{index}]"
        if label.edge >= n:
            errors.append(
                RenderSpecError("bad_edge_index", path, f"edge {label.edge} does not exist; edges are 0..{n - 1}")
            )
            continue
        if label.edge in seen:
            errors.append(RenderSpecError("duplicate_edge_label", path, f"edge {label.edge} is labelled twice"))
        seen.add(label.edge)
        if label.kind == "symbol" and not label.text:
            errors.append(RenderSpecError("symbol_needs_text", path, "symbol labels need text such as 'x'"))
        if label.kind != "symbol" and label.text:
            errors.append(
                RenderSpecError("unexpected_text", path, "only symbol labels carry text; computed lengths are measured")
            )
        if label.kind == "computed":
            value = g.length(pts[label.edge], pts[(label.edge + 1) % n])
            if not g.is_nice(value):
                errors.append(
                    RenderSpecError(
                        "awkward_length",
                        path,
                        f"edge {label.edge} measures {value:.3f}; use kind 'symbol' or 'hidden', or fix the points",
                    )
                )
    for index, seg in enumerate(spec.segments):
        path = f"segments[{index}]"
        if g.length(seg.start, seg.end) < 1e-9:
            errors.append(RenderSpecError("degenerate_segment", path, "segment has zero length"))
            continue
        if not g.segment_inside(seg.start, seg.end, pts):
            errors.append(RenderSpecError("segment_outside", path, "segment leaves the shape"))
        if seg.right_angle_at is not None:
            foot = seg.start if seg.right_angle_at == "start" else seg.end
            if not g.on_boundary(foot, pts):
                errors.append(
                    RenderSpecError("right_angle_off_boundary", path, "right_angle_at must be an endpoint on the shape's edge")
                )
    total = 0.0
    for index, region in enumerate(spec.regions):
        path = f"regions[{index}]"
        if g.area(region.points) < 1e-9 or not g.is_simple(region.points):
            errors.append(RenderSpecError("bad_region", path, "region is degenerate or self-intersecting"))
            continue
        if not all(g.inside_or_on(p, pts) for p in region.points) or not g.inside_or_on(
            g.centroid(region.points), pts
        ):
            errors.append(RenderSpecError("region_outside", path, "region extends outside the shape"))
        total += g.area(region.points)
    if total > g.area(pts) + 1e-6:
        errors.append(RenderSpecError("regions_overlap", "regions", "regions cover more than the whole shape"))
    return errors


def describe(spec: PolygonAreaSpec) -> str:
    labelled = [edge_label_text(spec, i) for i in range(len(spec.points))]
    shown = [text for text in labelled if text]
    parts = [f"Shape with {len(spec.points)} straight sides"]
    if shown:
        parts.append("sides labelled " + ", ".join(shown))
    if spec.regions:
        names = [r.label for r in spec.regions if r.label]
        parts.append(
            f"divided into {len(spec.regions)} parts" + (f" ({', '.join(names)})" if names else "")
        )
    return "; ".join(parts) + "."


def numbers(spec: PolygonAreaSpec) -> list[float]:
    n = len(spec.points)
    return [
        g.length(spec.points[label.edge], spec.points[(label.edge + 1) % n])
        for label in spec.edge_labels
        if label.kind == "computed" and label.edge < n
    ]


__all__ = ["PlacedLabel", "describe", "draw", "edge_label_text", "numbers", "place_labels", "validate"]
