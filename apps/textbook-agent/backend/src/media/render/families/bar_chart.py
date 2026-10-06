"""``bar_chart``: vertical or horizontal bars, one to three series.

The y axis is chosen here (nice maximum and step) unless the spec fixes it, so
a chart never ends on an awkward scale. Bars are plain shades with an ink edge
so the figure survives greyscale printing.
"""

from __future__ import annotations

import math
import textwrap
from collections.abc import Sequence

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.text import Text
from matplotlib.ticker import FixedLocator

from media.render.contracts import BarChartSpec, RenderSpecError
from media.render.layout import find_clashes, fit_labels
from media.render.style import GRID, INK, SHADES, THIN

_MAX_TICKS = 12
_SERIES_SHADES = {
    1: (SHADES[1],),
    2: (SHADES[3], SHADES[0]),
    3: (SHADES[3], SHADES[1], SHADES[0]),
}


def _tick_text(value: float) -> str:
    return f"{value:g}"


def nice_axis(top: float) -> tuple[float, float]:
    """Smallest nice step giving at most eight intervals, and the rounded-up maximum."""
    if top <= 0:
        return 1.0, 0.2
    base = math.floor(math.log10(top))
    for exponent in range(base - 1, base + 2):
        for mult in (1, 2, 5):
            step = mult * 10.0**exponent
            n = math.ceil(top / step - 1e-9)
            if n <= 8:
                return round(n * step, 10), round(step, 10)
    step = 10.0 ** (base + 1)
    return step, step


def axis_scale(spec: BarChartSpec) -> tuple[float, float]:
    top = max(v for s in spec.series for v in s.values)
    auto_max, auto_step = nice_axis(top)
    if spec.y_max is None:
        return auto_max, auto_step
    if spec.y_step is not None:
        return spec.y_max, spec.y_step
    # Fixed maximum without a step: pick a step that divides it neatly.
    for exponent in range(-2, 6):
        for mult in (1, 2, 2.5, 5):
            step = mult * 10.0**exponent
            ratio = spec.y_max / step
            if abs(ratio - round(ratio)) < 1e-6 and 3 <= round(ratio) <= 6:
                return spec.y_max, step
    return spec.y_max, spec.y_max / 5


def _wrap(label: str, width: int) -> str:
    return "\n".join(textwrap.wrap(label, width=width, break_long_words=False)) or label


def draw(spec: BarChartSpec) -> Figure:
    n_cat = len(spec.categories)
    n_ser = len(spec.series)
    y_max, y_step = axis_scale(spec)
    horizontal = spec.orientation == "horizontal"
    colours = _SERIES_SHADES[n_ser]
    ticks = [round(i * y_step, 10) for i in range(int(round(y_max / y_step)) + 1)]

    def build(font_size: float) -> tuple[Figure, Sequence[Text], Sequence[Artist]]:
        width = 6.2
        height = 4.2 if not horizontal else min(6.0, 1.6 + 0.55 * n_cat * max(1.0, n_ser * 0.7))
        modes: list[tuple[int, int]] = [(14, 0), (9, 0), (6, 0), (6, 30), (6, 45)]
        if horizontal:
            modes = [(22, 0), (14, 0)]
        fig: Figure | None = None
        tick_texts: list[Text] = []
        for wrap_width, rotation in modes:
            fig = Figure(figsize=(width, height), layout="constrained")
            ax = fig.add_subplot()
            bar = 0.8 / n_ser
            positions = list(range(n_cat))
            for s_index, series in enumerate(spec.series):
                offset = (s_index - (n_ser - 1) / 2) * bar
                coords = [p + offset for p in positions]
                kwargs = {
                    "color": colours[s_index],
                    "edgecolor": INK,
                    "linewidth": THIN,
                    "label": series.name,
                    "zorder": 3,
                }
                if horizontal:
                    ax.barh(coords, series.values, height=bar, **kwargs)
                else:
                    ax.bar(coords, series.values, width=bar, **kwargs)
            names = [_wrap(c, wrap_width) for c in spec.categories]
            tick_labels = [_tick_text(t) for t in ticks]
            if horizontal:
                ax.set_ylim(n_cat - 0.4, -0.6)
                ax.set_xlim(0, y_max)
                ax.set_yticks(positions)
                ax.set_yticklabels(names, fontsize=font_size)
                ax.xaxis.set_major_locator(FixedLocator(ticks))
                ax.set_xticklabels(tick_labels, fontsize=font_size)
                ax.grid(axis="x", color=GRID, linewidth=1.0, zorder=0)
                ax.set_xlabel(spec.y_label or "", fontsize=font_size)
                ax.set_ylabel(spec.x_label or "", fontsize=font_size)
                cat_axis, val_axis = ax.yaxis, ax.xaxis
            else:
                ax.set_xlim(-0.6, n_cat - 0.4)
                ax.set_ylim(0, y_max)
                ax.set_xticks(positions)
                ax.set_xticklabels(
                    names,
                    fontsize=font_size,
                    rotation=rotation,
                    ha="right" if rotation else "center",
                    rotation_mode="anchor",
                )
                ax.yaxis.set_major_locator(FixedLocator(ticks))
                ax.set_yticklabels(tick_labels, fontsize=font_size)
                ax.grid(axis="y", color=GRID, linewidth=1.0, zorder=0)
                ax.set_xlabel(spec.x_label or "", fontsize=font_size)
                ax.set_ylabel(spec.y_label or "", fontsize=font_size)
                cat_axis, val_axis = ax.xaxis, ax.yaxis
            ax.set_axisbelow(True)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            for side in ("left", "bottom"):
                ax.spines[side].set_color(INK)
                ax.spines[side].set_linewidth(THIN)
            cat_axis.set_tick_params(length=0 if not horizontal else 4, pad=4)
            val_axis.set_tick_params(length=4, width=THIN)
            if n_ser > 1:
                handles, labels = ax.get_legend_handles_labels()
                fig.legend(
                    handles,
                    labels,
                    loc="outside upper center",
                    ncol=n_ser,
                    frameon=False,
                    fontsize=font_size,
                )
            fig.draw_without_rendering()
            tick_texts = [t for t in cat_axis.get_ticklabels() if t.get_text()]
            if not find_clashes(fig, tick_texts):
                break
        assert fig is not None
        return fig, tick_texts, []

    return fit_labels(build)


