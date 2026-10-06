from __future__ import annotations

from types import SimpleNamespace

import pytest

from infra.authoring.model_policy import V3_FIGURE_SPEC, get_v3_slot
from infra.llm.types import ModelSlot
from media.generation.contracts import (
    SourceOfTruthEntry,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
)
from media.render import spec_builder
from media.render.contracts import FAMILIES, PolygonAreaSpec, RenderSpecError, RenderSpecResult
from media.render.gallery import GALLERY


def make_order() -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="wo-1",
        visual=VisualPlanItem(
            id="v1",
            attaches_to="s1",
            purpose="Show the L-shaped room",
            must_show=["every side length"],
            labels_required=["9 m"],
            must_not_show=["furniture"],
        ),
        source_of_truth=[
            SourceOfTruthEntry(key="caption", text="Plan of a 9 m by 7 m room."),
            SourceOfTruthEntry(key="sentence", text="Find the floor area of the room."),
        ],
    )


def previous() -> RenderSpecResult:
    spec = PolygonAreaSpec.model_validate(GALLERY["polygon_l_room"])
    return RenderSpecResult(family="polygon_area", spec=spec)


def test_build_prompt_lists_families_request_and_sources() -> None:
    prompt = spec_builder.build_prompt(make_order())
    for family in FAMILIES:
        assert family in prompt
    assert "Show the L-shaped room" in prompt
    assert "every side length" in prompt
    assert "furniture" in prompt
    assert "Plan of a 9 m by 7 m room." in prompt
    assert "Find the floor area of the room." in prompt
    assert "[[0,0],[9,0],[9,5],[6,5],[6,7],[0,7]]" in prompt
    assert '"none"' in prompt


def test_repair_prompt_has_errors_and_previous_spec() -> None:
    errors = [RenderSpecError("edge_out_of_range", "edge_labels[0].edge", "edge 99 missing")]
    prompt = spec_builder.repair_prompt(make_order(), previous(), errors)
    assert "edge_out_of_range" in prompt
    assert "edge_labels[0].edge" in prompt
    assert "edge 99 missing" in prompt
    assert '"family": "polygon_area"' in prompt
    assert '"points"' in prompt


def test_node_is_registered_on_fast_slot() -> None:
    assert V3_FIGURE_SPEC == "v3_figure_spec"
    assert get_v3_slot(V3_FIGURE_SPEC) == ModelSlot.FAST


async def test_llm_spec_builder_uses_figure_spec_node(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    calls: list[dict[str, object]] = []
    expected = previous()

    def fake_prepare(*, node_name, output_type):
        seen["node_name"] = node_name
        seen["output_type"] = output_type
        return object(), output_type, None, object(), "test"

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            seen["agent_kwargs"] = kwargs

    async def fake_run_llm(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output=expected)

    monkeypatch.setattr(spec_builder, "prepare_structured_agent", fake_prepare)
    monkeypatch.setattr(spec_builder, "Agent", FakeAgent)
    monkeypatch.setattr(spec_builder, "run_llm", fake_run_llm)

    builder = spec_builder.LlmSpecBuilder(trace_id="t1", generation_id="g1")
    order = make_order()
    assert await builder.build(order) == expected
    errors = [RenderSpecError("x", "p", "m")]
    assert await builder.repair(order, expected, errors) == expected

    assert seen["node_name"] == V3_FIGURE_SPEC
    assert seen["output_type"] is RenderSpecResult
    first, second = calls
    assert first["node"] == V3_FIGURE_SPEC
    assert first["caller"] == "v3_figure_spec"
    assert second["caller"] == "v3_figure_spec_repair"
    assert first["trace_id"] == "t1"
    assert first["generation_id"] == "g1"
