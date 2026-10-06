from __future__ import annotations

import io

import pytest

from media.render.contracts import NumberLineSpec
from media.render.families.number_line import (
    GALLERY,
    describe,
    draw,
    format_fraction,
    numbers,
    tick_text,
    validate,
)
from media.render.style import drawing


def _spec(**overrides: object) -> NumberLineSpec:
    raw: dict = {"family": "number_line", "start": -5, "end": 5, "step": 1}
    raw.update(overrides)
    return NumberLineSpec.model_validate(raw)


def _svg(spec: NumberLineSpec) -> bytes:
    with drawing():
        fig = draw(spec)
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", metadata={"Date": None})
    return buf.getvalue()


def _codes(spec: NumberLineSpec) -> list[str]:
    return [e.code for e in validate(spec)]


@pytest.mark.parametrize("name", sorted(GALLERY))
def test_gallery_validates_and_renders_deterministically(name: str) -> None:
    spec = NumberLineSpec.model_validate(GALLERY[name])
    assert validate(spec) == []
    assert describe(spec)
    assert numbers(spec) == []
    first = _svg(spec)
    assert first.startswith(b"<?xml") or b"<svg" in first
    assert first == _svg(spec)


def test_fraction_ticks_are_simplified() -> None:
    assert format_fraction(0.5, 4) == "1/2"
    assert format_fraction(0.25, 4) == "1/4"
    assert format_fraction(1.0, 4) == "1"
    assert format_fraction(0.0, 4) == "0"
    assert format_fraction(-0.75, 4) == "−3/4"
    assert format_fraction(1.5, 6) == "3/2"
    spec = _spec(start=0, end=2, step=0.25, tick_format="fraction", denominator=4)
    assert tick_text(spec, 1.25) == "5/4"


def test_decimal_and_integer_ticks() -> None:
    dec = _spec(start=0, end=1, step=0.25, tick_format="decimal")
    assert tick_text(dec, 0.25) == "0.25"
    assert tick_text(dec, 1.0) == "1"
    assert tick_text(_spec(), -3) == "−3"


def test_bad_range() -> None:
    assert _codes(_spec(start=3, end=3)) == ["bad_range"]


def test_step_not_dividing() -> None:
    assert _codes(_spec(step=3)) == ["step_not_dividing"]


def test_too_many_ticks() -> None:
    assert _codes(_spec(start=0, end=30, step=1)) == ["too_many_ticks"]


def test_fraction_needs_denominator() -> None:
    assert _codes(_spec(tick_format="fraction")) == ["fraction_needs_denominator"]


def test_step_not_fraction() -> None:
    spec = _spec(start=0, end=2, step=0.5, tick_format="fraction", denominator=3)
    assert _codes(spec) == ["step_not_fraction"]


def test_point_out_of_range() -> None:
    errors = validate(_spec(points=[{"value": 1}, {"value": 9}]))
    assert [(e.code, e.path) for e in errors] == [("point_out_of_range", "points[1].value")]


def test_jump_out_of_range_and_zero_length() -> None:
    errors = validate(_spec(jumps=[{"start": 0, "end": 8}, {"start": 2, "end": 2}]))
    assert [(e.code, e.path) for e in errors] == [
        ("jump_out_of_range", "jumps[0].end"),
        ("jump_zero_length", "jumps[1]"),
    ]


def test_interval_out_of_range_and_unordered() -> None:
    errors = validate(
        _spec(intervals=[{"start": -9, "end": 1}, {"start": 3, "end": 1}])
    )
    assert [(e.code, e.path) for e in errors] == [
        ("interval_out_of_range", "intervals[0].start"),
        ("interval_not_ordered", "intervals[1]"),
    ]
