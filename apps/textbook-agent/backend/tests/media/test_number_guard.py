from __future__ import annotations

from decimal import Decimal

from media.generation.contracts import (
    SourceOfTruthEntry,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
)
from media.render.contracts import BarChartSpec, PolygonAreaSpec, RenderSpecResult
from media.render.gallery import GALLERY
from media.render.number_guard import (
    allowed_numbers,
    label_numbers_outside_data,
    numbers_in,
    numbers_of,
    unsupported_numbers,
)
from media.render.pipeline import Rendered, Unavailable, render_figure

SERIES = {
    "days": [0, 7, 14, 21, 28],
    "height_seedling_a_cm": [5, 12, 22, 35, 48],
    "height_seedling_b_cm": [5, 6, 7, 8, 9],
}


def order_for(
    *,
    data=None,
    must_show=None,
    labels=None,
    sot=None,
) -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="wo-1",
        visual=VisualPlanItem(
            id="v1",
            attaches_to="s1",
            purpose="Show the figure",
            must_show=must_show or [],
            labels_required=labels or [],
            data=data,
        ),
        source_of_truth=[SourceOfTruthEntry(key=k, text=t) for k, t in (sot or [])],
    )


class FakeBuilder:
    def __init__(self, built) -> None:
        self.built = built
        self.repair_calls = 0

    async def build(self, order):
        return self.built

    async def repair(self, order, previous, errors):
        self.repair_calls += 1
        return self.built


def test_numbers_in_normalises_and_reads_signs() -> None:
    assert numbers_in("Day 28: 48 cm, 5.0 and 5") == {Decimal(28), Decimal(48), Decimal(5)}
    assert numbers_in("-3 to 4.50") == {Decimal(-3), Decimal("4.5")}
    # A minus glued to a word is a hyphen, not a sign.
    assert numbers_in("Day-7 and 5-10") == {Decimal(7), Decimal(5), Decimal(10)}
    assert numbers_in("") == set()


def test_numbers_of_walks_raw_values() -> None:
    assert numbers_of({"a": [1, 2.0, "x3"], "b": {"c": 4}, "note": "cm", "ok": True}) == {
        Decimal(1),
        Decimal(2),
        Decimal(3),
        Decimal(4),
    }
    assert numbers_of(None) == set()


def test_allowed_numbers_take_data_labels_and_approved_facts_not_context() -> None:
    order = order_for(
        data={"days": [0, 7]},
        must_show=["rows for Day 14"],
        labels=["21 cm"],
        sot=[
            ("fact-1", "The room is 9 m long."),
            ("figure-data", "days: 0, 7"),
            ("context:caption", "A caption saying 99"),
        ],
    )
    allowed = allowed_numbers(order)
    assert allowed == {Decimal(n) for n in (0, 7, 14, 21, 9)}
    assert Decimal(99) not in allowed


def test_unsupported_numbers_keeps_order_without_repeats() -> None:
    allowed = {Decimal(5), Decimal(12)}
    assert unsupported_numbers([5.0, 19.0, 12, 25, 19], allowed) == [Decimal(19), Decimal(25)]


def test_label_numbers_must_be_in_data_only_for_a_data_figure() -> None:
    bad = order_for(data=SERIES, labels=["Day 28: 48 cm", "Day 30"], must_show=["a table of 19"])
    assert label_numbers_outside_data(bad) == [Decimal(19), Decimal(30)]
    ok = order_for(data=SERIES, labels=["Day 28: 48 cm"], must_show=["rows Day 0 to Day 28"])
    assert label_numbers_outside_data(ok) == []
    scalar = order_for(data={"day_28_height_cm": 48}, labels=["Day 28: 48 cm", "Day 30"])
    assert label_numbers_outside_data(scalar) == []


def _bar(values: list[float]) -> RenderSpecResult:
    spec = BarChartSpec.model_validate(
        {
            "family": "bar_chart",
            "categories": [f"c{i}" for i in range(len(values))],
            "series": [{"name": "Height", "values": values}],
            "x_label": "Check",
            "y_label": "Height (cm)",
        }
    )
    return RenderSpecResult(family="bar_chart", spec=spec)


