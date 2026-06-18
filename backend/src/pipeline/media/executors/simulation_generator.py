from __future__ import annotations

import asyncio
from dataclasses import dataclass

import core.events as core_events
from pydantic_ai import Agent

from core.config import settings
from pipeline.events import InteractionOutcomeEvent, SimulationTypeSelectedEvent
from pipeline.llm_runner import run_llm
from pipeline.media.assembly import apply_slot_results_to_section, build_slot_result
from pipeline.media.planner.media_planner import find_slot
from pipeline.media.prompts.simulation_prompts import (
    _SIMULATION_SYSTEM_PROMPT,
    build_simulation_prompt,
)
from pipeline.media.qc.simulation_qc import validate_simulation_content
from pipeline.media.runtime_events import (
    emit_frame_failed,
    emit_frame_ready,
    emit_frame_started,
    emit_slot_state,
)
from pipeline.media.types import SlotType, VisualFrameResult, VisualFrameResultStatus
from pipeline.providers.registry import get_node_text_model
from pipeline.state import PipelineError, TextbookPipelineState
from pipeline.types.section_content import (
    InteractionContext,
    InteractionDimensions,
    InteractionSpec,
    SimulationContent,
)


@dataclass(slots=True)
class ParsedSimulationOutput:
    html_content: str
    simulation_type: str
    goal: str
    explanation: str | None


def _publish_interaction_outcome(
    generation_id: str,
    section_id: str | None,
    outcome: str,
    *,
    skip_reason: str | None = None,
    interaction_count: int = 0,
) -> None:
    if not generation_id or not section_id:
        return
    core_events.event_bus.publish(
        generation_id,
        InteractionOutcomeEvent(
            generation_id=generation_id,
            section_id=section_id,
            outcome=outcome,
            skip_reason=skip_reason,
            interaction_count=interaction_count,
        ),
    )


def _resolve_colors(state: TextbookPipelineState) -> tuple[str, str]:
    palette = (state.style_context.palette if state.style_context is not None else "").lower()
    if "navy" in palette:
        return "#17417a", "#f7fbff"
    if "green" in palette:
        return "#166534", "#f6fff9"
    return "#1f3b6b", "#fbfcfe"


