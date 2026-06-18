"""
diagram_generator node -- generates structured diagram specs and SVG surfaces.

Reads:
    current_section_id, generated_sections, style_context, contract, composition_plans
Writes:
    generated_sections[current_section_id], diagram_outcomes, completed_nodes, errors
"""

from __future__ import annotations

import asyncio
import json
import logging
from html import escape

from core.config import settings as app_settings
from core.llm.logging import NodeLogger
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from pipeline.console_diagnostics import force_console_log
from pipeline.events import DiagramOutcomeEvent
from pipeline.llm_runner import run_llm
from pipeline.media.assembly import capture_static_slot_results
from pipeline.media.planner.media_planner import find_slot
from pipeline.media.prompts.diagram_prompts import (
    build_diagram_system_prompt,
    build_diagram_user_prompt,
)
from pipeline.media.slot_state import section_level_visual_slots, visual_mode
from pipeline.media.types import SlotType, VisualFrame, VisualSlot
from pipeline.providers.registry import get_node_text_model
from pipeline.runtime_context import retry_policy_for_node, timeout_policy_from_config
from pipeline.runtime_diagnostics import publish_runtime_event
from pipeline.types.requests import needs_diagram_from_placements
from pipeline.runtime_policy import resolve_runtime_policy_bundle
from pipeline.state import PipelineError, TextbookPipelineState
from pipeline.types.section_content import (
    DiagramCompareContent,
    DiagramContent,
    DiagramSeriesContent,
    DiagramSeriesStep,
)

logger = logging.getLogger(__name__)

_SVG_WIDTH = 600
_SVG_HEIGHT = 400
_SVG_BG = "#f8fbff"
_SVG_STROKE = "#1e3a5f"
_SVG_MUTED = "#64748b"
_SVG_FILL = "#ffffff"
_SVG_EMPHASIS_FILL = "#e6f0ff"
_SVG_LABEL = "#12263a"


class DiagramOutput(BaseModel):
    spec: DiagramSpec
    caption: str
    alt_text: str


class DiagramElement(BaseModel):
    id: str
    label: str
    x: float
    y: float
    width: float = 120
    height: float = 60
    shape: str = "rounded-rect"
    emphasis: bool = False


class DiagramConnection(BaseModel):
    from_id: str
    to_id: str
    label: str | None = None
    style: str = "arrow"


class DiagramSpec(BaseModel):
    type: str
    title: str
    elements: list[DiagramElement]
    connections: list[DiagramConnection] = Field(default_factory=list)
    layout_hint: str = "horizontal"


def _log_diagram_event(level: int, event: str, **payload) -> None:
    logger.log(
        level,
        "DIAG::%s::%s",
        event,
        json.dumps(payload, sort_keys=True, default=str),
    )


def _get_supported_targets(state: TextbookPipelineState) -> list[str]:
    media_plan = state.media_plans.get(state.current_section_id)
    return [slot.slot_type.value for slot in section_level_visual_slots(media_plan)]


def _slot_target_ready(section, slot: VisualSlot | None) -> bool:
    if slot is None:
        return False
    _, slot_result = capture_static_slot_results(section, slot)
    return slot_result.ready


def _publish_outcome(generation_id: str, section_id: str | None, outcome: str) -> None:
    if section_id is None:
        return
    publish_runtime_event(
        generation_id,
        DiagramOutcomeEvent(
            generation_id=generation_id,
            section_id=section_id,
            outcome=outcome,
        ),
    )


def _with_outcome(
    outcomes: dict[str, str],
    *,
    generation_id: str,
    section_id: str | None,
    outcome: str,
) -> dict[str, str]:
    if section_id is None:
        return outcomes

    updated = dict(outcomes)
    updated[section_id] = outcome
    _publish_outcome(generation_id, section_id, outcome)
    return updated


def _wrap_label(label: str, *, max_chars: int = 18) -> list[str]:
    words = label.split()
    if not words:
        return [label]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        lines.append(current)
        current = word
    lines.append(current)
    return lines[:3]


