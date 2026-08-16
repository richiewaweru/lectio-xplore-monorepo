"""Phase 04/05 streaming + visual dispatch unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from planning.whole_lesson import visual_dispatch
from planning.whole_lesson.visual_dispatch import (
    collect_pending_figure_dispatches,
    dispatch_native_pending_visuals,
    figure_work_order_from_pending,
)
from v3_execution.prompts.visual_executor import build_visual_prompt
from v3_execution.models import ExecutorOutcome
from v3_execution.runtime.retry_runner import run_with_retries


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
    assert order.visual.must_show == [
        "Show the requested semantic structure with shapes and arrows; no additional text."
    ]


def test_work_order_uses_persisted_teaching_and_packet_constraints() -> None:
    order = figure_work_order_from_pending(
        generation_id="gen-1",
        block_id="fig-1",
        content={"alt_text": "Water cycle"},
        teaching_block={
            "brief": "Show the movement of water through the cycle.",
            "evidence": "Evaporation precedes condensation.",
        },
        lesson_packet={
            "lesson": {"objective": "Explain the water cycle."},
            "scope": {
                "must_establish": [{"id": "must-1", "statement": "Evaporation"}],
                "must_not_introduce": [{"id": "not-1", "statement": "Advanced thermodynamics"}],
                "terminology": ["evaporation", " EVAPORATION ", "condensation"],
            },
        },
    )
    assert "Show the movement of water through the cycle." not in order.visual.purpose
    assert any(
        item.key == "block.fig-1.brief"
        and item.text == "Show the movement of water through the cycle."
        for item in order.source_of_truth
    )
    assert "Evaporation" not in order.visual.must_show
    assert "Water cycle" not in order.visual.must_show
    assert order.visual.must_show == [
        "Show the requested semantic structure with shapes and arrows; no additional text."
    ]
    assert any(item.key == "lesson.must_establish.0" for item in order.source_of_truth)
    assert "Advanced thermodynamics" in order.visual.must_not_show
    assert order.visual.labels_required == ["evaporation", "condensation"]
    assert any(item.key == "lesson.objective" for item in order.source_of_truth)


def test_retry_work_order_carries_latest_qc_correction_only_as_metadata() -> None:
    pending = collect_pending_figure_dispatches(
        generation_id="gen-1",
        block_execution={
            "explain:fig-1:everyone": {
                "object": "figure",
                "status": "failed_recoverable",
                "block_id": "fig-1",
                "request_id": "req-1",
                "content": {"alt_text": "Water cycle", "asset": {"status": "failed"}},
                "visual_qc": {
                    "status": "flagged_quality",
                    "reasons": ["labels are garbled"],
                    "correction_hint": "Use large, high-contrast labels.",
                },
            }
        },
    )
    assert pending[0][2].qc_correction_hint == "Use large, high-contrast labels."
    assert pending[0][2].visual.visual_style == "diagram_precision"
    prompt = build_visual_prompt(pending[0][2])
    assert "NO visible text" in prompt
    assert "LABELS REQUIRED" not in prompt
    assert "PREVIOUS QC CORRECTION" not in prompt
    assert "Use large, high-contrast labels." not in prompt


def test_water_cycle_retry_prompt_stays_provider_bounded_and_grounded() -> None:
    order = figure_work_order_from_pending(
        generation_id="gen-water",
        block_id="fig-water",
        content={"alt_text": "Water cycle diagram"},
        intent="explain",
        teaching_block={
            "brief": "Show the sequence and movement of water through the water cycle.",
            "evidence": "Evaporation precedes condensation and precipitation.",
        },
        lesson_packet={
            "lesson": {"objective": "Explain the water cycle."},
            "anchor": {"id": "water-cycle", "description": "Water moves through a repeating cycle."},
            "scope": {
                "must_establish": [
                    {"id": "evaporation", "statement": "Liquid water changes into vapor."},
                    {"id": "condensation", "statement": "Water vapor cools into droplets."},
                ],
                "must_not_introduce": [{"id": "thermo", "statement": "Advanced thermodynamics."}],
                "terminology": ["evaporation", "condensation", "precipitation", "collection"],
            },
        },
        qc_correction_hint="Use large, high-contrast labels and correct spelling.",
    )
    prompt = build_visual_prompt(order)
    assert len(prompt) <= 8000
    for text in (
        "Explain the water cycle.",
        "Show the sequence and movement of water through the water cycle.",
        "Liquid water changes into vapor.",
        "Evaporation",
        "Advanced thermodynamics.",
    ):
        assert text in prompt
    assert "LABELS REQUIRED" not in prompt
    assert "correct spelling" not in prompt


@pytest.mark.asyncio
async def test_non_retryable_provider_outcome_stops_internal_retry_loop() -> None:
    calls = 0

    async def factory(_already_retried: bool) -> ExecutorOutcome:
        nonlocal calls
        calls += 1
        return ExecutorOutcome(ok=False, errors=["HTTP 400"], retryable=False)

    result = await run_with_retries("visual", factory, max_retries=2)
    assert calls == 1
    assert result.retryable is False


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


@pytest.mark.asyncio
async def test_flagged_quality_with_url_is_failed_and_retryable() -> None:
    async def fake_execute(order, emit, **kwargs):
        _ = order, emit, kwargs
        return [
            type(
                "B",
                (),
                {
                    "status": "flagged_quality",
                    "image_url": "https://example.test/flagged.png",
                    "fallback_image_url": None,
                    "html_content": None,
                    "qc_reasons": ["label is faint"],
                    "qc_correction_hint": "increase label contrast",
                },
            )()
        ]

    apply = AsyncMock(return_value={"document_revision": 3})
    result = await dispatch_native_pending_visuals(
        generation_id="gen-flagged",
        block_execution={
            "explain:fig-1:everyone": {
                "object": "figure",
                "status": "visual_pending",
                "block_id": "fig-1",
                "request_id": "req-flagged",
                "content": {
                    "alt_text": "Leaf",
                    "asset": {
                        "status": "pending",
                        "request_id": "req-flagged",
                    },
                },
            }
        },
        apply_completion=apply,
        execute_visual_fn=fake_execute,
    )

    assert result["failed"] == 1
    assert result["results"] == [
        {
            "block_id": "fig-1",
            "request_id": "req-flagged",
            "work_order_id": "native-visual:req-flagged",
            "asset_status": "failed",
            "document_revision": 3,
            "visual_qc": {
                "status": "flagged_quality",
                "reasons": ["label is faint"],
                "correction_hint": "increase label contrast",
            },
        }
    ]
    kwargs = apply.await_args.kwargs
    assert kwargs["asset"] == {
        "status": "failed",
        "request_id": "req-flagged",
        "kind": "image",
        "src": "https://example.test/flagged.png",
    }
    assert kwargs["visual_qc"] == result["results"][0]["visual_qc"]


@pytest.mark.asyncio
async def test_product_dispatch_injects_topology_qc_adapter_and_returns_awaiting_visuals_on_flag(
    monkeypatch,
) -> None:
    from planning.whole_lesson.visual_dispatch import dispatch_and_patch_from_repo
    from planning.whole_lesson.visual_topology_recovery import TopologyRecoveryError

    class Repo:
        def __init__(self, _session, _generation_id):
            pass

        async def load_page_generation_state(self):
            return {
                "block_execution": {
                    "explain:fig-1:everyone": {
                        "object": "figure",
                        "status": "failed_recoverable",
                        "block_id": "fig-1",
                        "request_id": "req-topo",
                        "visual_qc": {"status": "flagged_quality"},
                        "content": {
                            "asset": {
                                "status": "failed",
                                "request_id": "req-topo",
                                "internal_asset_key": "internal/key.png",
                                "topology_recovery": True,
                            }
                        },
                    }
                },
                "teaching_plan": None,
                "lesson_packet": {"lesson": {"objective": "Explain the cycle."}},
            }

        async def apply_visual_completion(self, **_):
            raise AssertionError("flagged topology must not complete")

        async def persist_visual_dispatch_failure(self, **_):
            return None

        async def clear_visual_last_error(self):
            return None

    captured: dict[str, object] = {}

    async def recover(**kwargs):
        captured.update(kwargs)
        raise TopologyRecoveryError("TOPOLOGY_QC_FLAGGED", "flagged")

    monkeypatch.setattr(visual_dispatch, "PageDocumentRepository", Repo)
    monkeypatch.setattr(
        visual_dispatch.topology_recovery,
        "recover_flagged_visual_topology",
        recover,
    )

    async def provider(*_args, **_kwargs):
        raise AssertionError("ordinary image provider must not run")

    result = await dispatch_and_patch_from_repo(
        session=object(),
        generation_id="gen-topo",
        execute_visual_fn=provider,
    )
    assert captured.get("qc_fn") is not None
    assert captured.get("work_order") is not None
    assert result["failed"] >= 1
    assert result["topology_recovery"][0]["status"] == "awaiting_visuals"
def test_local_image_key_from_src_accepts_only_app_image_routes() -> None:
    assert (
        visual_dispatch._local_image_key_from_src(
            "http://127.0.0.1:8000/images/gen/explain/figure.png"
        )
        == "gen/explain/figure.png"
    )
    assert visual_dispatch._local_image_key_from_src("/images/gen/figure.png") == "gen/figure.png"
    assert visual_dispatch._local_image_key_from_src("https://example.com/images/gen/figure.png") is None
    assert visual_dispatch._local_image_key_from_src("http://127.0.0.1:8000/images/../secret.png") is None
