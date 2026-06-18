from __future__ import annotations

import os
from importlib import import_module

from pipeline.media.assembly import apply_slot_results_to_section, build_slot_result, frame_result_key
from pipeline.media.prompts.image_prompts import (
    build_compare_image_prompts,
    build_image_generation_prompt,
    build_series_step_image_prompt,
)
from pipeline.media.utils.image_processing import normalise_image_for_frame
from pipeline.media.runtime_events import (
    emit_frame_failed,
    emit_frame_ready,
    emit_frame_started,
    emit_slot_state,
)
from pipeline.media.types import SlotType, VisualFrameResult, VisualFrameResultStatus
from pipeline.state import PipelineError, TextbookPipelineState


def _image_size_for_frame(slot, frame) -> str:
    if getattr(slot, "sizing", "full") == "compact":
        return "1024x1024"
    if frame.target_w is None or frame.target_h is None:
        return "1024x1024"
    ratio = frame.target_w / frame.target_h
    if ratio > 1.4:
        return "1792x1024"
    return "1024x1024"


def _static_image_slots(state: TextbookPipelineState) -> list:
    media_plan = state.media_plans.get(state.current_section_id)
    if media_plan is None:
        return []
    return [
        slot
        for slot in media_plan.slots
        if slot.slot_type in {SlotType.DIAGRAM, SlotType.DIAGRAM_COMPARE, SlotType.DIAGRAM_SERIES}
        and slot.preferred_render.value == "image"
    ]


async def _ensure_store_and_client(legacy, *, _store, _client):
    store = _store or legacy.get_image_store()
    client = _client or legacy.get_image_client()
    provider_spec = legacy.load_image_provider_spec()
    api_key_present = (
        bool(legacy.resolve_gemini_image_api_key())
        if provider_spec.provider == "gemini"
        else bool(os.getenv(provider_spec.api_key_env or ""))
    )
    return store, client, api_key_present, provider_spec.provider


async def _generate_image_frame(
    *,
    legacy,
    slot,
    frame,
    section_title: str,
    style_context,
    sid: str,
    generation_id: str,
    store,
    client,
    api_key_present: bool,
    variant: str,
) -> VisualFrameResult:
    prompt = slot.generation_prompt or build_image_generation_prompt(
        section_title=section_title,
        slot=slot,
        frame=frame,
        style_context=style_context,
    )
    image_result, _attempts = await legacy._request_image_bytes(
        client=client,
        prompt=prompt,
        section_id=sid,
        variant=variant,
        api_key_present=api_key_present,
        size=_image_size_for_frame(slot, frame),
    )
    normalised_bytes = normalise_image_for_frame(
        image_result.bytes, target_w=frame.target_w, target_h=frame.target_h
    )
    store_format = "png" if (frame.target_w and frame.target_h) else image_result.format
    image_url = await legacy._store_image_with_logging(
        store,
        image_bytes=normalised_bytes,
        generation_id=generation_id,
        section_id=sid,
        filename=f"{variant}.{store_format}",
        format=store_format,
        variant=variant,
    )
    return VisualFrameResult(
        slot_id=slot.slot_id,
        frame_index=frame.index,
        label=frame.label,
        render=slot.preferred_render,
        status=VisualFrameResultStatus.GENERATED,
        image_url=image_url,
        alt_text=f"{frame.label or section_title} for {slot.caption}",
    )


async def _generate_compare_frame(
    *,
    legacy,
    slot,
    frame,
    peer_frame,
    section_title: str,
    style_context,
    sid: str,
    generation_id: str,
    store,
    client,
    api_key_present: bool,
) -> VisualFrameResult:
    before_prompt, after_prompt = build_compare_image_prompts(
        section_title=section_title,
        slot=slot,
        before_frame=slot.frames[0],
        after_frame=slot.frames[1],
        style_context=style_context,
    )
    prompt = before_prompt if frame.index == 0 else after_prompt
    variant = "compare-before" if frame.index == 0 else "compare-after"
    image_result, _attempts = await legacy._request_image_bytes(
        client=client,
        prompt=prompt,
        section_id=sid,
        variant=variant,
        api_key_present=api_key_present,
        size=_image_size_for_frame(slot, frame),
    )
    normalised_bytes = normalise_image_for_frame(
        image_result.bytes, target_w=frame.target_w, target_h=frame.target_h
    )
    store_format = "png" if (frame.target_w and frame.target_h) else image_result.format
    image_url = await legacy._store_image_with_logging(
        store,
        image_bytes=normalised_bytes,
        generation_id=generation_id,
        section_id=sid,
        filename=f"{variant}.{store_format}",
        format=store_format,
        variant=variant,
    )
    _ = peer_frame
    return VisualFrameResult(
        slot_id=slot.slot_id,
        frame_index=frame.index,
        label=frame.label,
        render=slot.preferred_render,
        status=VisualFrameResultStatus.GENERATED,
        image_url=image_url,
        alt_text=f"{frame.label or section_title} for {slot.caption}",
    )


