from __future__ import annotations

import pytest

from media.generation.contracts import (
    SourceOfTruthEntry,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
)
from media.render.contracts import (
    FAMILIES,
    CycleSpec,
    PolygonAreaSpec,
    RenderSpecError,
    RenderSpecResult,
)
from media.render.families import RENDERERS
from media.render.gallery import GALLERY
from media.render.pipeline import (
    MAX_REPAIRS,
    Fallback,
    Rendered,
    Unavailable,
    render_figure,
)

FULL_TEXT = "The room is 9 m by 7 m with a 3 m by 2 m notch; sides 5 m and 6 m."


def make_order(text: str = FULL_TEXT) -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="wo-1",
        visual=VisualPlanItem(
            id="v1",
            attaches_to="s1",
            purpose="Show the L-shaped room",
            must_show=["every side length"],
        ),
        source_of_truth=[SourceOfTruthEntry(key="caption", text=text)],
    )


def l_room() -> RenderSpecResult:
    spec = PolygonAreaSpec.model_validate(GALLERY["polygon_l_room"])
    return RenderSpecResult(family="polygon_area", spec=spec)


def bad_room() -> RenderSpecResult:
    # Edge label index out of range -> structural error.
    data = dict(GALLERY["polygon_l_room"])
    data["edge_labels"] = [{"edge": 99}]
    spec = PolygonAreaSpec.model_validate(data)
    return RenderSpecResult(family="polygon_area", spec=spec)


class FakeBuilder:
    def __init__(self, built, repairs=(), build_error=None, repair_error=None) -> None:
        self.built = built
        self.repairs = list(repairs)
        self.build_error = build_error
        self.repair_error = repair_error
        self.repair_calls = 0

    async def build(self, order):
        if self.build_error:
            raise self.build_error
        return self.built

    async def repair(self, order, previous, errors):
        self.repair_calls += 1
        assert errors
        assert all(isinstance(e, RenderSpecError) for e in errors)
        if self.repair_error:
            raise self.repair_error
        return self.repairs.pop(0)


async def test_valid_spec_renders_first_try() -> None:
    out = await render_figure(make_order(), builder=FakeBuilder(l_room()))
    assert isinstance(out, Rendered)
    assert out.attempts == 1
    assert b"<svg" in out.figure.svg
    assert out.warnings == []


async def test_invalid_then_fixed_renders_after_one_repair() -> None:
    builder = FakeBuilder(bad_room(), repairs=[l_room()])
    out = await render_figure(make_order(), builder=builder)
    assert isinstance(out, Rendered)
    assert out.attempts == 2
    assert builder.repair_calls == 1


async def test_invalid_three_times_is_unavailable() -> None:
    builder = FakeBuilder(bad_room(), repairs=[bad_room(), bad_room()])
    out = await render_figure(make_order(), builder=builder)
    assert isinstance(out, Unavailable)
    assert out.code == "render_spec_invalid"
    assert builder.repair_calls == MAX_REPAIRS == 2
    assert out.errors
    assert {"code", "path", "message"} <= set(out.errors[0])


async def test_none_family_falls_back() -> None:
    out = await render_figure(
        make_order(), builder=FakeBuilder(RenderSpecResult(family="none", reason="a cell"))
    )
    assert out == Fallback("no_family: a cell")


async def test_build_failure_falls_back() -> None:
    out = await render_figure(make_order(), builder=FakeBuilder(None, build_error=TimeoutError()))
    assert out == Fallback("spec_builder_failed: TimeoutError")


async def test_repair_failure_is_unavailable() -> None:
    builder = FakeBuilder(bad_room(), repair_error=RuntimeError("boom"))
    out = await render_figure(make_order(), builder=builder)
    assert isinstance(out, Unavailable)
    assert out.code == "render_spec_invalid"


async def test_repair_returning_none_or_other_family_is_unavailable() -> None:
    for repaired in (
        RenderSpecResult(family="none", reason="give up"),
        RenderSpecResult(family="cycle", spec=CycleSpec(nodes=["a", "b", "c"])),
    ):
        out = await render_figure(make_order(), builder=FakeBuilder(bad_room(), repairs=[repaired]))
        assert isinstance(out, Unavailable)
        assert out.code == "render_spec_invalid"


async def test_missing_number_is_a_warning_not_a_failure() -> None:
    out = await render_figure(
        make_order("The room is 9 m by 5 m, notch 3 m by 2 m, side 6 m."),
        builder=FakeBuilder(l_room()),
    )
    assert isinstance(out, Rendered)
    assert len(out.warnings) == 1
    assert "7" in out.warnings[0]


async def test_unimplemented_family_falls_back() -> None:
    missing = [f for f in FAMILIES if f not in RENDERERS]
    if not missing:
        pytest.skip("all families implemented")
    family = missing[0]
    stub = RenderSpecResult.model_construct(family=family, spec=object(), reason="")
    out = await render_figure(make_order(), builder=FakeBuilder(stub))
    assert out == Fallback(f"family_not_implemented: {family}")
