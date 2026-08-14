from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError

import core.events as core_events
from core.llm.runner import RetryPolicy, TruncatedCompletionError, run_llm
from core.llm.types import ModelFamily, ModelSlot, ModelSpec


class _FakeAgent:
    async def run(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return SimpleNamespace(
            output="ok",
            usage=SimpleNamespace(
                prompt_tokens=120,
                completion_tokens=45,
                details={
                    "prompt_cache_hit_tokens": 90,
                    "prompt_cache_miss_tokens": 30,
                    "reasoning_tokens": 12,
                },
            )
        )


class _LengthLimitedAgent:
    async def run(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return SimpleNamespace(
            output="partial",
            response=SimpleNamespace(
                choices=[SimpleNamespace(finish_reason="length")]
            ),
            usage=SimpleNamespace(
                prompt_tokens=120,
                completion_tokens=45,
                details={},
            ),
        )


class _RaisingAgent:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc
        self.calls = 0

    async def run(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        self.calls += 1
        raise self.exc


class _TimeoutThenSuccessAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("provider timed out")
        return SimpleNamespace(output="ok")


@pytest.mark.asyncio
async def test_run_llm_publishes_cache_usage_fields_on_success() -> None:
    captured: list[dict] = []

    def _capture(trace_id: str, event):  # type: ignore[no-untyped-def]
        _ = trace_id
        captured.append(event.model_dump(mode="json", exclude_none=True))

    with patch.object(core_events.event_bus, "publish", side_effect=_capture):
        await run_llm(
            caller="planner",
            trace_id="trace-1",
            generation_id="gen-1",
            agent=_FakeAgent(),
            user_prompt="hello",
            model="fake-model",
            slot=ModelSlot.STANDARD,
            spec=ModelSpec(
                family=ModelFamily.OPENAI_COMPATIBLE,
                model_name="deepseek-v4-pro",
                base_url="https://api.deepseek.com",
            ),
            node="v3_stage2_expander",
            model_settings={"max_tokens": 100},
        )

    success = next(event for event in captured if event["type"] == "llm_call_succeeded")
    assert success["tokens_in"] == 120
    assert success["tokens_out"] == 45
    assert success["prompt_cache_hit_tokens"] == 90
    assert success["prompt_cache_miss_tokens"] == 30
    assert success["thinking_tokens"] == 12


@pytest.mark.asyncio
async def test_run_llm_preserves_missing_generation_id_for_pre_generation_calls() -> None:
    captured: list[dict] = []

    def _capture(trace_id: str, event):  # type: ignore[no-untyped-def]
        _ = trace_id
        captured.append(event.model_dump(mode="json", exclude_none=False))

    with patch.object(core_events.event_bus, "publish", side_effect=_capture):
        await run_llm(
            caller="v3_constructor",
            trace_id="constructor-trace",
            generation_id=None,
            agent=_FakeAgent(),
            user_prompt="hello",
            model="fake-model",
            slot=ModelSlot.FAST,
            spec=ModelSpec(family=ModelFamily.TEST, model_name="fake-model"),
        )

    llm_events = [event for event in captured if event["type"].startswith("llm_call_")]
    assert llm_events
    assert {event["generation_id"] for event in llm_events} == {None}


@pytest.mark.asyncio
async def test_run_llm_raises_typed_error_for_length_truncation() -> None:
    with pytest.raises(TruncatedCompletionError, match="finish_reason=length"):
        await run_llm(
            caller="planner",
            trace_id="trace-truncated",
            generation_id="gen-truncated",
            agent=_LengthLimitedAgent(),
            user_prompt="hello",
            model="fake-model",
            slot=ModelSlot.STANDARD,
            spec=ModelSpec(
                family=ModelFamily.OPENAI_COMPATIBLE,
                model_name="deepseek-v4-pro",
                base_url="https://api.deepseek.com",
            ),
            node="v3_stage1_planner",
            model_settings={"max_tokens": 120000},
        )


@pytest.mark.asyncio
async def test_model_api_error_is_inherently_retryable_when_local_budget_is_one() -> None:
    captured: list[dict] = []
    agent = _RaisingAgent(
        ModelAPIError(model_name="provider-model", message="Connection error")
    )

    def _capture(trace_id: str, event):  # type: ignore[no-untyped-def]
        _ = trace_id
        captured.append(event.model_dump(mode="json", exclude_none=True))

    with (
        patch.object(core_events.event_bus, "publish", side_effect=_capture),
        pytest.raises(ModelAPIError, match="Connection error"),
    ):
        await run_llm(
            caller="planner",
            trace_id="trace-connection",
            agent=agent,
            user_prompt="hello",
            retry_policy=RetryPolicy(max_attempts=1),
        )

    failed = next(event for event in captured if event["type"] == "llm_call_failed")
    assert failed["retryable"] is True
    assert failed["error_class"] == "ModelAPIError"
    assert agent.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_retryable"),
    [(400, False), (429, True), (503, True)],
)
async def test_model_http_error_uses_status_sensitive_retryability(
    status_code: int,
    expected_retryable: bool,
) -> None:
    captured: list[dict] = []
    agent = _RaisingAgent(
        ModelHTTPError(
            status_code=status_code,
            model_name="provider-model",
            body={"error": "provider response"},
        )
    )

    def _capture(trace_id: str, event):  # type: ignore[no-untyped-def]
        _ = trace_id
        captured.append(event.model_dump(mode="json", exclude_none=True))

    with (
        patch.object(core_events.event_bus, "publish", side_effect=_capture),
        pytest.raises(ModelHTTPError),
    ):
        await run_llm(
            caller="planner",
            trace_id=f"trace-http-{status_code}",
            agent=agent,
            user_prompt="hello",
            retry_policy=RetryPolicy(max_attempts=1),
        )

    failed = next(event for event in captured if event["type"] == "llm_call_failed")
    assert failed["retryable"] is expected_retryable
    assert agent.calls == 1


@pytest.mark.asyncio
async def test_attempt_start_offsets_events_without_changing_local_retry_budget() -> None:
    captured: list[dict] = []
    agent = _TimeoutThenSuccessAgent()
    sleep = AsyncMock()

    def _capture(trace_id: str, event):  # type: ignore[no-untyped-def]
        _ = trace_id
        captured.append(event.model_dump(mode="json", exclude_none=True))

    with (
        patch.object(core_events.event_bus, "publish", side_effect=_capture),
        patch("core.llm.runner.asyncio.sleep", new=sleep),
    ):
        await run_llm(
            caller="planner",
            trace_id="trace-offset",
            agent=agent,
            user_prompt="hello",
            retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.25),
            attempt_start=7,
        )

    assert [event["attempt"] for event in captured] == [7, 7, 8, 8]
    assert [event["type"] for event in captured] == [
        "llm_call_started",
        "llm_call_failed",
        "llm_call_started",
        "llm_call_succeeded",
    ]
    assert captured[1]["retryable"] is True
    sleep.assert_awaited_once_with(0.25)
