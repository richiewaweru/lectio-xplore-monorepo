from __future__ import annotations

import copy

from media.render.chart_spec import chart_spec_from_declaration
from media.render.contracts import BarChartSpec, ComboChartSpec

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
OAKFIELD = {
    "days": DAYS,
    "location": "Oakfield",
    "reading_time": "08:00",
    "rainfall_mm": [0, 12, 4, 0, 18, 6, 2],
    "temperature_c": [18, 16, 19, 21, 15, 17, 20],
    "left_axis_max_mm": 20,
    "right_axis_max_c": 22,
    "right_axis_min_c": 14,
    "total_rainfall_mm": 42,
}
COMBO = {
    "kind": "combo",
    "categories": "days",
    "bars": {"key": "rainfall_mm", "label": "Rainfall (mm)", "min": 0, "max": 20},
    "line": {"key": "temperature_c", "label": "Temperature (°C)", "min": 14, "max": 22},
}


def test_oakfield_combo() -> None:
    spec = chart_spec_from_declaration(COMBO, OAKFIELD, title="Rainfall and temperature at Oakfield")
    assert isinstance(spec, ComboChartSpec)
    assert spec.categories == DAYS
    assert spec.bars.values == [0, 12, 4, 0, 18, 6, 2]
    assert spec.bars.name == spec.bars.axis_label == "Rainfall (mm)"
    assert (spec.bars.axis_min, spec.bars.axis_max) == (0, 20)
    assert spec.line.values == [18, 16, 19, 21, 15, 17, 20]
    assert (spec.line.axis_min, spec.line.axis_max) == (14, 22)
    assert spec.x_label is None and spec.title == "Rainfall and temperature at Oakfield"


def test_variants_without_limits_or_title() -> None:
    data = {"days": DAYS, "rain": [5, 0, 22, 14, 3, 0, 8], "temp": [22, 24, 21, 19, 23, 25, 24]}
    decl = {
        "kind": "combo",
        "categories": "days",
        "bars": {"key": "rain", "label": "Rainfall"},
        "line": {"key": "temp", "label": "Temperature"},
    }
    spec = chart_spec_from_declaration(decl, data)
    assert isinstance(spec, ComboChartSpec)
    assert spec.bars.axis_max is None and spec.line.axis_min is None and spec.title is None


def test_unusable_declarations_return_none() -> None:
    bad_key = copy.deepcopy(COMBO)
    bad_key["bars"]["key"] = "nope"
    assert chart_spec_from_declaration(bad_key, OAKFIELD) is None
    short = {**OAKFIELD, "rainfall_mm": [1, 2, 3]}
    assert chart_spec_from_declaration(COMBO, short) is None
    scalar = {**OAKFIELD, "rainfall_mm": 5}
    assert chart_spec_from_declaration(COMBO, scalar) is None
    text = {**OAKFIELD, "rainfall_mm": ["a"] * 7}
    assert chart_spec_from_declaration(COMBO, text) is None
    assert chart_spec_from_declaration(COMBO, {**OAKFIELD, "days": "days"}) is None
    assert chart_spec_from_declaration(None, OAKFIELD) is None
    assert chart_spec_from_declaration(COMBO, None) is None
    assert chart_spec_from_declaration({"kind": "pie"}, OAKFIELD) is None
    assert chart_spec_from_declaration({"kind": "combo", "bars": 3}, OAKFIELD) is None
    too_many = {"days": [str(i) for i in range(13)], "a": [1.0] * 13, "b": [1.0] * 13}
    decl = {"kind": "combo", "categories": "days", "bars": {"key": "a", "label": "A"},
            "line": {"key": "b", "label": "B"}}
    assert chart_spec_from_declaration(decl, too_many) is None


def test_bar_declaration() -> None:
    data = {"days": DAYS, "rainfall_mm": OAKFIELD["rainfall_mm"]}
    decl = {
        "kind": "bar",
        "categories": "days",
        "series": [{"key": "rainfall_mm", "label": "Rainfall (mm)"}],
        "x_label": "Day",
        "y_label": "mm",
        "y_max": 20,
    }
    spec = chart_spec_from_declaration(decl, data)
    assert isinstance(spec, BarChartSpec)
    assert spec.series[0].name == "Rainfall (mm)" and spec.series[0].values[1] == 12
    assert (spec.x_label, spec.y_label, spec.y_max) == ("Day", "mm", 20)
