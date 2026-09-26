from __future__ import annotations

import pytest

from document.shared_lesson.figure_executor_adapter import SharedFigureExecutorAdapter
from media.generation.contracts import (
    GeneratedVisualBlock,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
)


def _order() -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="shared-media-work-1",
        resource_type="shared_lesson_figure",
        dependency="section_text",
        visual=VisualPlanItem(
            id="shared-figure-1",
            attaches_to="figure-1",
            mode="diagram",
            purpose="A plant using light",
            must_show=["A plant using light"],
        ),
    )


def _block(order: VisualGeneratorWorkOrder) -> GeneratedVisualBlock:
    return GeneratedVisualBlock(
        visual_id=order.visual.id,
        attaches_to=order.visual.attaches_to,
        mode=order.visual.mode,
        image_url="https://cdn.example.test/figure.png",
        caption=order.visual.purpose,
        alt_text=order.visual.must_show[0],
        source_work_order_id=order.work_order_id,
        status="ready",
    )


@pytest.mark.asyncio
async def test_adapter_returns_existing_valid_hosted_visual_and_stable_ids(monkeypatch):
    order = _order()
    events = []

    async def emit(event_type, payload):
        events.append((event_type, payload))

    async def execute(order, emit_event, *, trace_id, generation_id):
        await emit_event("visual_ready", {"visual_id": order.visual.id})
        assert trace_id == "shared-document:run-1:media:shared-media-work-1"
        assert generation_id == "shared-document:run-1"
        return [_block(order)]

    monkeypatch.setattr("document.shared_lesson.figure_executor_adapter.execute_visual", execute)
    result = await SharedFigureExecutorAdapter(run_id="run-1", emit_event=emit).execute_figure(
        order
    )

    assert result == [_block(order)]
    assert events == [("visual_ready", {"visual_id": "shared-figure-1"})]


@pytest.mark.asyncio
async def test_adapter_propagates_provider_failure(monkeypatch):
    async def execute(*_args, **_kwargs):
        raise RuntimeError("image provider unavailable")

    monkeypatch.setattr("document.shared_lesson.figure_executor_adapter.execute_visual", execute)

    with pytest.raises(RuntimeError, match="image provider unavailable"):
        await SharedFigureExecutorAdapter(run_id="run-1").execute_figure(_order())


def test_adapter_rejects_blank_run_id():
    with pytest.raises(ValueError, match="run_id"):
        SharedFigureExecutorAdapter(run_id=" ")
