"""Unit test: Learn figure pipeline attaches asset_id via execute_visual."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from learn.generation.figure_pipeline import FigurePipelineError, attach_figure_asset


@pytest.mark.asyncio
async def test_attach_figure_asset_sets_asset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_execute_visual(order, emit, **kwargs):
        return [
            SimpleNamespace(
                status="ready",
                image_url="/images/gen/learn-fig.png",
                fallback_image_url=None,
                error_message=None,
            )
        ]

    monkeypatch.setattr(
        "learn.generation.figure_pipeline.execute_visual",
        fake_execute_visual,
    )
    node = {
        "id": "fig-1",
        "kind": "figure",
        "caption": "Leaf cross-section with stomata",
        "alt": "Diagram of stomata",
        "asset_id": None,
        "teaching_block_id": "b1",
    }
    out = await attach_figure_asset(
        node,
        generation_id="gen-1",
        teaching_block={"id": "b1", "brief": "Show stomata openings", "intent": "illustrate"},
        lesson_context={"objective": "Explain stomata"},
    )
    assert out["asset_id"] == "gen/learn-fig.png"
    assert out["caption"] == node["caption"]


@pytest.mark.asyncio
async def test_attach_figure_asset_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    async def always_fail(order, emit, **kwargs):
        calls["n"] += 1
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "learn.generation.figure_pipeline.execute_visual",
        always_fail,
    )
    with pytest.raises(FigurePipelineError):
        await attach_figure_asset(
            {"id": "fig-1", "kind": "figure", "caption": "x", "alt": "y"},
            generation_id="gen-1",
            teaching_block={"id": "b1", "brief": "b"},
            max_attempts=2,
        )
    assert calls["n"] == 2
