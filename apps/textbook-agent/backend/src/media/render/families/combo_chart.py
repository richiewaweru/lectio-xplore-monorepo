"""``combo_chart``: category bars on the left axis and a joined line on the right axis.

Two measures with different units (rainfall in mm, temperature in degrees C)
share one set of categories. Bars use the house shades with an ink edge and the
line is ink with round markers, drawn above the bars so it survives greyscale.
Only the left axis draws gridlines, so the two scales never fight.
"""

from __future__ import annotations

import math
import textwrap
from collections.abc import Sequence

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.text import Text
from matplotlib.ticker import FixedLocator

from media.render.contracts import ComboChartSpec, ComboSeries, RenderSpecError
from media.render.families.bar_chart import nice_axis
from media.render.layout import find_clashes, fit_labels
from media.render.style import GRID, INK, LINE, SHADES, THIN

_MAX_TICKS = 12


def _tick_text(value: float) -> str:
    return f"{value:g}"


def _fixed_step(lo: float, hi: float) -> float:
    """A neat step that divides lo..hi exactly into 3-8 intervals, else five equal ones."""
    span = hi - lo
    for low_n, high_n in ((3, 6), (3, 8)):
        for exponent in range(-3, 7):
            for mult in (1, 2, 2.5, 5):
                step = mult * 10.0**exponent
                ratio = span / step
                if abs(ratio - round(ratio)) < 1e-6 and low_n <= round(ratio) <= high_n:
                    return step
    return span / 5


def _ticks(lo: float, hi: float, step: float) -> list[float]:
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 10) for i in range(n + 1)]


def left_scale(spec: ComboChartSpec) -> tuple[float, float, float]:
    bars = spec.bars
    lo = 0.0 if bars.axis_min is None else bars.axis_min
    if bars.axis_max is not None:
        return lo, bars.axis_max, _fixed_step(lo, bars.axis_max)
    top, step = nice_axis(max(bars.values))
    return lo, max(top, lo + step), step


def right_scale(spec: ComboChartSpec) -> tuple[float, float, float]:
    line = spec.line
    if line.axis_min is not None and line.axis_max is not None:
        return line.axis_min, line.axis_max, _fixed_step(line.axis_min, line.axis_max)
    low, high = min(line.values), max(line.values)
    span = (high - low) or max(abs(high), 1.0)
    step = nice_axis(span * 1.4)[1]
    lo = (
        line.axis_min
        if line.axis_min is not None
        else math.floor((low - 0.1 * span) / step) * step
    )
    hi = (
        line.axis_max
        if line.axis_max is not None
        else math.ceil((high + 0.1 * span) / step) * step
    )
    lo, hi = round(lo, 10), round(hi, 10)
    ratio = (hi - lo) / step
    if abs(ratio - round(ratio)) > 1e-6:
        step = _fixed_step(lo, hi)
    return lo, hi, step


def _wrap(label: str, width: int) -> str:
    return "\n".join(textwrap.wrap(label, width=width, break_long_words=False)) or label


