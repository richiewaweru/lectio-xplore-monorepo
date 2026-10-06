"""``number_line``: a ruled line with ticks, points, jump arcs and shaded intervals.

Tick positions come from ``start``/``step`` only, so labels cannot disagree with
the drawing. Fractions are simplified (2/4 shows as 1/2).
"""

from __future__ import annotations

from fractions import Fraction

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse, FancyArrowPatch, Rectangle
from matplotlib.text import Text

from media.render import geometry as g
from media.render.contracts import NumberLineSpec, RenderSpecError
from media.render.layout import fit_labels
from media.render.style import INK, LINE, SHADES, THIN

_EPS = 1e-9
_MAX_TICKS = 25
_WIDTH_IN = 6.0
_BELOW_IN = 0.55
_ABOVE_IN = 1.05
_SIDE_PAD_IN = 0.45  # room for the arrowheads at both ends
_TICK_IN = 0.08
_DOT_R_IN = 0.065
_MINUS = "−"


def _signed(text: str, negative: bool) -> str:
    return (_MINUS + text) if negative else text


def format_fraction(value: float, denominator: int) -> str:
    """``value`` as a simplified ``n/d`` (whole numbers and zero as integers)."""
    frac = Fraction(round(value * denominator), denominator)
    if frac.denominator == 1:
        return _signed(str(abs(frac.numerator)), frac < 0)
    return _signed(f"{abs(frac.numerator)}/{frac.denominator}", frac < 0)


def tick_text(spec: NumberLineSpec, value: float) -> str:
    if spec.tick_format == "fraction" and spec.denominator:
        return format_fraction(value, spec.denominator)
    if spec.tick_format == "decimal":
        rounded = round(value, 3)
        if abs(rounded - round(rounded)) < _EPS:
            text = str(abs(int(round(rounded))))
        else:
            text = f"{abs(rounded):.3f}".rstrip("0").rstrip(".")
        return _signed(text, rounded < 0)
    rounded_int = int(round(value))
    return _signed(str(abs(rounded_int)), rounded_int < 0)


def _tick_count(spec: NumberLineSpec) -> int:
    return int(round((spec.end - spec.start) / spec.step)) + 1


def tick_values(spec: NumberLineSpec) -> list[float]:
    return [round(spec.start + i * spec.step, 9) for i in range(_tick_count(spec))]