def _element_center(element: DiagramElement) -> tuple[float, float]:
    return (element.x + (element.width / 2), element.y + (element.height / 2))


def _render_connection(connection, elements_by_id: dict[str, DiagramElement], index: int) -> str:
    source = elements_by_id.get(connection.from_id)
    target = elements_by_id.get(connection.to_id)
    if source is None or target is None:
        return ""
    x1, y1 = _element_center(source)
    x2, y2 = _element_center(target)
    dasharray = ' stroke-dasharray="8 6"' if connection.style == "dashed" else ""
    marker = ' marker-end="url(#arrowhead)"' if connection.style == "arrow" else ""
    label_markup = ""
    if connection.label:
        label_markup = (
            f'<text x="{(x1 + x2) / 2:.1f}" y="{((y1 + y2) / 2) - 6:.1f}" '
            f'font-size="12" fill="{_SVG_MUTED}" text-anchor="middle" '
            f'font-family="Arial, Helvetica, sans-serif">{escape(connection.label)}</text>'
        )
    return (
        f'<line id="connection-{index}" x1="{x1:.1f}" y1="{y1:.1f}" '
        f'x2="{x2:.1f}" y2="{y2:.1f}" stroke="{_SVG_MUTED}" stroke-width="2"{dasharray}{marker}/>'
        f"{label_markup}"
    )


def _render_element_shape(element: DiagramElement) -> str:
    stroke_width = 3 if element.emphasis else 2
    fill = _SVG_EMPHASIS_FILL if element.emphasis else _SVG_FILL
    if element.shape == "circle":
        cx, cy = _element_center(element)
        radius = min(element.width, element.height) / 2
        return (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
            f'fill="{fill}" stroke="{_SVG_STROKE}" stroke-width="{stroke_width}"/>'
        )
    if element.shape == "diamond":
        cx, cy = _element_center(element)
        points = " ".join(
            [
                f"{cx:.1f},{element.y:.1f}",
                f"{element.x + element.width:.1f},{cy:.1f}",
                f"{cx:.1f},{element.y + element.height:.1f}",
                f"{element.x:.1f},{cy:.1f}",
            ]
        )
        return (
            f'<polygon points="{points}" fill="{fill}" stroke="{_SVG_STROKE}" '
            f'stroke-width="{stroke_width}"/>'
        )
    rx = 12 if element.shape == "rounded-rect" else 0
    return (
        f'<rect x="{element.x:.1f}" y="{element.y:.1f}" width="{element.width:.1f}" '
        f'height="{element.height:.1f}" rx="{rx}" fill="{fill}" '
        f'stroke="{_SVG_STROKE}" stroke-width="{stroke_width}"/>'
    )


def _render_element_label(element: DiagramElement) -> str:
    lines = _wrap_label(element.label)
    cx, cy = _element_center(element)
    first_y = cy - ((len(lines) - 1) * 9)
    tspans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else "18"
        tspans.append(
            f'<tspan x="{cx:.1f}" dy="{dy}">{escape(line)}</tspan>'
        )
    return (
        f'<text x="{cx:.1f}" y="{first_y:.1f}" text-anchor="middle" '
        f'font-size="14" font-weight="600" fill="{_SVG_LABEL}" '
        'font-family="Arial, Helvetica, sans-serif">'
        f'{"".join(tspans)}</text>'
    )


def _render_spec_svg(spec: DiagramSpec) -> str:
    elements_by_id = {element.id: element for element in spec.elements}
    connections = "".join(
        _render_connection(connection, elements_by_id, index)
        for index, connection in enumerate(spec.connections)
    )
    elements = "".join(
        f"{_render_element_shape(element)}{_render_element_label(element)}"
        for element in spec.elements
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_WIDTH} {_SVG_HEIGHT}" '
        f'role="img" aria-label="{escape(spec.title)}">'
        "<defs>"
        '<marker id="arrowhead" markerWidth="10" markerHeight="7" refX="8" refY="3.5" orient="auto">'
        f'<polygon points="0 0, 10 3.5, 0 7" fill="{_SVG_MUTED}"/>'
        "</marker>"
        "</defs>"
        f'<rect x="0" y="0" width="{_SVG_WIDTH}" height="{_SVG_HEIGHT}" rx="18" fill="{_SVG_BG}"/>'
        f'<text x="{_SVG_WIDTH / 2:.1f}" y="28" text-anchor="middle" font-size="18" font-weight="700" '
        f'fill="{_SVG_LABEL}" font-family="Arial, Helvetica, sans-serif">{escape(spec.title)}</text>'
        f"{connections}{elements}"
        "</svg>"
    )


