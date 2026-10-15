"""A figure with a chart declaration is drawn by code: no builder, no image model."""

from __future__ import annotations

import pytest

from media.generation.contracts import (
    SourceOfTruthEntry,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
)
from media.render.contracts import RenderSpecResult
from tests.document.test_render_routing_executor import _make
from tests.media.test_chart_spec import COMBO, OAKFIELD

TITLE = "Rainfall and temperature at Oakfield, 08:00"


class CountingBuilder:
    def __init__(self) -> None:
        self.build_calls = 0

    async def build(self, order):
        self.build_calls += 1
        return RenderSpecResult(family="none", reason="no fit")

    async def repair(self, order, previous, errors):
        return RenderSpecResult(family="none", reason="no fit")


def _order(chart: dict | None) -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="wo-c",
        visual=VisualPlanItem(
            id="v1",
            attaches_to="s1",
            mode="render",
            purpose="Compare rainfall and temperature over the week",
            must_show=["rainfall bars and a temperature line"],
            labels_required=[TITLE],
            data=OAKFIELD,
            chart=chart,
        ),
        source_of_truth=[SourceOfTruthEntry(key="caption", text="Oakfield week")],
    )


@pytest.mark.asyncio
async def test_combo_declaration_renders_without_model(monkeypatch, tmp_path):
    builder = CountingBuilder()
    executor, delegated = _make(monkeypatch, tmp_path, builder)
    blocks = await executor.execute_figure(_order(COMBO))
    assert blocks[0].render_route == "chart_declared:combo"
    assert blocks[0].image_url and blocks[0].fallback_image_url
    assert builder.build_calls == 0 and not delegated


@pytest.mark.asyncio
async def test_invalid_declaration_falls_through_to_the_chain(monkeypatch, tmp_path):
    builder = CountingBuilder()
    executor, delegated = _make(monkeypatch, tmp_path, builder)
    bad = {**COMBO, "bars": {"key": "missing", "label": "Rain"}}
    blocks = await executor.execute_figure(_order(bad))
    assert builder.build_calls == 1
    assert blocks[0].render_route != "chart_declared:combo"
    assert len(delegated) <= 1


@pytest.mark.asyncio
async def test_no_declaration_is_unchanged(monkeypatch, tmp_path):
    builder = CountingBuilder()
    executor, _ = _make(monkeypatch, tmp_path, builder)
    blocks = await executor.execute_figure(_order(None))
    assert builder.build_calls == 1
    assert not blocks[0].render_route.startswith("chart_declared")