def draw(spec: NumberLineSpec) -> Figure:
    span = spec.end - spec.start
    per_in = span / (_WIDTH_IN - 2 * _SIDE_PAD_IN)  # data units per inch
    x_lo = spec.start - _SIDE_PAD_IN * per_in
    x_hi = spec.end + _SIDE_PAD_IN * per_in
    ticks = tick_values(spec)
    above = _ABOVE_IN if spec.jumps else 0.6
    run_off = 0.12 * per_in  # unbounded intervals stop just short of the arrowhead

    def build(font_size: float) -> tuple[Figure, list[Text], list[Artist]]:
        fig = Figure(figsize=(_WIDTH_IN, _BELOW_IN + above))
        ax = fig.add_axes((0, 0, 1, 1))
        # x in number-line units; y in inches above the line.
        ax.set_xlim(x_lo, x_hi)
        ax.set_ylim(-_BELOW_IN, above)
        ax.axis("off")

        texts: list[Text] = []
        obstacles: list[Artist] = []

        def bounds(start: float | None, end: float | None) -> tuple[float, float]:
            return (
                start if start is not None else x_lo + run_off,
                end if end is not None else x_hi - run_off,
            )

        # Intervals first, so the line and ticks sit on top.
        for interval in spec.intervals:
            lo, hi = bounds(interval.start, interval.end)
            ax.add_patch(
                Rectangle(
                    (lo, -0.055), hi - lo, 0.11, facecolor=SHADES[3], edgecolor="none", zorder=1
                )
            )

        ax.annotate(
            "",
            xy=(x_hi, 0),
            xytext=(x_lo, 0),
            arrowprops={
                "arrowstyle": "<|-|>",
                "color": INK,
                "lw": LINE,
                "mutation_scale": 14,
                "shrinkA": 0,
                "shrinkB": 0,
            },
            zorder=2,
        )

        for value in ticks:
            ax.plot([value, value], [-_TICK_IN, _TICK_IN], color=INK, linewidth=THIN, zorder=3)
            texts.append(
                ax.text(
                    value,
                    -_TICK_IN - 0.05,
                    tick_text(spec, value),
                    ha="center",
                    va="top",
                    fontsize=font_size,
                    color=INK,
                )
            )

        def dot(value: float, closed: bool) -> None:
            # An ellipse in data units: the x scale differs from the y (inch) scale.
            ax.add_patch(
                Ellipse(
                    (value, 0),
                    2 * _DOT_R_IN * per_in,
                    2 * _DOT_R_IN,
                    facecolor=INK if closed else "white",
                    edgecolor=INK,
                    linewidth=LINE,
                    zorder=5,
                )
            )

        for interval in spec.intervals:
            if interval.start is not None:
                dot(interval.start, interval.start_closed)
            if interval.end is not None:
                dot(interval.end, interval.end_closed)
            if interval.label:
                lo, hi = bounds(interval.start, interval.end)
                texts.append(
                    ax.text(
                        (lo + hi) / 2,
                        0.17,
                        interval.label,
                        ha="center",
                        va="bottom",
                        fontsize=font_size,
                        color=INK,
                    )
                )

        for point in spec.points:
            dot(point.value, point.style == "closed")
            if point.label:
                texts.append(
                    ax.text(
                        point.value,
                        0.17,
                        point.label,
                        ha="center",
                        va="bottom",
                        fontsize=font_size,
                        fontweight="bold",
                        color=INK,
                    )
                )

        for jump in spec.jumps:
            dist_in = abs(jump.end - jump.start) / per_in
            rise = min(0.5, max(0.22, 0.28 * dist_in))
            rad = 2 * rise / dist_in
            # arc3 bends to one side of the direction of travel; flip so arcs rise.
            sign = -1.0 if jump.end > jump.start else 1.0
            ax.add_patch(
                FancyArrowPatch(
                    (jump.start, 0.1),
                    (jump.end, 0.1),
                    connectionstyle=f"arc3,rad={sign * rad}",
                    arrowstyle="-|>",
                    mutation_scale=12,
                    color=INK,
                    linewidth=THIN,
                    shrinkA=0,
                    shrinkB=0,
                    zorder=4,
                )
            )
            if jump.label:
                texts.append(
                    ax.text(
                        (jump.start + jump.end) / 2,
                        0.1 + rise + 0.05,
                        jump.label,
                        ha="center",
                        va="bottom",
                        fontsize=font_size,
                        color=INK,
                    )
                )
        return fig, texts, obstacles

    return fit_labels(build)


