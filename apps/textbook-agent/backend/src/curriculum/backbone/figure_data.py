"""Deterministic checks that a backbone figure's numbers agree with its own data.

Kept out of the pydantic model on purpose so stored backbones still load; the
backbone writer calls this on freshly generated output and feeds the messages
into its repair prompt.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from curriculum.backbone.models import (
    BackboneFigure,
    BarChartDeclaration,
    ComboChartDeclaration,
    LessonBackbone,
)

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _numbers_in_text(text: str) -> set[Decimal]:
    found: set[Decimal] = set()
    for token in _NUMBER.findall(text):
        try:
            found.add(Decimal(token))
        except InvalidOperation:  # pragma: no cover - regex guarantees a number
            continue
    return found


def _numbers_in_value(value: Any) -> set[Decimal]:
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, (int, float)):
        return {Decimal(str(value))}
    if isinstance(value, str):
        return _numbers_in_text(value)
    if isinstance(value, dict):
        found: set[Decimal] = set()
        for item in value.values():
            found |= _numbers_in_value(item)
        return found
    if isinstance(value, (list, tuple)):
        found = set()
        for item in value:
            found |= _numbers_in_value(item)
        return found
    return set()


def _is_series(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
    )


# Mirror of the code table limits in media/render/contracts.py (TableSpec); kept as
# literals so the backbone package imports nothing from media.
_MAX_SERIES_ENTRIES = 12
_MAX_SERIES_COUNT = 8


def _fmt(number: Decimal) -> str:
    return format(number.normalize(), "f")


_MAX_CHART_CATEGORIES = 12
_MAX_BAR_SERIES = 3


def _is_number_list(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 1
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
    )


def _chart_errors(figure: BackboneFigure) -> list[str]:
    """Checks for the optional ``chart`` declaration; every message names the figure."""
    chart = figure.chart
    if chart is None:
        return []
    fid = figure.id
    data = figure.data or {}
    errors: list[str] = []
    if figure.effective_mode != "render":
        errors.append(
            f"BACKBONE_FIGURE_CHART_NEEDS_RENDER: figure {fid} declares a chart but mode "
            f"is '{figure.effective_mode}'; chart needs mode render"
        )

    categories = data.get(chart.categories)
    category_count: int | None = None
    if chart.categories not in data:
        errors.append(
            f"BACKBONE_FIGURE_CHART_KEY_MISSING: figure {fid} chart categories key "
            f"'{chart.categories}' is not a key of data"
        )
    elif not (
        isinstance(categories, (list, tuple))
        and categories
        and all(isinstance(item, str) for item in categories)
    ):
        errors.append(
            f"BACKBONE_FIGURE_CHART_CATEGORIES: figure {fid} data['{chart.categories}'] "
            "must be a list of category names (strings)"
        )
    else:
        category_count = len(categories)
        if category_count > _MAX_CHART_CATEGORIES:
            errors.append(
                f"BACKBONE_FIGURE_CHART_TOO_MANY_CATEGORIES: figure {fid} has "
                f"{category_count} categories; at most {_MAX_CHART_CATEGORIES}"
            )

    def check_series(key: str, role: str) -> list[Any] | None:
        if key not in data:
            errors.append(
                f"BACKBONE_FIGURE_CHART_KEY_MISSING: figure {fid} chart {role} key "
                f"'{key}' is not a key of data"
            )
            return None
        values = data[key]
        if not _is_number_list(values):
            errors.append(
                f"BACKBONE_FIGURE_CHART_SERIES_NOT_NUMERIC: figure {fid} data['{key}'] "
                f"({role}) must be a list of numbers"
            )
            return None
        if category_count is not None and len(values) != category_count:
            errors.append(
                f"BACKBONE_FIGURE_CHART_LENGTH: figure {fid} data['{key}'] ({role}) has "
                f"{len(values)} values but there are {category_count} categories"
            )
        return list(values)

    def check_limits(
        values: list[Any] | None, low: float | None, high: float | None, role: str
    ) -> None:
        if low is not None and high is not None and low >= high:
            errors.append(
                f"BACKBONE_FIGURE_CHART_RANGE: figure {fid} {role} min {low} must be "
                f"less than max {high}"
            )
        if values is None:
            return
        if high is not None and high < max(values):
            errors.append(
                f"BACKBONE_FIGURE_CHART_RANGE: figure {fid} {role} max {high} is below "
                f"the largest value {max(values)}"
            )
        if low is not None and low > min(values):
            errors.append(
                f"BACKBONE_FIGURE_CHART_RANGE: figure {fid} {role} min {low} is above "
                f"the smallest value {min(values)}"
            )

    if isinstance(chart, ComboChartDeclaration):
        if chart.bars.key == chart.line.key:
            errors.append(
                f"BACKBONE_FIGURE_CHART_SAME_KEY: figure {fid} bars and line both use "
                f"data['{chart.bars.key}']; they need two different series"
            )
        bar_values = check_series(chart.bars.key, "bars")
        line_values = check_series(chart.line.key, "line")
        if (
            bar_values is not None
            and line_values is not None
            and len(bar_values) != len(line_values)
        ):
            errors.append(
                f"BACKBONE_FIGURE_CHART_LENGTH: figure {fid} bars ({len(bar_values)}) "
                f"and line ({len(line_values)}) series have different lengths"
            )
        check_limits(bar_values, chart.bars.min, chart.bars.max, "bars")
        check_limits(line_values, chart.line.min, chart.line.max, "line")
    elif isinstance(chart, BarChartDeclaration):
        if not 1 <= len(chart.series) <= _MAX_BAR_SERIES:
            errors.append(
                f"BACKBONE_FIGURE_CHART_SERIES_COUNT: figure {fid} bar chart needs 1 to "
                f"{_MAX_BAR_SERIES} series, got {len(chart.series)}"
            )
        all_values: list[Any] = []
        for entry in chart.series:
            values = check_series(entry.key, "series")
            all_values.extend(values or [])
        if chart.y_max is not None and all_values and chart.y_max < max(all_values):
            errors.append(
                f"BACKBONE_FIGURE_CHART_RANGE: figure {fid} y_max {chart.y_max} is below "
                f"the largest value {max(all_values)}"
            )
    return errors


def figure_data_errors(backbone: LessonBackbone) -> list[str]:
    """Return one message per problem; each names the figure id."""
    errors: list[str] = []
    for figure in backbone.figures:
        data = figure.data or {}
        errors.extend(_chart_errors(figure))
        label_numbers: set[Decimal] = set()
        for entry in [*figure.labels_required, *figure.must_show]:
            label_numbers |= _numbers_in_text(str(entry))

        data_numbers = _numbers_in_value(data)
        for key in data:
            # Numbers in key names ("height_day_28_cm") count as present in the data.
            data_numbers |= _numbers_in_text(str(key))

        series = {key: value for key, value in data.items() if _is_series(value)}
        if series and figure.effective_mode != "render":
            errors.append(
                f"BACKBONE_FIGURE_SERIES_NEEDS_RENDER: figure {figure.id} data holds "
                f"number series ({', '.join(series)}) but mode is "
                f"'{figure.effective_mode}'; set mode to 'render' so code draws it"
            )
        if figure.effective_mode == "render":
            longest = max((len(value) for value in series.values()), default=0)
            if longest > _MAX_SERIES_ENTRIES or len(data) > _MAX_SERIES_COUNT:
                errors.append(
                    f"BACKBONE_FIGURE_SERIES_TOO_LARGE: figure {figure.id} render data is "
                    f"too large for a code table (at most {_MAX_SERIES_ENTRIES} entries "
                    f"per series and {_MAX_SERIES_COUNT} series); trim or split the figure"
                )

        lengths = {
            key: len(value) for key, value in data.items() if isinstance(value, (list, tuple))
        }
        if len(set(lengths.values())) > 1:
            detail = ", ".join(f"{key}={size}" for key, size in lengths.items())
            errors.append(
                f"BACKBONE_FIGURE_SERIES_LENGTH: figure {figure.id} data series have "
                f"unequal lengths ({detail}); every series needs one value per label"
            )

        if not label_numbers:
            continue
        if not data:
            errors.append(
                f"BACKBONE_FIGURE_DATA_MISSING: figure {figure.id} labels or must_show "
                "contain numbers but data is empty; put every number in data"
            )
            continue
        missing = sorted(label_numbers - data_numbers)
        if missing:
            listed = ", ".join(_fmt(number) for number in missing)
            errors.append(
                f"BACKBONE_FIGURE_LABEL_NUMBER: figure {figure.id} labels or must_show "
                f"use number(s) {listed} that are not in its data"
            )
    return errors


__all__ = ["figure_data_errors"]