def build_interaction_spec(
    state: TextbookPipelineState,
    section,
    slot,
    *,
    simulation_type: str | None = None,
    simulation_goal: str | None = None,
) -> InteractionSpec:
    accent_color, surface_color = _resolve_colors(state)
    learner_level = getattr(state.current_section_plan, "interaction_policy", "allowed")
    return InteractionSpec(
        type=simulation_type or slot.simulation_type or "graph_slider",
        goal=simulation_goal or slot.simulation_goal or slot.simulation_intent or slot.pedagogical_intent,
        anchor_content={
            "headline": section.hook.headline,
            "body": section.explanation.body[:280],
            "anchor_block": slot.anchor_block or "explanation",
        },
        context=InteractionContext(
            learner_level=learner_level,
            template_id=state.contract.id,
            color_mode="light",
            accent_color=accent_color,
            surface_color=surface_color,
            font_mono="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        ),
        dimensions=InteractionDimensions(
            width="100%",
            height=420,
            resizable=True,
        ),
        print_translation=slot.print_translation or "static_diagram",
    )


def _strip_wrapping_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if not lines:
        return stripped
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_simulation_output(raw_output: str, *, slot) -> ParsedSimulationOutput:
    stripped = raw_output.strip()
    html_part = stripped
    meta_part = ""
    if "SIMULATION_META:" in stripped:
        html_part, meta_part = stripped.split("SIMULATION_META:", 1)

    metadata: dict[str, str] = {}
    for line in meta_part.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip()

    html_content = _strip_wrapping_code_fence(html_part)
    return ParsedSimulationOutput(
        html_content=html_content,
        simulation_type=metadata.get("type") or slot.simulation_type or "graph_slider",
        goal=metadata.get("goal") or slot.simulation_goal or slot.simulation_intent or slot.pedagogical_intent,
        explanation=metadata.get("explanation") or None,
    )


async def _generate_simulation_markup(
    state: TextbookPipelineState,
    *,
    section,
    slot,
    frame,
    model_overrides: dict | None = None,
) -> tuple[InteractionSpec, str, str]:
    model = get_node_text_model(
        "interaction_generator",
        model_overrides=model_overrides,
        generation_mode=state.request.mode,
    )
    agent = Agent(
        model=model,
        output_type=str,
        system_prompt=_SIMULATION_SYSTEM_PROMPT,
    )
    result = await asyncio.wait_for(
        run_llm(
            generation_id=state.request.generation_id or "",
            node="interaction_generator",
            agent=agent,
            model=model,
            section_id=state.current_section_id,
            generation_mode=state.request.mode,
            user_prompt=build_simulation_prompt(
                section_title=section.header.title,
                slot=slot,
                frame=frame,
            ),
        ),
        timeout=settings.pipeline_timeout_interaction_seconds,
    )
    output = result.output if hasattr(result, "output") else result
    if not isinstance(output, str):
        raise ValueError("Simulation generator expected string HTML output.")

    parsed = _parse_simulation_output(output, slot=slot)
    generation_id = state.request.generation_id or ""
    section_id = state.current_section_id or ""
    if generation_id and section_id:
        core_events.event_bus.publish(
            generation_id,
            SimulationTypeSelectedEvent(
                generation_id=generation_id,
                section_id=section_id,
                simulation_type=parsed.simulation_type,
                simulation_goal=parsed.goal,
            ),
        )
    spec = build_interaction_spec(
        state,
        section,
        slot,
        simulation_type=parsed.simulation_type,
        simulation_goal=parsed.goal,
    )
    explanation = parsed.explanation or (
        f"Interactive view for {section.header.title}. "
        f"Use it to explore {spec.goal.lower()} step by step."
    )
    return spec, parsed.html_content, explanation


def _failed_interaction_response(
    *,
    generation_id: str,
    sid: str,
    slot,
    frame,
    message: str,
) -> dict:
    frame_result = VisualFrameResult(
        slot_id=slot.slot_id,
        frame_index=frame.index,
        label=frame.label,
        render=slot.preferred_render,
        status=VisualFrameResultStatus.FAILED,
        error_message=message,
    )
    frame_results = {str(frame.index): frame_result}
    slot_result = build_slot_result(slot, frame_results, error_message=message)
    emit_frame_failed(
        generation_id=generation_id,
        section_id=sid,
        slot=slot,
        frame=frame,
        error=message,
    )
    emit_slot_state(
        generation_id=generation_id,
        section_id=sid,
        slot=slot,
        ready_frames=slot_result.completed_frames,
        total_frames=slot_result.total_frames,
        error=slot_result.error_message,
    )
    return {
        "errors": [
            PipelineError(
                node="interaction_generator",
                section_id=sid,
                message=message,
                recoverable=True,
            )
        ],
        "media_frame_results": {sid: {slot.slot_id: frame_results}},
        "media_slot_results": {sid: {slot.slot_id: slot_result}},
        "media_lifecycle": {sid: "failed"},
        "completed_nodes": ["interaction_generator"],
    }


async def simulation_generator(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
) -> dict:
    typed = TextbookPipelineState.parse(state)
    sid = typed.current_section_id
    section = typed.generated_sections.get(sid)
    generation_id = typed.request.generation_id or ""

    if sid is None or section is None:
        return {"completed_nodes": ["interaction_generator"]}

    has_contract_slot = "simulation-block" in (
        set(typed.contract.required_components)
        | set(typed.contract.optional_components)
        | set(getattr(typed.contract, "contextually_present", []) or [])
    )
    if not has_contract_slot:
        _publish_interaction_outcome(generation_id, sid, "skipped", skip_reason="no_slot")
        return {"completed_nodes": ["interaction_generator"]}

    media_plan = typed.media_plans.get(sid)
    slot = find_slot(media_plan, SlotType.SIMULATION)
    if slot is None:
        _publish_interaction_outcome(generation_id, sid, "skipped", skip_reason="no_plan")
        return {"completed_nodes": ["interaction_generator"]}

    if typed.current_section_plan is not None and typed.current_section_plan.interaction_policy == "disabled":
        _publish_interaction_outcome(generation_id, sid, "skipped", skip_reason="policy_disabled")
        return {"completed_nodes": ["interaction_generator"]}

    if typed.contract.interaction_level not in {"medium", "high"}:
        _publish_interaction_outcome(
            generation_id,
            sid,
            "skipped",
            skip_reason="low_interaction_level",
        )
        return {"completed_nodes": ["interaction_generator"]}

    frame = slot.frames[0]
    emit_frame_started(
        generation_id=generation_id,
        section_id=sid,
        slot=slot,
        frame=frame,
    )

    try:
        spec, html_content, explanation = await _generate_simulation_markup(
            typed,
            section=section,
            slot=slot,
            frame=frame,
            model_overrides=model_overrides,
        )
    except Exception as exc:
        return _failed_interaction_response(
            generation_id=generation_id,
            sid=sid,
            slot=slot,
            frame=frame,
            message=f"Simulation generation failed: {exc}",
        )

    frame_result = VisualFrameResult(
        slot_id=slot.slot_id,
        frame_index=frame.index,
        label=frame.label,
        render=slot.preferred_render,
        status=VisualFrameResultStatus.GENERATED,
        html_content=html_content,
        interaction_spec=spec,
        explanation=explanation,
    )
    frame_results = {str(frame.index): frame_result}
    slot_result = build_slot_result(slot, frame_results)
    preview_section = apply_slot_results_to_section(
        section,
        slot,
        frame_results,
        fallback_diagram=section.diagram,
    )
    preview_simulation = preview_section.simulation or SimulationContent(
        spec=spec,
        html_content=html_content,
        explanation=frame_result.explanation,
    )
    qc_issues = validate_simulation_content(
        slot=slot,
        simulation=preview_simulation,
        fallback_diagram=preview_simulation.fallback_diagram,
    )
    if qc_issues:
        return _failed_interaction_response(
            generation_id=generation_id,
            sid=sid,
            slot=slot,
            frame=frame,
            message=f"Simulation QC failed: {'; '.join(qc_issues)}",
        )

    emit_frame_ready(
        generation_id=generation_id,
        section_id=sid,
        slot=slot,
        frame=frame,
    )
    emit_slot_state(
        generation_id=generation_id,
        section_id=sid,
        slot=slot,
        ready_frames=slot_result.completed_frames,
        total_frames=slot_result.total_frames,
        error=slot_result.error_message,
    )
    _publish_interaction_outcome(generation_id, sid, "generated", interaction_count=1)
    return {
        "generated_sections": {sid: preview_section},
        "interaction_specs": {sid: spec},
        "media_frame_results": {sid: {slot.slot_id: frame_results}},
        "media_slot_results": {sid: {slot.slot_id: slot_result}},
        "media_lifecycle": {sid: "generated"},
        "completed_nodes": ["interaction_generator"],
    }


__all__ = [
    "ParsedSimulationOutput",
    "_parse_simulation_output",
    "build_interaction_spec",
    "simulation_generator",
]
