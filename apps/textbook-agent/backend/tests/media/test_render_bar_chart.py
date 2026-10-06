from __future__ import annotations

import io
from typing import Any

import pytest

from media.render.contracts import BarChartSpec
from media.render.families import bar_chart
from media.render.style import drawing


def _svg(spec: BarChartSpec) -> bytes:
    with drawing():
        fig = bar_chart.draw(spec)
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", metadata={"Date": None})
    return buf.getvalue()


def _codes(**fields: Any) -> list[str]:
    base: dict[str, Any] = {
        "categories": ["A", "B", "C"],
        "series": [{"values": [1, 2, 3]}],
    }
    base.update(fields)
    return [e.code for e in bar_chart.validate(BarChartSpec.model_validate(base))]


@pytest.mark.parametrize("name", sorted(bar_chart.GALLERY))
def test_gallery_validates_and_draws_deterministically(name: str) -> None:
    spec = BarChartSpec.model_validate(bar_chart.GALLERY[name])
    assert bar_chart.validate(spec) == []
    assert bar_chart.describe(spec)
    first = _svg(spec)
    assert first.startswith(b"<?xml") and first == _svg(spec)


def test_numbers_returns_every_bar_value() -> None:
    spec = BarChartSpec.model_validate(bar_chart.GALLERY["bar_chart_grouped"])
    assert bar_chart.numbers(spec) == [18, 22, 15, 10, 20, 17, 24, 13]


def test_valid_spec_has_no_errors() -> None:
    assert _codes() == []


def test_length_mismatch() -> None:
    assert _codes(series=[{"values": [1, 2]}]) == ["length_mismatch"]


def test_negative_value() -> None:
    assert _codes(series=[{"values": [1, -2, 3]}]) == ["negative_value"]


def test_series_needs_name() -> None:
    codes = _codes(series=[{"name": "a", "values": [1, 2, 3]}, {"values": [1, 2, 3]}])
    assert codes == ["series_needs_name"]


def test_y_max_too_small() -> None:
    assert _codes(y_max=2) == ["y_max_too_small"]


def test_y_step_needs_y_max() -> None:
    assert _codes(y_step=1) == ["y_step_needs_y_max"]


def test_y_step_must_divide_y_max() -> None:
    assert _codes(y_max=10, y_step=3) == ["y_step_not_divisor"]


def test_too_many_ticks() -> None:
    assert _codes(y_max=100, y_step=5) == ["too_many_ticks"]


def test_duplicate_category() -> None:
    assert _codes(categories=["A", "a", "C"]) == ["duplicate_category"]


def test_nice_axis_rounds_up_to_a_nice_number() -> None:
    assert bar_chart.nice_axis(14) == (14, 2)
    assert bar_chart.nice_axis(23) == (25, 5)
    assert bar_chart.nice_axis(0) == (1, 0.2)


def test_long_category_names_still_draw() -> None:
    spec = BarChartSpec.model_validate(
        {
            "categories": [f"Category number {i} with long words" for i in range(8)],
            "series": [{"values": list(range(1, 9))}],
        }
    )
    assert _svg(spec)
