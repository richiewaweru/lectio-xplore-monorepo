from __future__ import annotations

from collections import defaultdict
from typing import Any

import core.events as core_events
from pipeline.state import TextbookPipelineState

_NODE_ATTEMPTS: dict[tuple[str, str], int] = defaultdict(int)


def generation_id_from_state(state: TextbookPipelineState | dict) -> str:
    typed = TextbookPipelineState.parse(state)
    return typed.request.generation_id or ""


def publish_runtime_event(generation_id: str, event: Any) -> None:
    if generation_id and generation_id.strip():
        core_events.event_bus.publish(generation_id, event)


def current_section_attempt(
    state: TextbookPipelineState | dict,
    section_id: str | None,
) -> tuple[int | None, str]:
    typed = TextbookPipelineState.parse(state)
    if section_id is None:
        return None, "initial"

    is_rerender = (
        typed.pending_rerender_for(section_id) is not None
        or typed.pending_media_retry_for(section_id) is not None
    )
    trigger = "rerender" if is_rerender else "initial"
    media_attempts = sum(
        sum(frame_counts.values())
        for frame_counts in typed.media_frame_retry_count.get(section_id, {}).values()
    )
    attempt = typed.rerender_count.get(section_id, 0) + media_attempts + 1
    if is_rerender:
        attempt += 1
    return attempt, trigger


def next_node_attempt(generation_id: str, node: str) -> int:
    key = (generation_id, node)
    _NODE_ATTEMPTS[key] += 1
    return _NODE_ATTEMPTS[key]


def clear_node_attempts(generation_id: str) -> None:
    stale = [key for key in _NODE_ATTEMPTS if key[0] == generation_id]
    for key in stale:
        del _NODE_ATTEMPTS[key]


def node_error_messages(
    errors: list[Any] | None,
    *,
    node: str,
    section_id: str | None = None,
) -> list[str]:
    if not errors:
        return []

    messages: list[str] = []
    for error in errors:
        if isinstance(error, dict):
            error_node = error.get("node")
            error_section_id = error.get("section_id")
            message = error.get("message")
        else:
            error_node = getattr(error, "node", None)
            error_section_id = getattr(error, "section_id", None)
            message = getattr(error, "message", None)

        if error_node != node:
            continue
        if section_id is not None and error_section_id != section_id:
            continue
        if message:
            messages.append(str(message))
    return messages
