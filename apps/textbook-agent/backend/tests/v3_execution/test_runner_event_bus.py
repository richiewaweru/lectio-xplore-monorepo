from __future__ import annotations

import pytest

from core.events import event_bus
from v3_execution.runtime import events
from v3_execution.runtime.runner import sse_event_stream


class _BlueprintMetadata:
    title = "Test Lesson"
    subject = "Mathematics"


class _Blueprint:
    metadata = _BlueprintMetadata()


@pytest.mark.asyncio
async def test_sse_stream_publishes_events_to_event_bus() -> None:
    generation_id = "v3-runner-event-bus"
    queue = event_bus.subscribe(generation_id)
    try:
        stream = sse_event_stream(
            blueprint=_Blueprint(),  # type: ignore[arg-type]
            generation_id=generation_id,
            blueprint_id="bp-1",
            template_id="guided-concept-path",
            trace_id=generation_id,
        )
        async for _chunk in stream:
            pass
        received: list[dict] = []
        while not queue.empty():
            received.append(queue.get_nowait())
        event_types = {payload.get("type") for payload in received}
        assert events.GENERATION_STARTED in event_types
        assert events.GENERATION_COMPLETE in event_types or events.GENERATION_WARNING in event_types
    finally:
        event_bus.unsubscribe(generation_id, queue)
