"""Build a chart render spec straight from a figure's chart declaration and data.

A declaration names which ``data`` keys are the categories and the series, so the
chart is drawn by code from the plan's exact numbers and no model is involved.
Pure functions that never raise; this module must stay independent of ``document``
and ``curriculum``.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from media.render.contracts import BarChartSpec, BarSeries, ComboChartSpec, ComboSeries, RenderSpec


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _numbers(data: dict, key: Any) -> list[float] | None:
    values = data.get(key) if isinstance(key, str) else None
    if not isinstance(values, list) or not values or not all(_is_number(v) for v in values):
        return None
    return [float(v) for v in values]


def _categories(data: dict, key: Any) -> list[str] | None:
    values = data.get(key) if isinstance(key, str) else None
    if not isinstance(values, list) or not values:
        return None
    if any(isinstance(v, (dict, list)) or v is None for v in values):
        return None
    return [str(v) for v in values]


def _opt_number(value: Any) -> float | None:
    return float(value) if _is_number(value) else None


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _combo_series(data: dict, decl: Any, size: int) -> ComboSeries | None:
    if not isinstance(decl, dict):
        return None
    values = _numbers(data, decl.get("key"))
    label = _text(decl.get("label"))
    if values is None or label is None or len(values) != size:
        return None
    return ComboSeries(
        name=label,
        values=values,
        axis_label=label,
        axis_min=_opt_number(decl.get("min")),
        axis_max=_opt_number(decl.get("max")),
    )


def _combo(chart: dict, data: dict, title: str | None) -> RenderSpec | None:
    categories = _categories(data, chart.get("categories"))
    if categories is None:
        return None
    bars = _combo_series(data, chart.get("bars"), len(categories))
    line = _combo_series(data, chart.get("line"), len(categories))
    if bars is None or line is None:
        return None
    return ComboChartSpec(categories=categories, bars=bars, line=line, title=_text(title))


def _bar(chart: dict, data: dict) -> RenderSpec | None:
    categories = _categories(data, chart.get("categories"))
    declared = chart.get("series")
    if categories is None or not isinstance(declared, list) or not declared:
        return None
    series: list[BarSeries] = []
    for item in declared:
        if not isinstance(item, dict):
            return None
        values = _numbers(data, item.get("key"))
        if values is None or len(values) != len(categories):
            return None
        series.append(BarSeries(name=_text(item.get("label")), values=values))
    return BarChartSpec(
        categories=categories,
        series=series,
        x_label=_text(chart.get("x_label")),
        y_label=_text(chart.get("y_label")),
        y_max=_opt_number(chart.get("y_max")),
    )


def chart_spec_from_declaration(
    chart: dict | None, data: dict | None, *, title: str | None = None
) -> RenderSpec | None:
    """The chart spec a declaration describes over ``data``, or ``None`` if it does not fit."""
    if not isinstance(chart, dict) or not isinstance(data, dict):
        return None
    try:
        kind = chart.get("kind")
        if kind == "combo":
            return _combo(chart, data, title)
        if kind == "bar":
            return _bar(chart, data)
    except (ValidationError, TypeError, ValueError):
        return None
    return None


__all__ = ["chart_spec_from_declaration"]
