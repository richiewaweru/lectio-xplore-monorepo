from __future__ import annotations

import asyncio

from core.events import EventBus, LLMCallStartedEvent


def test_event_bus_publishes_to_trace_and_global_subscribers_without_blocking() -> None:
    bus = EventBus()
    trace_queue = bus.subscribe("trace-1")
    global_queue = bus.subscribe_all()

    full_queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1)
    full_queue.put_nowait({"type": "preexisting"})
    bus._subscribers["trace-1"].append(full_queue)

    event = LLMCallStartedEvent(
        generation_id="gen-1",
        node="curriculum_planner",
        slot="fast",
        attempt=1,
    )
    bus.publish("trace-1", event)

    payload = trace_queue.get_nowait()
    assert payload["type"] == "llm_call_started"
    assert payload["trace_id"] == "gen-1"
    assert payload["generation_id"] == "gen-1"
    assert payload["caller"] == "curriculum_planner"
    assert global_queue.get_nowait() == payload
    assert full_queue.get_nowait() == {"type": "preexisting"}


def test_llm_events_mirror_trace_id_and_generation_id() -> None:
    started = LLMCallStartedEvent(
        generation_id="gen-2",
        node="content_generator",
        slot="standard",
        attempt=2,
    )

    assert started.trace_id == "gen-2"
    assert started.generation_id == "gen-2"
    assert started.caller == "content_generator"
    assert started.node == "content_generator"


def test_llm_events_allow_trace_only_for_non_generation_flows() -> None:
    started = LLMCallStartedEvent(
        trace_id="planning-trace-1",
        caller="brief_planner",
        slot="standard",
        attempt=1,
    )

    assert started.trace_id == "planning-trace-1"
    assert started.generation_id is None
    assert started.caller == "brief_planner"
    assert started.node == "brief_planner"