def draw(spec: ComboChartSpec) -> Figure:
    n_cat = len(spec.categories)
    l_lo, l_hi, l_step = left_scale(spec)
    r_lo, r_hi, r_step = right_scale(spec)
    l_ticks = _ticks(l_lo, l_hi, l_step)
    r_ticks = _ticks(r_lo, r_hi, r_step)
    positions = list(range(n_cat))

    def build(font_size: float) -> tuple[Figure, Sequence[Text], Sequence[Artist]]:
        modes: list[tuple[int, int]] = [(14, 0), (9, 0), (6, 0), (6, 30), (6, 45)]
        fig: Figure | None = None
        tick_texts: list[Text] = []
        for wrap_width, rotation in modes:
            fig = Figure(figsize=(6.6, 4.4), layout="constrained")
            ax = fig.add_subplot()
            ax.bar(
                positions,
                spec.bars.values,
                width=0.6,
                color=SHADES[1],
                edgecolor=INK,
                linewidth=THIN,
                label=spec.bars.name,
                zorder=3,
            )
            ax2 = ax.twinx()
            ax2.plot(
                positions,
                spec.line.values,
                color=INK,
                linewidth=LINE,
                marker="o",
                markersize=7,
                markerfacecolor=INK,
                label=spec.line.name,
                zorder=5,
            )
            ax.set_xlim(-0.6, n_cat - 0.4)
            ax.set_ylim(l_lo, l_hi)
            ax2.set_ylim(r_lo, r_hi)
            ax.set_xticks(positions)
            ax.set_xticklabels(
                [_wrap(c, wrap_width) for c in spec.categories],
                fontsize=font_size,
                rotation=rotation,
                ha="right" if rotation else "center",
                rotation_mode="anchor",
            )
            ax.yaxis.set_major_locator(FixedLocator(l_ticks))
            ax.set_yticklabels([_tick_text(t) for t in l_ticks], fontsize=font_size)
            ax2.yaxis.set_major_locator(FixedLocator(r_ticks))
            ax2.set_yticklabels([_tick_text(t) for t in r_ticks], fontsize=font_size)
            ax.grid(axis="y", color=GRID, linewidth=1.0, zorder=0)
            ax2.grid(False)
            ax.set_axisbelow(True)
            ax.set_xlabel(spec.x_label or "", fontsize=font_size)
            ax.set_ylabel(spec.bars.axis_label or spec.bars.name, fontsize=font_size)
            ax2.set_ylabel(spec.line.axis_label or spec.line.name, fontsize=font_size)
            ax.spines["top"].set_visible(False)
            ax2.spines["top"].set_visible(False)
            for side in ("left", "bottom"):
                ax.spines[side].set_color(INK)
                ax.spines[side].set_linewidth(THIN)
            ax2.spines["right"].set_color(INK)
            ax2.spines["right"].set_linewidth(THIN)
            ax2.spines["left"].set_visible(False)
            ax2.spines["bottom"].set_visible(False)
            ax.xaxis.set_tick_params(length=0, pad=4)
            ax.yaxis.set_tick_params(length=4, width=THIN)
            ax2.yaxis.set_tick_params(length=4, width=THIN)
            if spec.title:
                fig.suptitle(spec.title, fontsize=font_size, wrap=True)
            bar_handles, bar_labels = ax.get_legend_handles_labels()
            line_handles, line_labels = ax2.get_legend_handles_labels()
            fig.legend(
                [*bar_handles, *line_handles],
                [*bar_labels, *line_labels],
                loc="outside lower center",
                ncol=2,
                frameon=False,
                fontsize=font_size,
            )
            fig.draw_without_rendering()
            tick_texts = [t for t in ax.xaxis.get_ticklabels() if t.get_text()]
            if not find_clashes(fig, tick_texts):
                break
        assert fig is not None
        return fig, tick_texts, []

    return fit_labels(build)


def _check_series(
    series: ComboSeries, path: str, n: int, *, non_negative: bool
) -> list[RenderSpecError]:
    errors: list[RenderSpecError] = []
    if len(series.values) != n:
        errors.append(
            RenderSpecError(
                "length_mismatch",
                f"{path}.values",
                f"{path} has {len(series.values)} values but there are {n} categories; "
                "give exactly one value per category",
            )
        )
        return errors
    if non_negative:
        for v_index, value in enumerate(series.values):
            if value < 0:
                errors.append(
                    RenderSpecError(
                        "negative_value",
                        f"{path}.values[{v_index}]",
                        "bar values must be 0 or more",
                    )
                )
    lo, hi = series.axis_min, series.axis_max
    if lo is not None and hi is not None and hi <= lo:
        errors.append(
            RenderSpecError(
                "axis_range_invalid", f"{path}.axis_max", "axis_max must be greater than axis_min"
            )
        )
        return errors
    if hi is not None and hi < max(series.values):
        errors.append(
            RenderSpecError(
                "axis_max_too_small",
                f"{path}.axis_max",
                f"axis_max {hi:g} is below the largest value {max(series.values):g}; raise it",
            )
        )
    if lo is not None and lo > min(series.values):
        errors.append(
            RenderSpecError(
                "axis_min_too_large",
                f"{path}.axis_min",
                f"axis_min {lo:g} is above the smallest value {min(series.values):g}; lower it",
            )
        )
    return errors


