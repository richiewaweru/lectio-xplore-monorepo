from __future__ import annotations

from pipeline.events import SlotRenderModeResolvedEvent, event_bus
from pipeline.media.prompts.intelligent_image_prompt import (
    build_intelligent_image_prompt,
    should_resolve_intelligent_image_prompt,
)
from pipeline.media.planner.media_planner import media_planner as build_media_plan
from pipeline.media.types import SlotType, VisualRender
from pipeline.state import TextbookPipelineState


def _fallback_render_for_slot(slot_type: SlotType, preferred_render: VisualRender) -> VisualRender | None:
    if preferred_render == VisualRender.IMAGE:
        return VisualRender.SVG
    if preferred_render == VisualRender.HTML_SIMULATION:
        return VisualRender.SVG
    if preferred_render == VisualRender.SVG and slot_type == SlotType.SIMULATION:
        return VisualRender.HTML_SIMULATION
    return None


def _frame_output_placeholders(render: VisualRender) -> dict[str, str | None]:
    if render == VisualRender.IMAGE:
        return {"image_url": None}
    return {"svg_content": None}


async def _resolve_static_slot_prompts(
    typed: TextbookPipelineState,
    *,
    sid: str,
    section_title: str,
    plan,
    model_overrides: dict | None = None,
) -> None:
    for slot in plan.slots:
        if not should_resolve_intelligent_image_prompt(slot):
            continue
        try:
            prompt, preferred_render = await build_intelligent_image_prompt(
                section_title=section_title,
                slot=slot,
                style_context=typed.style_context,
                generation_id=typed.request.generation_id or "",
                section_id=sid,
                model_overrides=model_overrides,
                generation_mode=typed.request.mode,
            )
        except Exception:
            continue

        slot.preferred_render = preferred_render
        slot.fallback_render = _fallback_render_for_slot(slot.slot_type, preferred_render)
        generation_id = typed.request.generation_id or ""
        if generation_id:
            event_bus.publish(
                generation_id,
                SlotRenderModeResolvedEvent(
                    generation_id=generation_id,
                    section_id=sid,
                    slot_id=slot.slot_id,
                    render_mode=preferred_render.value,
                    decided_by="intelligent_image_prompt",
                ),
            )
        if len(slot.frames) == 1:
            slot.generation_prompt = prompt
        for frame in slot.frames:
            frame.output_placeholders = _frame_output_placeholders(preferred_render)


async def media_planner(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
) -> dict:
    typed = TextbookPipelineState.parse(state)
    sid = typed.current_section_id
    section = typed.generated_sections.get(sid)
    if sid is None or section is None or typed.current_section_plan is None:
        return {"completed_nodes": ["media_planner"]}

    plan = build_media_plan(
        section_plan=typed.current_section_plan,
        section_content=section,
        template_contract=typed.contract,
        style_context=typed.style_context,
    )
    await _resolve_static_slot_prompts(
        typed,
        sid=sid,
        section_title=section.header.title,
        plan=plan,
        model_overrides=model_overrides,
    )
    return {
        "media_plans": {sid: plan},
        "media_lifecycle": {sid: "planned"},
        "completed_nodes": ["media_planner"],
    }


__all__ = ["media_planner"]
