from __future__ import annotations

from dataclasses import dataclass

from pipeline.media.assembly import frame_result_key, frame_has_required_artifact
from pipeline.media.types import SlotType, VisualSlot
from pipeline.state import MediaFrameRetryRequest, TextbookPipelineState

_MEDIA_BLOCK_TYPES = {
    "diagram",
    "diagram_compare",
    "diagram_series",
    "simulation",
    "simulation_block",
}
_SIMULATION_BLOCK_TYPES = {"simulation", "simulation_block"}
_STATIC_SLOT_TYPES = {
    SlotType.DIAGRAM,
    SlotType.DIAGRAM_COMPARE,
    SlotType.DIAGRAM_SERIES,
}
MAX_MEDIA_FRAME_RETRIES = 1


@dataclass(frozen=True)
class MediaBlockStatus:
    blocked: bool
    slot_ids: list[str]
    reason: str | None = None


def is_media_block(block_type: str | None) -> bool:
    return bool(block_type and block_type in _MEDIA_BLOCK_TYPES)


def executor_for_slot(slot: VisualSlot) -> str:
    if slot.slot_type == SlotType.SIMULATION:
        return "interaction_generator"
    if slot.preferred_render.value == "image":
        return "image_generator"
    return "diagram_generator"


def block_matches_slot(block_type: str | None, slot: VisualSlot) -> bool:
    if block_type is None:
        return True
    if block_type in _SIMULATION_BLOCK_TYPES:
        return slot.slot_type == SlotType.SIMULATION
    return block_type == slot.slot_type.value


def frame_retry_count(
    state: TextbookPipelineState,
    *,
    section_id: str,
    slot_id: str,
    frame_key: str,
) -> int:
    return (
        state.media_frame_retry_count.get(section_id, {})
        .get(slot_id, {})
        .get(frame_key, 0)
    )


def next_retry_request(
    state: TextbookPipelineState,
    *,
    section_id: str,
    blocking_issues: list[dict] | None = None,
) -> MediaFrameRetryRequest | None:
    media_plan = state.media_plans.get(section_id)
    if media_plan is None:
        return None

    blocks = [
        issue.get("block")
        for issue in (blocking_issues or [])
        if is_media_block(issue.get("block"))
    ]

    for slot in media_plan.slots:
        if not slot.required:
            continue
        if blocks and not any(block_matches_slot(block, slot) for block in blocks):
            continue
        section_frame_results = state.media_frame_results.get(section_id, {}).get(slot.slot_id, {})
        for frame in slot.frames:
            key = frame_result_key(frame)
            frame_result = section_frame_results.get(key)
            if frame_has_required_artifact(slot, frame_result):
                continue
            if frame_retry_count(
                state,
                section_id=section_id,
                slot_id=slot.slot_id,
                frame_key=key,
            ) >= MAX_MEDIA_FRAME_RETRIES:
                continue
            return MediaFrameRetryRequest(
                section_id=section_id,
                slot_id=slot.slot_id,
                slot_type=slot.slot_type.value,
                frame_key=key,
                frame_index=frame.index,
                executor_node=executor_for_slot(slot),
                reason=next(
                    (
                        issue.get("message")
                        for issue in (blocking_issues or [])
                        if block_matches_slot(issue.get("block"), slot)
                    ),
                    None,
                ),
            )
    return None


def blocked_required_media(
    state: TextbookPipelineState,
    *,
    section_id: str,
) -> MediaBlockStatus:
    media_plan = state.media_plans.get(section_id)
    if media_plan is None:
        return MediaBlockStatus(blocked=False, slot_ids=[])

    blocked_slots: list[str] = []
    for slot in media_plan.slots:
        if not slot.required:
            continue
        section_frame_results = state.media_frame_results.get(section_id, {}).get(slot.slot_id, {})
        slot_ready = True
        exhausted = True
        for frame in slot.frames:
            key = frame_result_key(frame)
            frame_result = section_frame_results.get(key)
            if frame_has_required_artifact(slot, frame_result):
                continue
            slot_ready = False
            if frame_retry_count(
                state,
                section_id=section_id,
                slot_id=slot.slot_id,
                frame_key=key,
            ) < MAX_MEDIA_FRAME_RETRIES:
                exhausted = False
        if not slot_ready and exhausted:
            blocked_slots.append(slot.slot_id)

    if not blocked_slots:
        return MediaBlockStatus(blocked=False, slot_ids=[])

    return MediaBlockStatus(
        blocked=True,
        slot_ids=blocked_slots,
        reason=(
            "Required media is still incomplete after exhausting the per-frame retry budget."
        ),
    )