def validate(spec: ComboChartSpec) -> list[RenderSpecError]:
    errors: list[RenderSpecError] = []
    n = len(spec.categories)
    seen: set[str] = set()
    for index, category in enumerate(spec.categories):
        key = category.strip().casefold()
        if key in seen:
            errors.append(
                RenderSpecError(
                    "duplicate_category",
                    f"categories[{index}]",
                    f"category {category!r} appears twice; rename one",
                )
            )
        seen.add(key)
    errors += _check_series(spec.bars, "bars", n, non_negative=True)
    errors += _check_series(spec.line, "line", n, non_negative=False)
    if errors:
        return errors
    for path, (lo, hi, step) in (("bars", left_scale(spec)), ("line", right_scale(spec))):
        ticks = int(round((hi - lo) / step)) + 1
        if ticks > _MAX_TICKS:
            errors.append(
                RenderSpecError(
                    "too_many_ticks",
                    f"{path}.axis_max",
                    f"the {path} axis would need {ticks} ticks; use at most {_MAX_TICKS}",
                )
            )
    return errors


def describe(spec: ComboChartSpec) -> str:
    bar_label = spec.bars.axis_label or spec.bars.name
    line_label = spec.line.axis_label or spec.line.name
    parts = [
        f"Combination chart over {', '.join(spec.categories)}, with {spec.bars.name} as bars "
        f"on the left axis ({bar_label}) and {spec.line.name} as a line with markers on the "
        f"right axis ({line_label})"
    ]
    for category, bar, line in zip(spec.categories, spec.bars.values, spec.line.values):
        parts.append(f"{category}: {spec.bars.name} {bar:g}, {spec.line.name} {line:g}")
    return "; ".join(parts) + "."


def numbers(spec: ComboChartSpec) -> list[float]:
    values = [float(v) for v in spec.bars.values] + [float(v) for v in spec.line.values]
    for series in (spec.bars, spec.line):
        for bound in (series.axis_min, series.axis_max):
            if bound is not None:
                values.append(float(bound))
    return values


GALLERY: dict[str, dict] = {
    "combo_chart_weather": {
        "family": "combo_chart",
        "categories": [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ],
        "bars": {
            "name": "Rainfall",
            "values": [0, 12, 4, 0, 18, 6, 2],
            "axis_label": "Rainfall (mm)",
            "axis_max": 20,
        },
        "line": {
            "name": "Temperature",
            "values": [18, 16, 19, 21, 15, 17, 20],
            "axis_label": "Temperature (°C)",
            "axis_min": 14,
            "axis_max": 22,
        },
        "title": (
            "Daily rainfall and temperature at Oakfield School weather station, Monday to Sunday"
        ),
        "x_label": "Day",
    },
    "combo_chart_sales": {
        "family": "combo_chart",
        "categories": ["Jan", "Feb", "Mar", "Apr", "May"],
        "bars": {"name": "Sales", "values": [40, 55, 48, 62, 70], "axis_label": "Sales (units)"},
        "line": {
            "name": "Profit",
            "values": [4.2, 6.1, 5.0, 7.4, 8.8],
            "axis_label": "Profit ($000)",
        },
        "x_label": "Month",
    },
}

__all__ = ["GALLERY", "describe", "draw", "left_scale", "numbers", "right_scale", "validate"]