async def _generate_diagram_output(
    state: TextbookPipelineState,
    *,
    slot: VisualSlot,
    frame: VisualFrame,
    section_title: str,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> DiagramOutput:
    model = get_node_text_model(
        "diagram_generator",
        model_overrides=model_overrides,
        generation_mode=state.request.mode,
    )
    agent = Agent(
        model=model,
        output_type=DiagramOutput,
        system_prompt=build_diagram_system_prompt(state.style_context, sizing=slot.sizing),
    )
    timeout_policy = timeout_policy_from_config(config)
    retry_policy = retry_policy_for_node(config, "diagram_generator")
    if timeout_policy is None or retry_policy is None:
        policy = resolve_runtime_policy_bundle(app_settings, state.request.mode)
        timeout_policy = timeout_policy or policy.timeouts
        retry_policy = retry_policy or policy.retries.for_node("diagram_generator")

    result = await asyncio.wait_for(
        run_llm(
            generation_id=state.request.generation_id or "",
            node="diagram_generator",
            agent=agent,
            model=model,
            user_prompt=build_diagram_user_prompt(
                section_title=section_title,
                slot=slot,
                frame=frame,
            ),
            generation_mode=state.request.mode,
            retry_policy=retry_policy,
        ),
        timeout=timeout_policy.diagram_node_budget_seconds,
    )
    return result.output


def _diagram_defaults(section, output: DiagramOutput) -> DiagramContent:
    existing = section.diagram
    if existing is not None:
        return existing.model_copy(
            update={
                "svg_content": _render_spec_svg(output.spec),
                "caption": output.caption,
                "alt_text": output.alt_text,
            }
        )
    return DiagramContent(
        svg_content=_render_spec_svg(output.spec),
        caption=output.caption,
        alt_text=output.alt_text,
    )


def _series_seed_steps(section, composition_plan) -> list[DiagramSeriesStep]:
    existing_series = section.diagram_series
    if existing_series is not None and existing_series.diagrams:
        return [
            step if isinstance(step, DiagramSeriesStep) else DiagramSeriesStep.model_validate(step)
            for step in existing_series.diagrams
        ]

    labels = composition_plan.diagram.key_concepts[:] or [section.header.title]
    step_count = max(len(labels), 3)
    steps: list[DiagramSeriesStep] = []
    for index in range(step_count):
        label = labels[index] if index < len(labels) else f"Stage {index + 1}"
        steps.append(
            DiagramSeriesStep(
                step_label=label,
                caption=f"{section.header.title} - {label}",
            )
        )
    return steps


def _seed_compare_content(section, composition_plan) -> DiagramCompareContent:
    if section.diagram_compare is not None:
        return section.diagram_compare
    before_label = composition_plan.diagram.compare_before_label or "Before"
    after_label = composition_plan.diagram.compare_after_label or "After"
    return DiagramCompareContent(
        before_label=before_label,
        after_label=after_label,
        caption=f"Before and after comparison for {section.header.title}",
        alt_text=f"Before and after comparison illustrating changes in {section.header.title}.",
    )


async def _write_single_diagram(
    state: TextbookPipelineState,
    section,
    plan,
    media_slot: VisualSlot | None,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
):
    slot = media_slot or VisualSlot(
        slot_id="diagram",
        slot_type=SlotType.DIAGRAM,
        required=True,
        preferred_render="svg",
        pedagogical_intent=plan.diagram.visual_guidance or section.header.title,
        caption=section.diagram.caption if section.diagram is not None else f"Visual explanation for {section.header.title}.",
        frames=[
            VisualFrame(
                slot_id="diagram",
                index=0,
                label=section.header.title,
                generation_goal=f"Show the core idea of {section.header.title}.",
                must_include=plan.diagram.key_concepts or [],
                avoid=["text overlays"],
            )
        ],
    )
    frame = slot.frames[0]
    output = await _generate_diagram_output(
        state,
        slot=slot,
        frame=frame,
        section_title=section.header.title,
        model_overrides=model_overrides,
        config=config,
    )
    return section.model_copy(update={"diagram": _diagram_defaults(section, output)})


async def _write_series_diagrams(
    state: TextbookPipelineState,
    section,
    plan,
    media_slot: VisualSlot | None,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
):
    seed_steps = _series_seed_steps(section, plan)
    key_concepts = plan.diagram.key_concepts or []
    rendered_steps: list[DiagramSeriesStep] = []
    slot = media_slot or VisualSlot(
        slot_id="diagram_series",
        slot_type=SlotType.DIAGRAM_SERIES,
        required=True,
        preferred_render="svg",
        pedagogical_intent=plan.diagram.visual_guidance or section.header.title,
        caption=section.diagram_series.title if section.diagram_series is not None else section.header.title,
        frames=[
            VisualFrame(
                slot_id="diagram_series",
                index=index,
                label=step.step_label,
                generation_goal=f"Show sequence step {index + 1} for {section.header.title}.",
                must_include=[step.step_label],
                avoid=["text overlays"],
            )
            for index, step in enumerate(seed_steps)
        ],
    )

    for index, step in enumerate(seed_steps):
        if (step.svg_content or "").strip():
            rendered_steps.append(step)
            continue

        frame = slot.frames[index] if index < len(slot.frames) else VisualFrame(
            slot_id=slot.slot_id,
            index=index,
            label=step.step_label,
            generation_goal=f"Show sequence step {index + 1} for {section.header.title}.",
            must_include=[key_concepts[index] if index < len(key_concepts) else step.step_label],
            avoid=["text overlays"],
        )

        output = await _generate_diagram_output(
            state,
            slot=slot,
            frame=frame,
            section_title=section.header.title,
            model_overrides=model_overrides,
            config=config,
        )
        rendered_steps.append(
            step.model_copy(
                update={
                    "caption": step.caption or output.caption,
                    "svg_content": _render_spec_svg(output.spec),
                }
            )
        )

    title = section.diagram_series.title if section.diagram_series is not None else section.header.title
    return section.model_copy(
        update={"diagram_series": DiagramSeriesContent(title=title, diagrams=rendered_steps)}
    )


async def _write_compare_diagrams(
    state: TextbookPipelineState,
    section,
    plan,
    media_slot: VisualSlot | None,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
):
    compare_content = _seed_compare_content(section, plan)
    before_svg = compare_content.before_svg
    after_svg = compare_content.after_svg
    slot = media_slot or VisualSlot(
        slot_id="diagram_compare",
        slot_type=SlotType.DIAGRAM_COMPARE,
        required=True,
        preferred_render="svg",
        pedagogical_intent=plan.diagram.visual_guidance or section.header.title,
        caption=compare_content.caption,
        frames=[
            VisualFrame(
                slot_id="diagram_compare",
                index=0,
                label=compare_content.before_label,
                generation_goal=f"Render the BEFORE state for {section.header.title}.",
                must_include=[compare_content.before_label],
                avoid=["text overlays"],
            ),
            VisualFrame(
                slot_id="diagram_compare",
                index=1,
                label=compare_content.after_label,
                generation_goal=f"Render the AFTER state for {section.header.title}.",
                must_include=[compare_content.after_label],
                avoid=["text overlays"],
            ),
        ],
    )

    if not (before_svg or "").strip():
        before_frame = slot.frames[0]
        before_output = await _generate_diagram_output(
            state,
            slot=slot,
            frame=before_frame,
            section_title=section.header.title,
            model_overrides=model_overrides,
            config=config,
        )
        before_svg = _render_spec_svg(before_output.spec)

    if not (after_svg or "").strip():
        after_frame = slot.frames[1]
        after_output = await _generate_diagram_output(
            state,
            slot=slot,
            frame=after_frame,
            section_title=section.header.title,
            model_overrides=model_overrides,
            config=config,
        )
        after_svg = _render_spec_svg(after_output.spec)

    return section.model_copy(
        update={
            "diagram_compare": compare_content.model_copy(
                update={
                    "before_svg": before_svg,
                    "after_svg": after_svg,
                }
            )
        }
    )


async def _run_diagram_generation(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    state = TextbookPipelineState.parse(state)
    sid = state.current_section_id
    _ = NodeLogger(
        generation_id=state.request.generation_id or "",
        section_id=sid,
        node_name="diagram_generator",
    )
    outcomes = dict(state.diagram_outcomes)
    plan = state.composition_plans.get(sid)
    targets = _get_supported_targets(state)
    mode = visual_mode(state.media_plans.get(sid))
    force_console_log(
        "VISUAL_RESOLVE",
        "DIAGRAM_GENERATOR",
        section_id=sid,
        mode=mode,
        targets=targets,
    )
    _log_diagram_event(
        logging.INFO,
        "GENERATOR_START",
        section_id=sid,
        mode=mode,
        targets=targets,
        plan_exists=plan is not None,
        enabled=plan.diagram.enabled if plan is not None else None,
    )

    if not targets:
        _log_diagram_event(logging.INFO, "GENERATOR_SKIP_NO_SLOT", section_id=sid)
        outcomes = _with_outcome(
            outcomes,
            generation_id=state.request.generation_id or "",
            section_id=sid,
            outcome="skipped",
        )
        return {"diagram_outcomes": outcomes, "completed_nodes": ["diagram_generator"]}

    if mode == "image":
        _log_diagram_event(
            logging.INFO,
            "GENERATOR_SKIP_MODE",
            section_id=sid,
            mode=mode,
        )
        outcomes = _with_outcome(
            outcomes,
            generation_id=state.request.generation_id or "",
            section_id=sid,
            outcome="skipped",
        )
        return {"diagram_outcomes": outcomes, "completed_nodes": ["diagram_generator"]}

    section = state.generated_sections.get(sid)
    if sid is None or section is None:
        _log_diagram_event(
            logging.INFO,
            "GENERATOR_SKIP_NO_SECTION",
            section_id=sid,
            available_sections=list(state.generated_sections.keys()),
        )
        return {"diagram_outcomes": outcomes, "completed_nodes": ["diagram_generator"]}

    if plan is not None and not plan.diagram.enabled:
        _log_diagram_event(logging.INFO, "GENERATOR_SKIP_NOT_ENABLED", section_id=sid)
        outcomes = _with_outcome(
            outcomes,
            generation_id=state.request.generation_id or "",
            section_id=sid,
            outcome="skipped",
        )
        return {"diagram_outcomes": outcomes, "completed_nodes": ["diagram_generator"]}

    if plan is None and state.current_section_plan and not needs_diagram_from_placements(
        state.current_section_plan
    ):
        _log_diagram_event(logging.INFO, "GENERATOR_SKIP_PLAN", section_id=sid)
        outcomes = _with_outcome(
            outcomes,
            generation_id=state.request.generation_id or "",
            section_id=sid,
            outcome="skipped",
        )
        return {"diagram_outcomes": outcomes, "completed_nodes": ["diagram_generator"]}

    if state.style_context is None:
        _log_diagram_event(
            logging.ERROR,
            "GENERATOR_FAILURE",
            section_id=sid,
            reason="no_style_context",
        )
        outcomes = _with_outcome(
            outcomes,
            generation_id=state.request.generation_id or "",
            section_id=sid,
            outcome="error",
        )
        return {
            "errors": [
                PipelineError(
                    node="diagram_generator",
                    section_id=sid,
                    message="style_context is None -- curriculum_planner may have failed",
                    recoverable=False,
                )
            ],
            "diagram_outcomes": outcomes,
            "completed_nodes": ["diagram_generator"],
        }
    try:
        updated_section = section
        media_plan = state.media_plans.get(sid) if sid is not None else None
        for target in targets:
            slot = find_slot(media_plan, SlotType(target))
            if _slot_target_ready(updated_section, slot):
                force_console_log(
                    "VISUAL_RESOLVE",
                    "SVG_TARGET_SKIPPED",
                    section_id=sid,
                    target=target,
                    reason="already_satisfied",
                )
                continue

            force_console_log(
                "VISUAL_RESOLVE",
                "SVG_WRITEBACK",
                section_id=sid,
                target=target,
                status="starting",
            )
            if target == "diagram":
                updated_section = await _write_single_diagram(
                    state,
                    updated_section,
                    plan,
                    slot,
                    model_overrides=model_overrides,
                    config=config,
                )
            elif target == "diagram_series":
                updated_section = await _write_series_diagrams(
                    state,
                    updated_section,
                    plan,
                    slot,
                    model_overrides=model_overrides,
                    config=config,
                )
            elif target == "diagram_compare":
                updated_section = await _write_compare_diagrams(
                    state,
                    updated_section,
                    plan,
                    slot,
                    model_overrides=model_overrides,
                    config=config,
                )
            force_console_log(
                "VISUAL_RESOLVE",
                "SVG_WRITEBACK",
                section_id=sid,
                target=target,
                status="completed",
                satisfied=_slot_target_ready(updated_section, slot),
            )

        outcomes = _with_outcome(
            outcomes,
            generation_id=state.request.generation_id or "",
            section_id=sid,
            outcome="success",
        )
        _log_diagram_event(logging.INFO, "GENERATOR_SUCCESS", section_id=sid, targets=targets)
        return {
            "generated_sections": {sid: updated_section},
            "diagram_outcomes": outcomes,
            "completed_nodes": ["diagram_generator"],
        }
    except asyncio.TimeoutError:
        timeout_policy = timeout_policy_from_config(config)
        if timeout_policy is None:
            timeout_policy = resolve_runtime_policy_bundle(app_settings, state.request.mode).timeouts
        outcomes = _with_outcome(
            outcomes,
            generation_id=state.request.generation_id or "",
            section_id=sid,
            outcome="timeout",
        )
        _log_diagram_event(
            logging.ERROR,
            "GENERATOR_TIMEOUT",
            section_id=sid,
            timeout_seconds=int(timeout_policy.diagram_node_budget_seconds),
        )
        return {
            "errors": [
                PipelineError(
                    node="diagram_generator",
                    section_id=sid,
                    message=(
                        f"Diagram generation timed out ({int(timeout_policy.diagram_node_budget_seconds)}s) "
                        "and the section will ship without a diagram."
                    ),
                    recoverable=True,
                )
            ],
            "diagram_outcomes": outcomes,
            "completed_nodes": ["diagram_generator"],
        }
    except Exception as exc:
        outcomes = _with_outcome(
            outcomes,
            generation_id=state.request.generation_id or "",
            section_id=sid,
            outcome="error",
        )
        _log_diagram_event(
            logging.ERROR,
            "GENERATOR_FAILURE",
            section_id=sid,
            error_type=type(exc).__name__,
            error_message=str(exc)[:500],
        )
        return {
            "errors": [
                PipelineError(
                    node="diagram_generator",
                    section_id=sid,
                    message=f"Diagram generation failed: {exc}",
                    recoverable=True,
                )
            ],
            "diagram_outcomes": outcomes,
            "completed_nodes": ["diagram_generator"],
        }


async def diagram_generator(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    from pipeline.media.executors.diagram_generator import diagram_generator as execute_diagram_generator

    return await execute_diagram_generator(
        state,
        model_overrides=model_overrides,
        config=config,
    )