async def test_invented_values_are_rejected_and_repaired_to_unavailable() -> None:
    order = order_for(data=SERIES, labels=["Day", "Height"])
    builder = FakeBuilder(_bar([19, 25]))
    out = await render_figure(order, builder=builder)
    assert isinstance(out, Unavailable)
    assert out.code == "render_spec_invalid"
    assert [e["code"] for e in out.errors] == ["number_not_in_data:19", "number_not_in_data:25"]
    assert builder.repair_calls == 2


async def test_values_taken_from_data_render() -> None:
    order = order_for(data=SERIES)
    out = await render_figure(order, builder=FakeBuilder(_bar([5, 12, 22, 35, 48])))
    assert isinstance(out, Rendered)


async def test_polygon_lengths_from_an_approved_fact_still_render() -> None:
    spec = PolygonAreaSpec.model_validate(GALLERY["polygon_l_room"])
    result = RenderSpecResult(family="polygon_area", spec=spec)
    fact = "The room is 9 m by 7 m with a 3 m by 2 m notch; sides 5 m and 6 m."

    allowed = order_for(sot=[("fact-room", fact)])
    assert isinstance(await render_figure(allowed, builder=FakeBuilder(result)), Rendered)

    # The same text arriving as writer context is not an approved fact.
    context_only = order_for(sot=[("context:caption", fact)])
    out = await render_figure(context_only, builder=FakeBuilder(result))
    assert isinstance(out, Unavailable)
    assert out.code == "render_spec_invalid"


async def test_prebuilt_spec_is_guarded_and_never_repaired() -> None:
    from media.render.data_spec import spec_from_data

    good = spec_from_data(SERIES, [], [])
    out = await render_figure(order_for(data=SERIES), prebuilt=good)
    assert isinstance(out, Rendered)

    # A table whose cells are not in the order's data fails with no repair loop.
    out = await render_figure(order_for(data={"days": [0, 7]}), prebuilt=good)
    assert isinstance(out, Unavailable)
    assert out.code == "render_spec_invalid"
    assert out.attempts == 1
    assert any(e["code"].startswith("number_not_in_data:") for e in out.errors)


async def test_no_builder_and_no_prebuilt_falls_back() -> None:
    from media.render.pipeline import Fallback

    assert isinstance(await render_figure(order_for()), Fallback)


def test_polygon_allows_pairwise_sum_and_difference_but_other_families_do_not() -> None:
    from media.render.number_guard import allowed_numbers_for

    order = order_for(must_show=["sides 10 and 3"])
    polygon = allowed_numbers_for(order, "polygon_area")
    assert Decimal(7) in polygon and Decimal(13) in polygon
    assert Decimal(19) not in polygon
    assert Decimal(7) not in allowed_numbers_for(order, "bar_chart")
    assert Decimal(7) not in allowed_numbers_for(order, "table")


def test_data_figures_never_get_derived_numbers() -> None:
    from media.render.number_guard import allowed_numbers_for

    order = order_for(data={"a": [10, 3], "b": [1, 2]})
    assert Decimal(7) not in allowed_numbers_for(order, "polygon_area")


def test_derived_polygon_side_passes_and_unrelated_number_fails() -> None:
    from media.render.number_guard import allowed_numbers_for

    order = order_for(must_show=["sides 10 and 3"])
    allowed = allowed_numbers_for(order, "polygon_area")
    assert unsupported_numbers([10, 3, 7], allowed) == []
    assert unsupported_numbers([10, 19], allowed) == [Decimal(19)]


async def test_bar_chart_with_a_derived_value_is_rejected() -> None:
    order = order_for(must_show=["values 10 and 3"])
    out = await render_figure(order, builder=FakeBuilder(_bar([10, 3, 7])))
    assert isinstance(out, Unavailable)
    assert [e["code"] for e in out.errors] == ["number_not_in_data:7"]
