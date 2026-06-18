from __future__ import annotations

from pipeline.media.assembly import slot_is_ready
from pipeline.media.types import MediaPlan, SlotType, VisualSlot
from pipeline.state import TextbookPipelineState

_SECTION_LEVEL_VISUAL_TYPES = {
    SlotType.DIAGRAM,
    SlotType.DIAGRAM_COMPARE,
    SlotType.DIAGRAM_SERIES,
}
_INLINE_BLOCK_TARGETS = {"practice", "worked_example"}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _required_slots(media_plan: MediaPlan | None) -> list[VisualSlot]:
    if media_plan is None:
        return []
    return [slot for slot in media_plan.slots if slot.required]


def section_level_visual_slots(media_plan: MediaPlan | None) -> list[VisualSlot]:
    return [
        slot
        for slot in _required_slots(media_plan)
        if slot.slot_type in _SECTION_LEVEL_VISUAL_TYPES
        and slot.block_target not in _INLINE_BLOCK_TARGETS
    ]


def visual_mode(media_plan: MediaPlan | None) -> str | None:
    for slot in section_level_visual_slots(media_plan):
        render = slot.preferred_render.value
        if render in {"svg", "image"}:
            return render
    return None


def required_visual_fields(media_plan: MediaPlan | None) -> list[str]:
    return _dedupe([slot.slot_type.value for slot in section_level_visual_slots(media_plan)])


def slot_ready(state: TextbookPipelineState, slot: VisualSlot) -> bool:
    section_id = state.current_section_id
    if section_id is None:
        return False
    slot_result = state.media_slot_results.get(section_id, {}).get(slot.slot_id)
    if slot_result is not None:
        return slot_result.ready
    frame_results = state.media_frame_results.get(section_id, {}).get(slot.slot_id)
    return slot_is_ready(slot, frame_results)


def pending_required_slot_ids(state: TextbookPipelineState) -> list[str]:
    media_plan = state.media_plans.get(state.current_section_id)
    return _dedupe(
        [
            slot.slot_id
            for slot in _required_slots(media_plan)
            if not slot_ready(state, slot)
        ]
    )
