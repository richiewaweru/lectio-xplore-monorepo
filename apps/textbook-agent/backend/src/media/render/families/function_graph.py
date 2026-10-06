"""``function_graph``: coordinate axes with structured curves and labelled points.

Curves are linear (m, c), quadratic (a, b, c) or a polyline. Nothing here
evaluates an expression; the schema only admits those numeric forms.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.path import Path
from matplotlib.text import Text
from matplotlib.transforms import Bbox

from media.render import geometry as g
from media.render.contracts import (
    FunctionGraphSpec,
    LinearCurve,
    PolylineCurve,
    QuadraticCurve,
    RenderSpecError,
)
from media.render.layout import fit_labels
from media.render.style import GRID, INK, LINE, THIN

_MAX_TICKS = 24
_SAMPLES = 400
_STYLES = ("solid", (0, (6, 3)), (0, (7, 3, 1.5, 3)), (0, (1.5, 2.5)))
_INNER_IN = 4.0
_PAD_PX = 3.0
_ARROW = 7

Curve = LinearCurve | QuadraticCurve | PolylineCurve


def _sample(curve: Curve, x0: float, x1: float) -> tuple[np.ndarray, np.ndarray]:
    if isinstance(curve, PolylineCurve):
        xs = np.array([p[0] for p in curve.points], dtype=float)
        ys = np.array([p[1] for p in curve.points], dtype=float)
        return xs, ys
    xs = np.linspace(x0, x1, _SAMPLES)
    if isinstance(curve, LinearCurve):
        return xs, curve.m * xs + curve.c
    return xs, curve.a * xs * xs + curve.b * xs + curve.c


def _tick_values(lo: float, hi: float, step: float | None) -> list[float]:
    if step is None:
        span = hi - lo
        if span <= 20:
            step = 1.0
        else:
            raw = span / 8
            base = 10.0 ** math.floor(math.log10(raw))
            step = next(m * base for m in (1, 2, 5, 10) if m * base >= raw)
    first = math.ceil(lo / step - 1e-9)
    last = math.floor(hi / step + 1e-9)
    return [round(i * step, 10) for i in range(first, last + 1)]


def _tick_count(lo: float, hi: float, step: float) -> int:
    return len(_tick_values(lo, hi, step))


def _align(dx: float, dy: float) -> tuple[str, str]:
    ha = "left" if dx > 0.35 else "right" if dx < -0.35 else "center"
    va = "bottom" if dy > 0.35 else "top" if dy < -0.35 else "center"
    return ha, va


def _label_text(value: float) -> str:
    # Tick labels use the true minus sign, like the number line family.
    return g.format_number(value).replace("-", "−")


class _Placer:
    """Greedy label placement against everything already drawn, in pixel space."""

    def __init__(self, fig: Figure, ax: Axes) -> None:
        self.fig = fig
        self.ax = ax
        self.canvas = fig.canvas if isinstance(fig.canvas, FigureCanvasAgg) else FigureCanvasAgg(fig)
        self.renderer = self.canvas.get_renderer()
        self.boxes: list[Bbox] = []
        self.paths: list[Path] = []
        self.texts: list[Text] = []

    def px(self, x: float, y: float) -> tuple[float, float]:
        a, b = self.ax.transData.transform((x, y))
        return float(a), float(b)

    def add_path(self, xs: np.ndarray, ys: np.ndarray) -> None:
        pts = np.column_stack([xs, ys])
        pts = pts[np.isfinite(pts).all(axis=1)]
        if len(pts) >= 2:
            self.paths.append(Path(self.ax.transData.transform(pts)))

    def add_box(self, box: Bbox) -> None:
        self.boxes.append(box.padded(_PAD_PX))

    def add_marker(self, x: float, y: float, radius: float = 6.0) -> None:
        a, b = self.px(x, y)
        self.boxes.append(Bbox([[a - radius, b - radius], [a + radius, b + radius]]))

    def fits(self, box: Bbox) -> bool:
        inner = self.ax.bbox
        if (
            box.x0 < inner.x0 + 2
            or box.x1 > inner.x1 - 2
            or box.y0 < inner.y0 + 2
            or box.y1 > inner.y1 - 2
        ):
            return False
        if any(box.overlaps(other) for other in self.boxes):
            return False
        return not any(path.intersects_bbox(box, filled=False) for path in self.paths)

    def _annotate(
        self,
        text: str,
        cand: tuple[float, float, float, float, float],
        font_size: float,
        italic: bool,
    ) -> Text:
        ax_, ay_, dx, dy, dist = cand
        ha, va = _align(dx, dy)
        return self.ax.annotate(
            text,
            (ax_, ay_),
            xytext=(dx * dist, dy * dist),
            textcoords="offset points",
            ha=ha,
            va=va,
            fontsize=font_size,
            fontstyle="italic" if italic else "normal",
            color=INK,
            annotation_clip=False,
            zorder=6,
        )

    def place(
        self,
        text: str,
        candidates: Sequence[tuple[float, float, float, float, float]],
        font_size: float,
        italic: bool = False,
    ) -> Text:
        """candidates: (anchor x, anchor y, dir x, dir y, distance in points) in pixel dirs."""
        chosen: Text | None = None
        for cand in candidates:
            ann = self._annotate(text, cand, font_size, italic)
            box = ann.get_window_extent(self.renderer).padded(_PAD_PX)
            if self.fits(box):
                chosen = ann
                break
            ann.remove()
        if chosen is None:
            chosen = self._annotate(text, candidates[0], font_size, italic)
        self.boxes.append(chosen.get_window_extent(self.renderer).padded(_PAD_PX))
        self.texts.append(chosen)
        return chosen


_DIRECTIONS = [
    (1, 1),
    (-1, 1),
    (1, -1),
    (-1, -1),
    (0, 1),
    (0, -1),
    (1, 0),
    (-1, 0),
]


def _unit(dx: float, dy: float) -> tuple[float, float]:
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def draw(spec: FunctionGraphSpec) -> Figure:
    x0, x1 = spec.x_range
    y0, y1 = spec.y_range
    xspan, yspan = x1 - x0, y1 - y0
    x_zero = x0 <= 0 <= x1
    y_zero = y0 <= 0 <= y1
    both_zero = x_zero and y_zero
    x_ticks = _tick_values(x0, x1, spec.x_step)
    y_ticks = _tick_values(y0, y1, spec.y_step)
    ratio = max(0.6, min(1.0, yspan / xspan)) if yspan < xspan else 1.0
    inner_w = _INNER_IN * (max(0.6, min(1.0, xspan / yspan)) if xspan < yspan else 1.0)
    inner_h = _INNER_IN * ratio
    # Margins in inches: room for the axis names (and tick labels when on an edge).
    label_chars = max(len(_label_text(t)) for t in [*x_ticks, *y_ticks]) if x_ticks else 2
    left = max(0.5, 0.055 * len(spec.y_label) + 0.15) if x_zero else 0.35 + 0.1 * label_chars + 0.45
    right = min(1.4, max(0.35, 0.1 * len(spec.x_label) + 0.25)) if y_zero else 0.35
    top = 0.45 if x_zero else 0.3
    bottom = 0.3 if y_zero else 0.95
    fig_w, fig_h = left + inner_w + right, bottom + inner_h + top
    drawn = list(spec.curves)

    def build(font_size: float) -> tuple[Figure, Sequence[Text], Sequence[Artist]]:
        fig = Figure(figsize=(fig_w, fig_h))
        ax = fig.add_axes((left / fig_w, bottom / fig_h, inner_w / fig_w, inner_h / fig_h))
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_xticks(x_ticks)
        ax.set_yticks(y_ticks)
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        if spec.grid:
            ax.grid(True, color=GRID, linewidth=1.0, zorder=0)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_position(("data", 0) if y_zero else ("data", y0))
        ax.spines["left"].set_position(("data", 0) if x_zero else ("data", x0))
        for side in ("left", "bottom"):
            ax.spines[side].set_color(INK)
            ax.spines[side].set_linewidth(THIN + 0.4)
        ax.tick_params(direction="inout", length=6, width=THIN, pad=3)
        ax_y = 0.0 if y_zero else y0
        ax_x = 0.0 if x_zero else x0
        if y_zero:
            ax.plot([x1], [0], marker=">", ms=_ARROW, color=INK, clip_on=False, zorder=5, ls="none")
        if x_zero:
            ax.plot([0], [y1], marker="^", ms=_ARROW, color=INK, clip_on=False, zorder=5, ls="none")
        fig.canvas = FigureCanvasAgg(fig)
        fig.canvas.draw()
        placer = _Placer(fig, ax)
        # Axis lines as obstacles (pixel space).
        placer.add_path(np.array([x0, x1]), np.array([ax_y, ax_y]))
        placer.add_path(np.array([ax_x, ax_x]), np.array([y0, y1]))
        tick_kw = {
            "textcoords": "offset points",
            "fontsize": font_size - 1,
            "annotation_clip": False,
            "zorder": 5.5,
            "bbox": {"facecolor": "white", "edgecolor": "none", "pad": 1.0, "alpha": 0.9},
        }
        for t in x_ticks:
            if both_zero and t == 0:
                continue
            ann = ax.annotate(
                _label_text(t), (t, ax_y), xytext=(0, -8), ha="center", va="top", **tick_kw
            )
            placer.add_box(ann.get_window_extent(placer.renderer))
        for t in y_ticks:
            if both_zero and t == 0:
                continue
            ann = ax.annotate(
                _label_text(t), (ax_x, t), xytext=(-8, 0), ha="right", va="center", **tick_kw
            )
            placer.add_box(ann.get_window_extent(placer.renderer))
        # Axis names.
        names: list[Text] = []
        if y_zero:
            xl = ax.annotate(
                spec.x_label,
                (x1, 0),
                xytext=(10, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=font_size,
                fontstyle="italic",
                annotation_clip=False,
            )
        else:
            xl = ax.annotate(
                spec.x_label,
                ((x0 + x1) / 2, y0),
                xytext=(0, -34),
                textcoords="offset points",
                ha="center",
                va="top",
                fontsize=font_size,
                fontstyle="italic",
                annotation_clip=False,
            )
        if x_zero:
            yl = ax.annotate(
                spec.y_label,
                (0, y1),
                xytext=(0, 10),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=font_size,
                fontstyle="italic",
                annotation_clip=False,
            )
        else:
            yl = ax.annotate(
                spec.y_label,
                (x0, (y0 + y1) / 2),
                xytext=(-(14 + 8 * label_chars), 0),
                textcoords="offset points",
                ha="right",
                va="center",
                rotation=90,
                fontsize=font_size,
                fontstyle="italic",
                annotation_clip=False,
            )
        names += [xl, yl]
        # Curves.
        curve_lines: list[Artist] = []
        samples: list[tuple[np.ndarray, np.ndarray]] = []
        for index, curve in enumerate(drawn):
            xs, ys = _sample(curve, x0, x1)
            samples.append((xs, ys))
            (line,) = ax.plot(
                xs,
                ys,
                color=INK,
                linewidth=LINE,
                linestyle=_STYLES[index % len(_STYLES)],
                solid_capstyle="butt",
                zorder=4,
            )
            curve_lines.append(line)
            inside = (ys >= y0 - 1e-9) & (ys <= y1 + 1e-9) & (xs >= x0 - 1e-9) & (xs <= x1 + 1e-9)
            placer.add_path(xs[inside], ys[inside])
        for p in spec.points:
            ax.plot([p.x], [p.y], "o", color=INK, ms=6, zorder=5, clip_on=False)
            placer.add_marker(p.x, p.y)
        if both_zero:
            # Origin label: first corner clear of curves and axes, else omitted.
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                zero = ax.annotate(
                    "0",
                    (0, 0),
                    xytext=(dx * 5, dy * 5),
                    textcoords="offset points",
                    ha="right" if dx < 0 else "left",
                    va="top" if dy < 0 else "bottom",
                    fontsize=font_size - 1,
                )
                box = zero.get_window_extent(placer.renderer).padded(1.0)
                if placer.fits(box):
                    placer.boxes.append(box)
                    break
                zero.remove()
        texts: list[Text] = []
        for curve, (xs, ys) in zip(drawn, samples):
            if not curve.label:
                continue
            inside = np.where((ys >= y0) & (ys <= y1) & (xs >= x0) & (xs <= x1))[0]
            if len(inside) == 0:
                continue
            candidates: list[tuple[float, float, float, float, float]] = []
            for frac in (0.0, 0.06, 0.12, 0.2, 0.3, 0.45):
                k = inside[max(0, int(round((len(inside) - 1) * (1 - frac))))]
                k2 = min(k + 1, len(xs) - 1)
                k1 = max(k - 1, 0)
                px0 = placer.px(xs[k1], ys[k1])
                px1 = placer.px(xs[k2], ys[k2])
                tx, ty = _unit(px1[0] - px0[0], px1[1] - px0[1])
                for sign in (1, -1):
                    candidates.append((float(xs[k]), float(ys[k]), -ty * sign, tx * sign, 9))
            texts.append(placer.place(curve.label, candidates, font_size))
        for p in spec.points:
            if not p.label:
                continue
            candidates = []
            for dist in (8, 14):
                for dx, dy in _DIRECTIONS:
                    ux, uy = _unit(dx, dy)
                    candidates.append((p.x, p.y, ux, uy, dist))
            texts.append(placer.place(p.label, candidates, font_size))
        return fig, [*texts, *names], curve_lines

    return fit_labels(build)


def validate(spec: FunctionGraphSpec) -> list[RenderSpecError]:
    errors: list[RenderSpecError] = []
    x0, x1 = spec.x_range
    y0, y1 = spec.y_range
    if not x0 < x1:
        errors.append(
            RenderSpecError("bad_range", "x_range", "x_range must be [min, max] with min < max")
        )
    if not y0 < y1:
        errors.append(
            RenderSpecError("bad_range", "y_range", "y_range must be [min, max] with min < max")
        )
    if errors:
        return errors
    for axis, lo, hi, step in (("x", x0, x1, spec.x_step), ("y", y0, y1, spec.y_step)):
        if step is not None and _tick_count(lo, hi, step) > _MAX_TICKS:
            errors.append(
                RenderSpecError(
                    "too_many_ticks",
                    f"{axis}_step",
                    f"{axis}_step {step:g} gives more than {_MAX_TICKS} ticks; use a larger step",
                )
            )
    eps = 1e-9
    for i, point in enumerate(spec.points):
        if not (x0 - eps <= point.x <= x1 + eps and y0 - eps <= point.y <= y1 + eps):
            errors.append(
                RenderSpecError(
                    "point_out_of_range",
                    f"points[{i}]",
                    f"point ({point.x:g}, {point.y:g}) lies outside the plotted ranges; "
                    "move it or widen the ranges",
                )
            )
    for i, curve in enumerate(spec.curves):
        path = f"curves[{i}]"
        if isinstance(curve, PolylineCurve):
            for j, (px, py) in enumerate(curve.points):
                if not (x0 - eps <= px <= x1 + eps and y0 - eps <= py <= y1 + eps):
                    errors.append(
                        RenderSpecError(
                            "point_out_of_range",
                            f"{path}.points[{j}]",
                            f"polyline point ({px:g}, {py:g}) lies outside the plotted ranges",
                        )
                    )
            continue
        _xs, ys = _sample(curve, x0, x1)
        if not bool(np.any((ys >= y0 - eps) & (ys <= y1 + eps))):
            errors.append(
                RenderSpecError(
                    "curve_not_visible",
                    path,
                    f"curve never enters y_range [{y0:g}, {y1:g}] for x in [{x0:g}, {x1:g}]; "
                    "change the ranges or the curve",
                )
            )
    seen: set[str] = set()
    for i, curve in enumerate(spec.curves):
        if curve.label:
            key = curve.label.strip().casefold()
            if key in seen:
                errors.append(
                    RenderSpecError(
                        "duplicate_label",
                        f"curves[{i}].label",
                        f"label {curve.label!r} is used twice",
                    )
                )
            seen.add(key)
    return errors


def _curve_text(curve: Curve) -> str:
    name = f" ({curve.label})" if curve.label else ""
    if isinstance(curve, LinearCurve):
        return f"straight line with gradient {curve.m:g} and y-intercept {curve.c:g}{name}"
    if isinstance(curve, QuadraticCurve):
        return f"parabola with a={curve.a:g}, b={curve.b:g}, c={curve.c:g}{name}"
    return f"line through {len(curve.points)} points{name}"


def describe(spec: FunctionGraphSpec) -> str:
    x0, x1 = spec.x_range
    y0, y1 = spec.y_range
    parts = [f"Graph with x from {x0:g} to {x1:g} and y from {y0:g} to {y1:g}"]
    if spec.curves:
        parts.append("showing " + "; ".join(_curve_text(c) for c in spec.curves))
    labelled = [
        f"{p.label} at ({p.x:g}, {p.y:g})" if p.label else f"({p.x:g}, {p.y:g})"
        for p in spec.points
    ]
    if labelled:
        parts.append("points " + ", ".join(labelled))
    return "; ".join(parts) + "."


def numbers(spec: FunctionGraphSpec) -> list[float]:
    return []


GALLERY: dict[str, dict] = {
    "function_graph_line": {
        "family": "function_graph",
        "x_range": [-5, 5],
        "y_range": [-5, 5],
        "grid": True,
        "curves": [{"form": "linear", "m": 2, "c": 1, "label": "y = 2x + 1"}],
        "points": [{"x": 0, "y": 1, "label": "(0, 1)"}],
    },
    "function_graph_parabola": {
        "family": "function_graph",
        "x_range": [-4, 4],
        "y_range": [-5, 6],
        "grid": True,
        "curves": [{"form": "quadratic", "a": 1, "b": 0, "c": -4, "label": "y = x² - 4"}],
        "points": [
            {"x": -2, "y": 0, "label": "(-2, 0)"},
            {"x": 2, "y": 0, "label": "(2, 0)"},
        ],
    },
    "function_graph_intersection": {
        "family": "function_graph",
        "x_range": [-2, 6],
        "y_range": [-2, 6],
        "grid": True,
        "curves": [
            {"form": "linear", "m": 1, "c": 0, "label": "y = x"},
            {"form": "linear", "m": -1, "c": 4, "label": "y = -x + 4"},
        ],
        "points": [{"x": 2, "y": 2, "label": "(2, 2)"}],
    },
}

__all__ = ["GALLERY", "describe", "draw", "numbers", "validate"]
