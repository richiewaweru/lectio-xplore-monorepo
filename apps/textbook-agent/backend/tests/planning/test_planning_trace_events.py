from __future__ import annotations

from unittest.mock import patch

from planning.routes import (
    _close_planning_trace,
    _register_planning_trace,
)


def test_planning_trace_registration_and_close_publish_existing_events() -> None:
    captured: list[dict] = []

    def capture(trace_id: str, event) -> None:  # type: ignore[no-untyped-def]
        assert trace_id == "path:user-1:trace"
        captured.append(event.model_dump(mode="json"))

    with patch("planning.routes.event_bus.publish", side_effect=capture):
        _register_planning_trace("path:user-1:trace", "user-1")
        _close_planning_trace("path:user-1:trace")

    assert [event["type"] for event in captured] == ["trace_registered", "trace_closed"]
    assert captured[0]["user_id"] == "user-1"
    assert captured[0]["source"] == "planning"
