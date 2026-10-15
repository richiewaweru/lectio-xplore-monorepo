from __future__ import annotations

import copy
import io
from typing import Any

import pytest

from media.render.contracts import ComboChartSpec
from media.render.families import combo_chart
from media.render.style import drawing

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _weather(**overrides: Any) -> dict[str, Any]:
    base = copy.deepcopy(combo_chart.GALLERY["combo_chart_weather"])
    base.update(overrides)
    return base


def _spec(data: dict[str, Any]) -> ComboChartSpec:
    return ComboChartSpec.model_validate(data)


def _svg(spec: ComboChartSpec) -> bytes:
    with drawing():
        fig = combo_chart.draw(spec)
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", metadata={"Date": None})
    return buf.getvalue()


def _codes(data: dict[str, Any]) -> list[str]:
    return [e.code for e in combo_chart.validate(_spec(data))]


FAIRHAVEN = {
    "family": "combo_chart",
    "categories": DAYS,
    "bars": {"name": "Rainfall", "values": [5, 0, 22, 14, 3, 0, 8], "axis_label": "Rainfall (mm)"},
    "line": {
        "name": "Temperature",
        "values": [22, 24, 21, 19, 23, 25, 24],
        "axis_label": "Temperature (°C)",
    },
}
KIRKSTONE = {
    "family": "combo_chart",
    "categories": DAYS,
    "bars": {"name": "Rainfall", "values": [0, 0, 8, 25, 11, 4, 0], "axis_label": "Rainfall (mm)"},
    "line": {
        "name": "Temperature",
        "values": [12, 13, 11, 9, 10, 14, 15],
        "axis_label": "Temperature (°C)",
    },
}


@pytest.mark.parametrize("name", sorted(combo_chart.GALLERY))
def test_gallery_validates_and_draws_deterministically(name: str) -> None:
    spec = _spec(combo_chart.GALLERY[name])
    assert combo_chart.validate(spec) == []
    assert combo_chart.describe(spec)
    first = _svg(spec)
    assert first.startswith(b"<?xml") and first == _svg(spec)


@pytest.mark.parametrize("data", [FAIRHAVEN, KIRKSTONE], ids=["fairhaven", "kirkstone"])
def test_other_weather_stations_validate_and_draw(data: dict[str, Any]) -> None:
    spec = _spec(data)
    assert combo_chart.validate(spec) == []
    assert _svg(spec)


def test_draw_has_two_y_axes() -> None:
    with drawing():
        fig = combo_chart.draw(_spec(combo_chart.GALLERY["combo_chart_weather"]))
    assert len(fig.axes) == 2
    left, right = fig.axes
    assert left.get_ylabel() == "Rainfall (mm)"
    assert right.get_ylabel() == "Temperature (°C)"
    assert right.get_ylim() == (14, 22)
    assert left.get_ylim() == (0, 20)


def test_describe_mentions_every_category_and_both_labels() -> None:
    text = combo_chart.describe(_spec(combo_chart.GALLERY["combo_chart_weather"]))
    for day in DAYS:
        assert day in text
    assert "Rainfall (mm)" in text and "Temperature (°C)" in text
    assert "Friday: Rainfall 18, Temperature 15" in text


def test_numbers_include_values_and_axis_bounds() -> None:
    values = combo_chart.numbers(_spec(combo_chart.GALLERY["combo_chart_weather"]))
    assert values == [0, 12, 4, 0, 18, 6, 2, 18, 16, 19, 21, 15, 17, 20, 20, 14, 22]


def test_length_mismatch() -> None:
    data = _weather()
    data["line"]["values"] = [18, 16, 19]
    assert _codes(data) == ["length_mismatch"]


def test_duplicate_category() -> None:
    data = _weather(categories=["Monday", "monday", *DAYS[2:]])
    assert _codes(data) == ["duplicate_category"]


def test_negative_bar() -> None:
    data = _weather()
    data["bars"]["values"] = [0, -12, 4, 0, 18, 6, 2]
    assert _codes(data) == ["negative_value"]


def test_axis_max_below_data() -> None:
    data = _weather()
    data["bars"]["axis_max"] = 10
    data["line"]["axis_max"] = 20
    assert _codes(data) == ["axis_max_too_small", "axis_max_too_small"]


def test_axis_min_above_data_and_inverted_range() -> None:
    data = _weather()
    data["line"]["axis_min"] = 16
    assert _codes(data) == ["axis_min_too_large"]
    data["line"]["axis_min"] = 23
    assert _codes(data) == ["axis_range_invalid"]


def test_automatic_axes_without_bounds() -> None:
    assert _codes(FAIRHAVEN) == []
    left_lo, left_hi, _ = combo_chart.left_scale(_spec(FAIRHAVEN))
    right_lo, right_hi, _ = combo_chart.right_scale(_spec(FAIRHAVEN))
    assert left_lo == 0 and left_hi >= 22
    assert right_lo <= 19 and right_hi >= 25


def test_long_category_names_still_draw() -> None:
    data = {
        "categories": [f"Category number {i} with long words" for i in range(8)],
        "bars": {"name": "A", "values": list(range(1, 9))},
        "line": {"name": "B", "values": [x * 3.5 for x in range(1, 9)]},
    }
    assert _svg(_spec(data))