def validate(spec: NumberLineSpec) -> list[RenderSpecError]:
    errors: list[RenderSpecError] = []
    if not spec.start < spec.end:
        errors.append(RenderSpecError("bad_range", "start", "start must be less than end"))
        return errors
    ratio = (spec.end - spec.start) / spec.step
    if abs(ratio - round(ratio)) > _EPS * max(1.0, ratio):
        errors.append(
            RenderSpecError(
                "step_not_dividing",
                "step",
                "step must divide (end - start) exactly so the last tick lands on end",
            )
        )
        return errors
    if _tick_count(spec) > _MAX_TICKS:
        errors.append(
            RenderSpecError(
                "too_many_ticks",
                "step",
                f"{_tick_count(spec)} ticks; at most {_MAX_TICKS} fit. Use a larger step",
            )
        )
        return errors
    if spec.tick_format == "fraction":
        if spec.denominator is None:
            errors.append(
                RenderSpecError(
                    "fraction_needs_denominator",
                    "denominator",
                    "tick_format 'fraction' requires a denominator such as 4",
                )
            )
        else:
            n = spec.step * spec.denominator
            if abs(n - round(n)) > 1e-6:
                errors.append(
                    RenderSpecError(
                        "step_not_fraction",
                        "step",
                        f"step times denominator must be a whole number; got {n:g}. "
                        "Use a step that is a multiple of 1/denominator",
                    )
                )

    def inside(value: float) -> bool:
        return spec.start - _EPS <= value <= spec.end + _EPS

    for i, point in enumerate(spec.points):
        if not inside(point.value):
            errors.append(
                RenderSpecError(
                    "point_out_of_range",
                    f"points[{i}].value",
                    f"{point.value:g} is outside [{spec.start:g}, {spec.end:g}]",
                )
            )
    for i, jump in enumerate(spec.jumps):
        for field, value in (("start", jump.start), ("end", jump.end)):
            if not inside(value):
                errors.append(
                    RenderSpecError(
                        "jump_out_of_range",
                        f"jumps[{i}].{field}",
                        f"{value:g} is outside [{spec.start:g}, {spec.end:g}]",
                    )
                )
        if abs(jump.start - jump.end) < _EPS:
            errors.append(
                RenderSpecError("jump_zero_length", f"jumps[{i}]", "jump start and end are equal")
            )
    for i, interval in enumerate(spec.intervals):
        for field, value in (("start", interval.start), ("end", interval.end)):
            if value is not None and not inside(value):
                errors.append(
                    RenderSpecError(
                        "interval_out_of_range",
                        f"intervals[{i}].{field}",
                        f"{value:g} is outside [{spec.start:g}, {spec.end:g}]; "
                        "use null to run off the end of the line",
                    )
                )
        if (
            interval.start is not None
            and interval.end is not None
            and not interval.start < interval.end
        ):
            errors.append(
                RenderSpecError(
                    "interval_not_ordered",
                    f"intervals[{i}]",
                    "interval start must be less than its end",
                )
            )
    return errors


def _value_text(spec: NumberLineSpec, value: float) -> str:
    if spec.tick_format == "integer":
        return g.format_number(value)
    return tick_text(spec, value)


def describe(spec: NumberLineSpec) -> str:
    parts = [
        f"Number line from {_value_text(spec, spec.start)} to {_value_text(spec, spec.end)}"
        f" with ticks every {_value_text(spec, spec.step)}"
    ]
    if spec.points:
        shown = []
        for p in spec.points:
            kind = "open" if p.style == "open" else "closed"
            shown.append(
                f"{kind} point at {_value_text(spec, p.value)}" + (f" ({p.label})" if p.label else "")
            )
        parts.append(", ".join(shown))
    for j in spec.jumps:
        parts.append(
            f"jump from {_value_text(spec, j.start)} to {_value_text(spec, j.end)}"
            + (f" labelled {j.label}" if j.label else "")
        )
    for iv in spec.intervals:
        lo = "the left end" if iv.start is None else _value_text(spec, iv.start)
        hi = "the right end" if iv.end is None else _value_text(spec, iv.end)
        parts.append(f"shaded from {lo} to {hi}")
    return "; ".join(parts) + "."


def numbers(spec: NumberLineSpec) -> list[float]:
    return []


GALLERY: dict[str, dict] = {
    "number_line_integers_jump": {
        "family": "number_line",
        "start": -5,
        "end": 5,
        "step": 1,
        "tick_format": "integer",
        "points": [
            {"value": -2, "label": "A", "style": "closed"},
            {"value": 1, "label": "B", "style": "closed"},
        ],
        "jumps": [{"start": -2, "end": 1, "label": "+3"}],
    },
    "number_line_fractions": {
        "family": "number_line",
        "start": 0,
        "end": 2,
        "step": 0.25,
        "tick_format": "fraction",
        "denominator": 4,
        "points": [{"value": 0.75, "label": "3/4", "style": "closed"}],
    },
    "number_line_inequality": {
        "family": "number_line",
        "start": -5,
        "end": 5,
        "step": 1,
        "tick_format": "integer",
        "intervals": [{"start": -2, "end": None, "start_closed": False, "label": "x > −2"}],
    },
}

__all__ = [
    "GALLERY",
    "describe",
    "draw",
    "format_fraction",
    "numbers",
    "tick_text",
    "validate",
]