async def _generate_series_frame(
    *,
    legacy,
    slot,
    frame,
    section_title: str,
    style_context,
    sid: str,
    generation_id: str,
    store,
    client,
    api_key_present: bool,
) -> VisualFrameResult:
    prompt = build_series_step_image_prompt(
        section_title=section_title,
        slot=slot,
        frame=frame,
        style_context=style_context,
    )
    variant = f"series-step-{frame.index + 1}"
    image_result, _attempts = await legacy._request_image_bytes(
        client=client,
        prompt=prompt,
        section_id=sid,
        variant=variant,
        api_key_present=api_key_present,
        size=_image_size_for_frame(slot, frame),
        prompt_details={
            "step_index": frame.index + 1,
            "step_total": len(slot.frames),
        },
    )
    normalised_bytes = normalise_image_for_frame(
        image_result.bytes, target_w=frame.target_w, target_h=frame.target_h
    )
    store_format = "png" if (frame.target_w and frame.target_h) else image_result.format
    image_url = await legacy._store_image_with_logging(
        store,
        image_bytes=normalised_bytes,
        generation_id=generation_id,
        section_id=sid,
        filename=f"{variant}.{store_format}",
        format=store_format,
        variant=variant,
    )
    return VisualFrameResult(
        slot_id=slot.slot_id,
        frame_index=frame.index,
        label=frame.label,
        render=slot.preferred_render,
        status=VisualFrameResultStatus.GENERATED,
        image_url=image_url,
        alt_text=f"{frame.label or section_title} for {slot.caption}",
    )


