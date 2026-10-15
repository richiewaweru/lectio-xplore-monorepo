"""Backbone figure `chart` declaration: model shape and deterministic checks."""

from __future__ import annotations

from typing import Any

from curriculum.backbone.figure_data import figure_data_errors
from curriculum.backbone.models import LessonBackbone

OAKFIELD: dict[str, Any] = {
    "id": "fig-1",
    "purpose": "Compare rainfall and temperature over a week at Oakfield.",
    "must_show": ["Rainfall bars and a temperature line for each day"],
    "labels_required": ["Rainfall (mm)", "Temperature (C)"],
    "mode": "render",
    "data": {
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "rainfall_mm": [0, 12, 4, 0, 18, 6, 2],
        "temperature_c": [18, 16, 19, 21, 15, 17, 20],
    },
    "chart": {
        "kind": "combo",
        "categories": "days",
        "bars": {"key": "rainfall_mm", "label": "Rainfall (mm)", "min": 0, "max": 20},
        "line": {"key": "temperature_c", "label": "Temperature (C)", "min": 14, "max": 22},
    },
}


def _backbone(*figures: dict[str, Any]) -> LessonBackbone:
    return LessonBackbone.model_validate(
        {"anchor": {"story": "Oakfield.", "data": {}}, "figures": list(figures)}
    )


def _oakfield(**changes: Any) -> dict[str, Any]:
    return {**OAKFIELD, **changes}


def _chart_with(**changes: Any) -> dict[str, Any]:
    return {**OAKFIELD["chart"], **changes}


def _codes(*figures: dict[str, Any]) -> list[str]:
    return [error.split(":")[0] for error in figure_data_errors(_backbone(*figures))]


def test_oakfield_combo_chart_is_clean() -> None:
    assert figure_data_errors(_backbone(OAKFIELD)) == []


def test_no_chart_keeps_dump_shape() -> None:
    plain = _backbone({k: v for k, v in OAKFIELD.items() if k != "chart"})
    assert "chart" not in plain.figures[0].model_dump()
    assert plain.figures[0].chart_dict() is None
    declared = _backbone(OAKFIELD).figures[0].chart_dict()
    assert declared is not None and declared["bars"]["max"] == 20


def test_chart_needs_render() -> None:
    assert "BACKBONE_FIGURE_CHART_NEEDS_RENDER" in _codes(_oakfield(mode="diagram"))


def test_chart_key_missing() -> None:
    assert _codes(_oakfield(chart=_chart_with(categories="weekdays"))) == [
        "BACKBONE_FIGURE_CHART_KEY_MISSING"
    ]
    bars = {"key": "nope", "label": "x"}
    assert "BACKBONE_FIGURE_CHART_KEY_MISSING" in _codes(_oakfield(chart=_chart_with(bars=bars)))


def test_chart_categories_must_be_strings() -> None:
    data = {**OAKFIELD["data"], "days": [1, 2, 3, 4, 5, 6, 7]}
    assert _codes(_oakfield(data=data)) == ["BACKBONE_FIGURE_CHART_CATEGORIES"]


def test_chart_series_not_numeric() -> None:
    data = {**OAKFIELD["data"], "rainfall_mm": list("abcdefg")}
    assert "BACKBONE_FIGURE_CHART_SERIES_NOT_NUMERIC" in _codes(_oakfield(data=data))


def test_chart_length_mismatch() -> None:
    data = {**OAKFIELD["data"], "temperature_c": [18, 16, 19]}
    assert "BACKBONE_FIGURE_CHART_LENGTH" in _codes(_oakfield(data=data))


def test_chart_same_key() -> None:
    line = {"key": "rainfall_mm", "label": "x"}
    assert "BACKBONE_FIGURE_CHART_SAME_KEY" in _codes(_oakfield(chart=_chart_with(line=line)))


def test_chart_range_errors() -> None:
    inverted = {"key": "temperature_c", "label": "T", "min": 22, "max": 14}
    assert "BACKBONE_FIGURE_CHART_RANGE" in _codes(_oakfield(chart=_chart_with(line=inverted)))
    low_max = {"key": "rainfall_mm", "label": "R", "min": 0, "max": 10}
    errors = figure_data_errors(_backbone(_oakfield(chart=_chart_with(bars=low_max))))
    assert any("below the largest value 18" in error for error in errors)
    high_min = {"key": "temperature_c", "label": "T", "min": 16, "max": 22}
    errors = figure_data_errors(_backbone(_oakfield(chart=_chart_with(line=high_min))))
    assert any("above the smallest value 15" in error for error in errors)


def test_chart_too_many_categories() -> None:
    data = {
        "days": [f"d{i}" for i in range(13)],
        "rainfall_mm": list(range(13)),
        "temperature_c": list(range(13)),
    }
    chart = _chart_with(
        bars={"key": "rainfall_mm", "label": "R"}, line={"key": "temperature_c", "label": "T"}
    )
    assert "BACKBONE_FIGURE_CHART_TOO_MANY_CATEGORIES" in _codes(_oakfield(data=data, chart=chart))


def test_bar_chart_valid_and_series_count() -> None:
    data = {"days": ["a", "b"], "x": [1, 2], "y": [3, 4], "z": [1, 1], "w": [2, 2]}
    bar = {"kind": "bar", "categories": "days", "series": [{"key": "x", "label": "X"}], "y_max": 5}
    assert _codes(_oakfield(data=data, chart=bar)) == []
    many = {**bar, "series": [{"key": k, "label": k} for k in ("x", "y", "z", "w")]}
    assert _codes(_oakfield(data=data, chart=many)) == ["BACKBONE_FIGURE_CHART_SERIES_COUNT"]
    none = {**bar, "series": []}
    assert _codes(_oakfield(data=data, chart=none)) == ["BACKBONE_FIGURE_CHART_SERIES_COUNT"]
    assert "BACKBONE_FIGURE_CHART_RANGE" in _codes(_oakfield(data=data, chart={**bar, "y_max": 1}))
