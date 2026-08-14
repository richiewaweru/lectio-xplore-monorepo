from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import core.events as core_events
from v3_execution.executors.visual_executor import execute_visual
from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem
from telemetry.service import TelemetryMonitor


def _order() -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="visual-telemetry-order",
        visual=VisualPlanItem(
            id="visual-telemetry",
            attaches_to="section-1",
            component_id="diagram-block",
            mode="diagram",
            purpose="show the concept",
        ),
        source_of_truth=[],
    )


class _Store:
    async def image_exists(self, *, key: str) -> bool:
        _ = key
        return False

    async def store_image(self, image_bytes: bytes, **kwargs: object) -> str:
        _ = image_bytes, kwargs
        return "https://cdn.example/visual.png"


async def _emit(_event: str, _payload: dict) -> None:
    return None


@pytest.mark.asyncio
async def test_visual_provider_attempt_emits_attributed_success_ledger_event(monkeypatch) -> None:
    class Client:
        async def generate_image(self, *, prompt: str):
            _ = prompt
            return SimpleNamespace(bytes=b"image", format="png", mime_type="image/png")

    async def run_once(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    captured: list[dict] = []
    monkeypatch.setenv("V3_IMAGE_CACHE_ENABLED", "false")
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.get_image_client", lambda: Client()
    )
    monkeypatch.setattr(
        "media.storage.image_store.get_image_store", lambda: _Store()
    )
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="xai", model_name="grok-imagine-image"),
    )
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.run_with_retries", run_once
    )

    def publish(_trace_id: str, event) -> None:  # type: ignore[no-untyped-def]
        if event.type.startswith("llm_call_"):
            captured.append(event.model_dump(mode="json", exclude_none=False))

    with patch.object(core_events.event_bus, "publish", side_effect=publish):
        blocks = await execute_visual(
            _order(),
            _emit,
            trace_id="visual-trace",
            generation_id="generation-visual",
        )

    assert blocks[0].status == "ready"
    assert [event["type"] for event in captured] == [
        "llm_call_started",
        "llm_call_succeeded",
    ]
    success = captured[-1]
    assert success["generation_id"] == "generation-visual"
    assert success["trace_id"] == "visual-trace"
    assert success["caller"] == "visual_provider"
    assert success["node"] == "visual_executor"
    assert success["family"] == "xai"
    assert success["model_name"] == "grok-imagine-image"
    assert success["attempt"] == 1
    assert success["latency_ms"] is not None


@pytest.mark.asyncio
async def test_visual_provider_failure_emits_retryable_error_class(monkeypatch) -> None:
    class Client:
        async def generate_image(self, *, prompt: str):
            _ = prompt
            raise TimeoutError("image provider timeout")

    async def run_once(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    captured: list[dict] = []
    monkeypatch.setenv("V3_IMAGE_CACHE_ENABLED", "false")
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.get_image_client", lambda: Client()
    )
    monkeypatch.setattr(
        "media.storage.image_store.get_image_store", lambda: _Store()
    )
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="gemini", model_name="gemini-image"),
    )
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.run_with_retries", run_once
    )

    def publish(_trace_id: str, event) -> None:  # type: ignore[no-untyped-def]
        if event.type.startswith("llm_call_"):
            captured.append(event.model_dump(mode="json", exclude_none=False))

    with patch.object(core_events.event_bus, "publish", side_effect=publish):
        blocks = await execute_visual(
            _order(),
            _emit,
            trace_id="visual-failure-trace",
            generation_id="generation-visual-failure",
        )

    assert blocks[0].status == "failed"
    failed = captured[-1]
    assert [event["type"] for event in captured] == [
        "llm_call_started",
        "llm_call_failed",
    ]
    assert failed["generation_id"] == "generation-visual-failure"
    assert failed["family"] == "gemini"
    assert failed["error_class"] == "TimeoutError"
    assert failed["retryable"] is True


@pytest.mark.asyncio
async def test_visual_ledger_event_uses_generation_lookup_for_user_attribution() -> None:
    class Repo:
        def __init__(self) -> None:
            self.saved: list[dict] = []

        async def save_call(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
            self.saved.append(kwargs)

    repo = Repo()
    monitor = TelemetryMonitor()

    async def load_repo():
        return repo

    async def lookup(_generation_id: str) -> str:
        return "visual-owner"

    monitor.configure(llm_call_repository_factory=load_repo)
    monitor._user_id_for_generation = lookup  # type: ignore[method-assign]
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "llm_call_succeeded",
            "trace_id": "native-visual:gen-1:req-1",
            "generation_id": "gen-1",
            "caller": "visual_provider",
            "node": "visual_executor",
            "slot": "visual",
            "family": "xai",
            "model_name": "grok-imagine-image",
            "attempt": 1,
            "latency_ms": 12.5,
        }
    )

    assert repo.saved[0]["user_id"] == "visual-owner"
    assert repo.saved[0]["generation_id"] == "gen-1"
    assert repo.saved[0]["node"] == "visual_executor"
