from __future__ import annotations

import io
from typing import Any

import pytest
from pydantic import TypeAdapter

from media.render.contracts import CycleSpec, RenderSpec
from media.render.families import cycle
from media.render.style import drawing

_ADAPTER = TypeAdapter(RenderSpec)


def _spec(name: str) -> CycleSpec:
    spec = _ADAPTER.validate_python(cycle.GALLERY[name])
    assert isinstance(spec, CycleSpec)
    return spec


def _svg(spec: CycleSpec) -> bytes:
    with drawing():
        fig = cycle.draw(spec)
        buffer = io.BytesIO()
        fig.savefig(buffer, format="svg", metadata={"Date": None})
    return buffer.getvalue()


def _codes(**fields: Any) -> list[str]:
    return [error.code for error in cycle.validate(CycleSpec(**fields))]


@pytest.mark.parametrize("name", sorted(cycle.GALLERY))
def test_gallery_validates_and_draws_deterministically(name: str) -> None:
    spec = _spec(name)
    assert cycle.validate(spec) == []
    first = _svg(spec)
    assert first.startswith(b"<?xml")
    assert first == _svg(spec)
    assert cycle.numbers(spec) == []


def test_clockwise_angles_start_at_top() -> None:
    assert cycle.node_angles(_spec("cycle_water")) == [90.0, 0.0, -90.0, -180.0]


def test_anticlockwise_angles_start_at_top() -> None:
    angles = cycle.node_angles(_spec("cycle_six_anticlockwise"))
    assert angles == [90.0, 150.0, 210.0, 270.0, 330.0, 390.0]


def test_describe_lists_stages_and_closes_the_loop() -> None:
    text = cycle.describe(_spec("cycle_water"))
    assert text.startswith("Cycle titled Water cycle of 4 stages: Evaporation → Condensation")
    assert text.endswith("→ back to Evaporation.")
    assert "anticlockwise" in cycle.describe(_spec("cycle_six_anticlockwise"))


def test_duplicate_node_text() -> None:
    errors = cycle.validate(CycleSpec(nodes=["Rain", "Sun", "rain"]))
    assert [(e.code, e.path) for e in errors] == [("duplicate_node_text", "nodes[2]")]


def test_node_text_too_long() -> None:
    long = "Pneumonoultramicroscopic"
    assert _codes(nodes=["A", "B", long]) == ["node_text_too_long"]
