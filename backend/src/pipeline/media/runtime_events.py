from __future__ import annotations

from pipeline.events import (
    MediaFrameFailedEvent,
    MediaFrameReadyEvent,
    MediaFrameStartedEvent,
    MediaSlotFailedEvent,
    MediaSlotReadyEvent,
)
from pipeline.media.types import VisualFrame, VisualSlot
from pipeline.runtime_diagnostics import publish_runtime_event


def emit_frame_started(
    *,
    generation_id: str,
    section_id: str,
    slot: VisualSlot,
    frame: VisualFrame,
) -> None:
    publish_runtime_event(
        generation_id,
        MediaFrameStartedEvent(
            generation_id=generation_id,
            section_id=section_id,
            slot_id=slot.slot_id,
            slot_type=slot.slot_type.value,
            frame_key=str(frame.index),
            frame_index=frame.index,
            render=slot.preferred_render.value,
            label=frame.label,
        ),
    )


def emit_frame_ready(
    *,
    generation_id: str,
    section_id: str,
    slot: VisualSlot,
    frame: VisualFrame,
) -> None:
    publish_runtime_event(
        generation_id,
        MediaFrameReadyEvent(
            generation_id=generation_id,
            section_id=section_id,
            slot_id=slot.slot_id,
            slot_type=slot.slot_type.value,
            frame_key=str(frame.index),
            frame_index=frame.index,
            render=slot.preferred_render.value,
            label=frame.label,
        ),
    )


def emit_frame_failed(
    *,
    generation_id: str,
    section_id: str,
    slot: VisualSlot,
    frame: VisualFrame,
    error: str,
) -> None:
    publish_runtime_event(
        generation_id,
        MediaFrameFailedEvent(
            generation_id=generation_id,
            section_id=section_id,
            slot_id=slot.slot_id,
            slot_type=slot.slot_type.value,
            frame_key=str(frame.index),
            frame_index=frame.index,
            render=slot.preferred_render.value,
            label=frame.label,
            error=error,
        ),
    )


def emit_slot_state(
    *,
    generation_id: str,
    section_id: str,
    slot: VisualSlot,
    ready_frames: int,
    total_frames: int,
    error: str | None = None,
) -> None:
    if error:
        publish_runtime_event(
            generation_id,
            MediaSlotFailedEvent(
                generation_id=generation_id,
                section_id=section_id,
                slot_id=slot.slot_id,
                slot_type=slot.slot_type.value,
                ready_frames=ready_frames,
                total_frames=total_frames,
                error=error,
            ),
        )
        return

    publish_runtime_event(
        generation_id,
        MediaSlotReadyEvent(
            generation_id=generation_id,
            section_id=section_id,
            slot_id=slot.slot_id,
            slot_type=slot.slot_type.value,
            ready_frames=ready_frames,
            total_frames=total_frames,
        ),
    )