async def image_generator(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    _store=None,
    _client=None,
) -> dict:
    _ = model_overrides
    typed = TextbookPipelineState.parse(state)
    legacy = import_module("pipeline.nodes.image_generator")
    sid = typed.current_section_id
    section = typed.generated_sections.get(sid)
    generation_id = typed.request.generation_id or ""

    if sid is None or section is None:
        return {"completed_nodes": ["image_generator"]}

    retry_request = typed.pending_media_retry_for(sid)
    if retry_request is not None and retry_request.executor_node != "image_generator":
        return {"completed_nodes": ["image_generator"]}

    slots = _static_image_slots(typed)
    if retry_request is not None:
        slots = [slot for slot in slots if slot.slot_id == retry_request.slot_id]

    outcomes = dict(typed.diagram_outcomes)
    if not slots:
        legacy._publish_image_outcome(generation_id, sid, "skipped")
        outcomes = legacy._with_outcome(typed, sid, "skipped")["diagram_outcomes"]
        return {
            "diagram_outcomes": outcomes,
            "completed_nodes": ["image_generator"],
        }

    if typed.style_context is None:
        legacy._publish_image_outcome(generation_id, sid, "error", error_message="Missing style context")
        outcomes = legacy._with_outcome(typed, sid, "error")["diagram_outcomes"]
        return {
            "errors": [
                PipelineError(
                    node="image_generator",
                    section_id=sid,
                    message="style_context is None -- curriculum_planner may have failed",
                    recoverable=False,
                )
            ],
            "diagram_outcomes": outcomes,
            "completed_nodes": ["image_generator"],
        }

    try:
        store, client, api_key_present, provider = await _ensure_store_and_client(
            legacy,
            _store=_store,
            _client=_client,
        )
    except Exception as exc:
        legacy._publish_image_outcome(generation_id, sid, "error", error_message=str(exc))
        outcomes = legacy._with_outcome(typed, sid, "error")["diagram_outcomes"]
        return {
            "errors": [
                PipelineError(
                    node="image_generator",
                    section_id=sid,
                    message=f"Image client setup failed: {exc}",
                    recoverable=True,
                )
            ],
            "diagram_outcomes": outcomes,
            "completed_nodes": ["image_generator"],
        }

    if _client is None and not api_key_present:
        message = (
            "No Gemini API key found for image generation."
            if provider == "gemini"
            else f"No API key found for image generation provider '{provider}'."
        )
        legacy._publish_image_outcome(generation_id, sid, "error", error_message=message)
        outcomes = legacy._with_outcome(typed, sid, "error")["diagram_outcomes"]
        return {
            "errors": [
                PipelineError(
                    node="image_generator",
                    section_id=sid,
                    message=message,
                    recoverable=True,
                )
            ],
            "diagram_outcomes": outcomes,
            "completed_nodes": ["image_generator"],
        }

    updated_section = section
    section_slot_results = dict(typed.media_slot_results.get(sid, {}))
    section_frame_results = {
        slot_id: dict(frame_results)
        for slot_id, frame_results in typed.media_frame_results.get(sid, {}).items()
    }
    errors: list[PipelineError] = []

    for slot in slots:
        slot_frame_results = dict(section_frame_results.get(slot.slot_id, {}))
        target_frames = slot.frames
        if retry_request is not None:
            target_frames = [
                frame for frame in slot.frames if frame_result_key(frame) == retry_request.frame_key
            ]

        for frame in target_frames:
            emit_frame_started(
                generation_id=generation_id,
                section_id=sid,
                slot=slot,
                frame=frame,
            )
            try:
                if slot.slot_type == SlotType.DIAGRAM_COMPARE:
                    peer_frame = slot.frames[1] if frame.index == 0 else slot.frames[0]
                    frame_result = await _generate_compare_frame(
                        legacy=legacy,
                        slot=slot,
                        frame=frame,
                        peer_frame=peer_frame,
                        section_title=updated_section.header.title,
                        style_context=typed.style_context,
                        sid=sid,
                        generation_id=generation_id,
                        store=store,
                        client=client,
                        api_key_present=api_key_present,
                    )
                elif slot.slot_type == SlotType.DIAGRAM_SERIES:
                    frame_result = await _generate_series_frame(
                        legacy=legacy,
                        slot=slot,
                        frame=frame,
                        section_title=updated_section.header.title,
                        style_context=typed.style_context,
                        sid=sid,
                        generation_id=generation_id,
                        store=store,
                        client=client,
                        api_key_present=api_key_present,
                    )
                else:
                    frame_result = await _generate_image_frame(
                        legacy=legacy,
                        slot=slot,
                        frame=frame,
                        section_title=updated_section.header.title,
                        style_context=typed.style_context,
                        sid=sid,
                        generation_id=generation_id,
                        store=store,
                        client=client,
                        api_key_present=api_key_present,
                        variant=slot.slot_id,
                    )
                slot_frame_results[frame_result_key(frame)] = frame_result
                emit_frame_ready(
                    generation_id=generation_id,
                    section_id=sid,
                    slot=slot,
                    frame=frame,
                )
            except Exception as exc:
                message = f"Image generation failed for frame {frame.index}: {exc}"
                slot_frame_results[frame_result_key(frame)] = VisualFrameResult(
                    slot_id=slot.slot_id,
                    frame_index=frame.index,
                    label=frame.label,
                    render=slot.preferred_render,
                    status=VisualFrameResultStatus.FAILED,
                    error_message=message,
                )
                emit_frame_failed(
                    generation_id=generation_id,
                    section_id=sid,
                    slot=slot,
                    frame=frame,
                    error=message,
                )
                errors.append(
                    PipelineError(
                        node="image_generator",
                        section_id=sid,
                        message=message,
                        recoverable=True,
                    )
                )

        section_frame_results[slot.slot_id] = slot_frame_results
        slot_result = build_slot_result(
            slot,
            slot_frame_results,
            error_message=next(
                (
                    result.error_message
                    for result in slot_frame_results.values()
                    if result.status == VisualFrameResultStatus.FAILED
                ),
                None,
            ),
        )
        section_slot_results[slot.slot_id] = slot_result
        updated_section = apply_slot_results_to_section(
            updated_section,
            slot,
            slot_frame_results,
            fallback_diagram=updated_section.diagram,
        )
        emit_slot_state(
            generation_id=generation_id,
            section_id=sid,
            slot=slot,
            ready_frames=slot_result.completed_frames,
            total_frames=slot_result.total_frames,
            error=slot_result.error_message,
        )

    lifecycle = "generated" if all(result.ready for result in section_slot_results.values()) else "partial"
    if errors and not any(result.ready for result in section_slot_results.values()):
        legacy._publish_image_outcome(generation_id, sid, "error", error_message=errors[0].message)
        outcomes = legacy._with_outcome(typed, sid, "error")["diagram_outcomes"]
    else:
        legacy._publish_image_outcome(generation_id, sid, "success")
        outcomes = legacy._with_outcome(typed, sid, "success")["diagram_outcomes"]

    output = {
        "generated_sections": {sid: updated_section},
        "media_slot_results": {sid: section_slot_results},
        "media_frame_results": {sid: section_frame_results},
        "media_lifecycle": {sid: lifecycle},
        "diagram_outcomes": outcomes,
        "completed_nodes": ["image_generator"],
    }
    if errors:
        output["errors"] = errors
    return output