def validate(spec: BarChartSpec) -> list[RenderSpecError]:
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
    for s_index, series in enumerate(spec.series):
        path = f"series[{s_index}]"
        if len(series.values) != n:
            errors.append(
                RenderSpecError(
                    "length_mismatch",
                    f"{path}.values",
                    f"series has {len(series.values)} values but there are {n} categories; "
                    "give exactly one value per category",
                )
            )
        for v_index, value in enumerate(series.values):
            if value < 0:
                errors.append(
                    RenderSpecError(
                        "negative_value",
                        f"{path}.values[{v_index}]",
                        "bar values must be 0 or more",
                    )
                )
        if len(spec.series) > 1 and not (series.name and series.name.strip()):
            errors.append(
                RenderSpecError(
                    "series_needs_name",
                    f"{path}.name",
                    "with several series every series needs a name for the legend",
                )
            )
    if errors:
        return errors
    top = max(v for s in spec.series for v in s.values)
    if spec.y_max is not None and spec.y_max < top:
        errors.append(
            RenderSpecError(
                "y_max_too_small",
                "y_max",
                f"y_max {spec.y_max:g} is below the largest value {top:g}; raise it",
            )
        )
    if spec.y_step is not None:
        if spec.y_max is None:
            errors.append(
                RenderSpecError("y_step_needs_y_max", "y_step", "y_step needs y_max to be set too")
            )
        else:
            ratio = spec.y_max / spec.y_step
            if abs(ratio - round(ratio)) > 1e-6:
                errors.append(
                    RenderSpecError(
                        "y_step_not_divisor",
                        "y_step",
                        f"y_step {spec.y_step:g} must divide y_max {spec.y_max:g} exactly",
                    )
                )
            elif round(ratio) + 1 > _MAX_TICKS:
                errors.append(
                    RenderSpecError(
                        "too_many_ticks",
                        "y_step",
                        f"y_step gives {round(ratio) + 1} ticks; use at most {_MAX_TICKS}",
                    )
                )
    return errors


def describe(spec: BarChartSpec) -> str:
    direction = "Horizontal" if spec.orientation == "horizontal" else "Vertical"
    parts = [f"{direction} bar chart of {', '.join(spec.categories)}"]
    for series in spec.series:
        values = ", ".join(f"{c} {v:g}" for c, v in zip(spec.categories, series.values))
        parts.append(f"{series.name}: {values}" if series.name else f"values: {values}")
    return "; ".join(parts) + "."


def numbers(spec: BarChartSpec) -> list[float]:
    return [float(v) for series in spec.series for v in series.values]


GALLERY: dict[str, dict] = {
    "bar_chart_single": {
        "family": "bar_chart",
        "categories": ["Apples", "Bananas", "Grapes", "Oranges", "Strawberries"],
        "series": [{"name": "Favourite fruit", "values": [8, 12, 5, 9, 14]}],
        "x_label": "Fruit",
        "y_label": "Number of pupils",
    },
    "bar_chart_grouped": {
        "family": "bar_chart",
        "categories": ["Maths", "English", "Science", "History"],
        "series": [
            {"name": "Year 7", "values": [18, 22, 15, 10]},
            {"name": "Year 8", "values": [20, 17, 24, 13]},
        ],
        "x_label": "Subject",
        "y_label": "Pupils",
        "y_max": 30,
        "y_step": 5,
    },
    "bar_chart_horizontal": {
        "family": "bar_chart",
        "categories": ["Walk", "Bus", "Car", "Cycle"],
        "series": [{"values": [14, 9, 6, 3]}],
        "x_label": "Travel to school",
        "y_label": "Number of pupils",
        "orientation": "horizontal",
    },
}

__all__ = ["GALLERY", "axis_scale", "describe", "draw", "nice_axis", "numbers", "validate"]
