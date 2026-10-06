from __future__ import annotations

import io
from typing import Any

import pytest
from pydantic import ValidationError

from media.render.contracts import FunctionGraphSpec
from media.render.families import function_graph
from media.render.style import drawing


def _svg(spec: FunctionGraphSpec) -> bytes:
    with drawing():
        fig = function_graph.draw(spec)
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", metadata={"Date": None})
    return buf.getvalue()


def _codes(**fields: Any) -> list[str]:
    base: dict[str, Any] = {"x_range": [-5, 5], "y_range": [-5, 5]}
    base.update(fields)
    return [e.code for e in function_graph.validate(FunctionGraphSpec.model_validate(base))]


@pytest.mark.parametrize("name", sorted(function_graph.GALLERY))
def test_gallery_validates_and_draws_deterministically(name: str) -> None:
    spec = FunctionGraphSpec.model_validate(function_graph.GALLERY[name])
    assert function_graph.validate(spec) == []
    assert function_graph.describe(spec)
    first = _svg(spec)
    assert first.startswith(b"<?xml") and first == _svg(spec)


def test_numbers_is_empty() -> None:
    spec = FunctionGraphSpec.model_validate(function_graph.GALLERY["function_graph_line"])
    assert function_graph.numbers(spec) == []


def test_free_form_expressions_are_rejected_by_the_schema() -> None:
    with pytest.raises(ValidationError):
        FunctionGraphSpec.model_validate(
            {
                "x_range": [-5, 5],
                "y_range": [-5, 5],
                "curves": [{"form": "linear", "m": 1, "c": 0, "expr": "__import__('os')"}],
            }
        )
    with pytest.raises(ValidationError):
        FunctionGraphSpec.model_validate(
            {
                "x_range": [-5, 5],
                "y_range": [-5, 5],
                "curves": [{"form": "expression", "expr": "x**2"}],
            }
        )


def test_bad_range() -> None:
    assert _codes(x_range=[3, 3]) == ["bad_range"]
    assert _codes(y_range=[4, -4]) == ["bad_range"]


def test_too_many_ticks() -> None:
    assert _codes(x_range=[-50, 50], x_step=1) == ["too_many_ticks"]


def test_point_out_of_range() -> None:
    assert _codes(points=[{"x": 9, "y": 0}]) == ["point_out_of_range"]


def test_polyline_point_out_of_range() -> None:
    curve = {"form": "polyline", "points": [[0, 0], [9, 1]]}
    assert _codes(curves=[curve]) == ["point_out_of_range"]


def test_curve_not_visible() -> None:
    assert _codes(curves=[{"form": "linear", "m": 0, "c": 50}]) == ["curve_not_visible"]


def test_duplicate_label() -> None:
    curves = [
        {"form": "linear", "m": 1, "c": 0, "label": "f"},
        {"form": "linear", "m": 2, "c": 0, "label": "f"},
    ]
    assert _codes(curves=curves) == ["duplicate_label"]


def test_axes_on_the_edge_still_draw() -> None:
    spec = FunctionGraphSpec.model_validate(
        {
            "x_range": [1, 10],
            "y_range": [10, 100],
            "x_label": "Time (s)",
            "y_label": "Distance (m)",
            "curves": [{"form": "polyline", "points": [[1, 12], [5, 45], [10, 100]], "label": "Car"}],
        }
    )
    assert function_graph.validate(spec) == []
    assert _svg(spec)
