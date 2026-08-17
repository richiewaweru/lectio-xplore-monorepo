from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Literal, Self

from pydantic import BaseModel, model_validator


class EventBus:
    """Simple in-process pub/sub bus for SSE streaming and telemetry."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
        self._global_subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    def subscribe(self, trace_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[trace_id].append(queue)
        return queue

    def subscribe_all(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._global_subscribers.append(queue)
        return queue

    def publish(self, trace_id: str, event: BaseModel | dict) -> None:
        payload = (
            event.model_dump(mode="json", exclude_none=True)
            if hasattr(event, "model_dump")
            else event
        )
        for queue in list(self._subscribers.get(trace_id, [])) + list(self._global_subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                continue

    def unsubscribe(self, trace_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        queues = self._subscribers.get(trace_id, [])
        if queue in queues:
            queues.remove(queue)
        if not queues and trace_id in self._subscribers:
            del self._subscribers[trace_id]

    def unsubscribe_all(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._global_subscribers:
            self._global_subscribers.remove(queue)


event_bus = EventBus()


class _LLMCallEvent(BaseModel):
    trace_id: str | None = None
    generation_id: str | None = None
    caller: str | None = None
    node: str | None = None
    slot: str
    family: str | None = None
    model_name: str | None = None
    endpoint_host: str | None = None
    attempt: int
    section_id: str | None = None
    structured_mode: str | None = None
    schema_source_kind: str | None = None
    schema_fingerprint: str | None = None
    strict_fallback: bool | None = None

    @model_validator(mode="after")
    def _mirror_trace_and_legacy_fields(self) -> Self:
        if self.trace_id is None and self.generation_id is None:
            raise ValueError("trace_id or generation_id is required")
        if self.trace_id is None:
            self.trace_id = self.generation_id
        if self.caller is None and self.node is None:
            raise ValueError("caller or node is required")
        if self.caller is None:
            self.caller = self.node
        if self.node is None:
            self.node = self.caller
        return self


class LLMCallStartedEvent(_LLMCallEvent):
    type: Literal["llm_call_started"] = "llm_call_started"


class LLMCallSucceededEvent(_LLMCallEvent):
    type: Literal["llm_call_succeeded"] = "llm_call_succeeded"
    latency_ms: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    thinking_tokens: int | None = None
    cost_usd: float | None = None


class LLMCallFailedEvent(_LLMCallEvent):
    type: Literal["llm_call_failed"] = "llm_call_failed"
    latency_ms: float | None = None
    retryable: bool = True
    error: str
    error_class: str | None = None


class TraceRegisteredEvent(BaseModel):
    type: Literal["trace_registered"] = "trace_registered"
    trace_id: str
    user_id: str
    source: Literal["generation", "planning", "block_generate"]


class TraceClosedEvent(BaseModel):
    type: Literal["trace_closed"] = "trace_closed"
    trace_id: str
    source: Literal["generation", "planning", "block_generate"]


__all__ = [
    "EventBus",
    "LLMCallStartedEvent",
    "LLMCallSucceededEvent",
    "LLMCallFailedEvent",
    "TraceRegisteredEvent",
    "TraceClosedEvent",
    "event_bus",
]
