"""Phase 04/05 streaming + visual dispatch unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from planning.whole_lesson.visual_dispatch import (
    collect_pending_figure_dispatches,
    dispatch_native_pending_visuals,
    figure_work_order_from_pending,
)


def test_v01_native_visual_work_order_mapping() -> None:
    order = figure_work_order_from_pending(
        generation_id="gen-1",
        block_id="fig-1",
        content={"alt_text": "Leaf diagram", "caption": "A leaf"},
        request_id="req-stable-1",
    )
    assert order.work_order_id == "native-visual:req-stable-1"
    assert order.visual.id == "req-stable-1"
    assert order.visual.attaches_to == "fig-1"
    assert "Leaf diagram" in order.visual.must_show


def test_v07_dispatcher_skips_ready_assets() -> None:
    block_execution = {
        "orient:fig-1:everyone": {
            "object": "figure",
            "status": "visual_pending",
            "block_id": "fig-1",
            "request_id": "req-1",
            "content": {"asset": {"status": "ready", "request_id": "req-1", "src": "x"}},
        },
        "explain:fig-2:everyone": {
            "object": "figure",
            "status": "visual_pending",
            "block_id": "fig-2",
            "request_id": "req-2",
            "content": {"asset": {"status": "pending", "request_id": "req-2"}},
        },
    }
    pending = collect_pending_figure_dispatches(
        generation_id="gen-1",
        block_execution=block_execution,
    )
    assert len(pending) == 1
    assert pending[0][1] == "req-2"


@pytest.mark.asyncio
async def test_v02_execute_visual_invoked_once() -> None:
    calls: list[Any] = []

    async def fake_execute(order, emit, **kwargs):
        calls.append(order.work_order_id)
        return [
            type(
                "B",
                (),
                {
                    "status": "ready",
                    "fallback_image_url": "https://example.test/fig.png",
                    "html_content": None,
                },
            )()
        ]

    apply = AsyncMock(
        return_value=type("R", (), {"document_revision": 2})()
    )
    result = await dispatch_native_pending_visuals(
        generation_id="gen-1",
        block_execution={
            "orient:fig-1:everyone": {
                "object": "figure",
                "status": "visual_pending",
                "block_id": "fig-1",
                "request_id": "req-1",
                "content": {
                    "alt_text": "Leaf",
                    "asset": {"status": "pending", "request_id": "req-1"},
                },
            }
        },
        apply_completion=apply,
        execute_visual_fn=fake_execute,
    )
    assert result["dispatched"] == 1
    assert calls == ["native-visual:req-1"]
    apply.assert_awaited_once()
    kwargs = apply.await_args.kwargs
    assert kwargs["request_id"] == "req-1"
    assert kwargs["asset"]["status"] == "ready"
