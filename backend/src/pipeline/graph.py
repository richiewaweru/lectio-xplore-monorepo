"""
pipeline.graph

The LangGraph generation graph. Curriculum planner fans out into
per-section execution through process_section.

After process_section/retry nodes, route_after_qc decides whether to rerender or finish.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.types import Send

from pipeline.events import (
    SectionMediaBlockedEvent,
    NodeFinishedEvent,
    NodeStartedEvent,
)
from pipeline.nodes.curriculum_planner import curriculum_planner
from pipeline.nodes.diagram_generator import diagram_generator
from pipeline.nodes.field_regenerator import field_regenerator
from pipeline.nodes.image_generator import image_generator
from pipeline.nodes.interaction_generator import interaction_generator
from pipeline.nodes.media_planner import media_planner
from pipeline.nodes.process_section import process_section
from pipeline.nodes.qc_agent import qc_agent
from pipeline.nodes.section_assembler import section_assembler
from pipeline.nodes.section_runner import run_section_steps
from pipeline.media.retry import blocked_required_media, next_retry_request
from pipeline.routers.qc_router import route_after_qc
from pipeline.runtime_context import get_runtime_context
from pipeline.runtime_diagnostics import (
    generation_id_from_state,
    next_node_attempt,
    node_error_messages,
    publish_runtime_event,
)
from pipeline.state import FailedSectionRecord, NodeFailureDetail, TextbookPipelineState, merge_state_updates
from pipeline.types.requests import count_visual_placements, needs_diagram_from_placements


def _normalize_langgraph_config_signature(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Force the config annotation to resolve to the runtime type LangGraph expects."""
    signature = inspect.signature(fn)
    config = signature.parameters.get("config")
    expected = RunnableConfig | None

    if config is None or config.annotation == expected:
        return fn

    fn.__signature__ = signature.replace(
        parameters=[
            parameter.replace(annotation=expected)
            if parameter.name == "config"
            else parameter
            for parameter in signature.parameters.values()
        ]
    )
    return fn


async def _invoke_node(
    fn,
    state,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
):
    kwargs = {"model_overrides": model_overrides}
    if config is not None and "config" in inspect.signature(fn).parameters:
        kwargs["config"] = config
    return await fn(state, **kwargs)


def fan_out_sections(state: TextbookPipelineState | dict) -> list[Send]:
    """Fan out one per-section flow after curriculum_planner."""
    state = TextbookPipelineState.parse(state)
    if not state.curriculum_outline:
        return []

    base = state.model_dump()
    return [
        Send("process_section", {
            **base,
            "current_section_id": plan.section_id,
            "current_section_plan": plan.model_dump(),
        })
        for plan in state.curriculum_outline
    ]


async def _run_generation_node(
    name: str,
    fn,
    state,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
):
    typed = TextbookPipelineState.parse(state)
    generation_id = generation_id_from_state(typed)
    attempt = next_node_attempt(generation_id, name) if generation_id else 1
    started = perf_counter()

    publish_runtime_event(
        generation_id,
        NodeStartedEvent(
            generation_id=generation_id,
            node=name,
            attempt=attempt,
        ),
    )

    try:
        result = await _invoke_node(
            fn,
            state,
            model_overrides=model_overrides,
            config=config,
        )
    except Exception as exc:
        publish_runtime_event(
            generation_id,
            NodeFinishedEvent(
                generation_id=generation_id,
                node=name,
                attempt=attempt,
                status="failed",
                latency_ms=(perf_counter() - started) * 1000.0,
                error=str(exc),
            ),
        )
        raise

    messages = node_error_messages(result.get("errors"), node=name)
    publish_runtime_event(
        generation_id,
        NodeFinishedEvent(
            generation_id=generation_id,
            node=name,
            attempt=attempt,
            status="failed" if messages else "succeeded",
            latency_ms=(perf_counter() - started) * 1000.0,
            error=" | ".join(messages) if messages else None,
        ),
    )

    return result


async def _instrumented_curriculum_planner(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
):
    return await _run_generation_node(
        "curriculum_planner",
        curriculum_planner,
        state,
        model_overrides=model_overrides,
        config=config,
    )


def _media_blocked_updates(
    state: TextbookPipelineState,
    *,
    section_id: str,
    slot_ids: list[str],
    reason: str,
) -> dict:
    plan = state.current_section_plan
    detail = NodeFailureDetail(
        node="retry_media_frame",
        section_id=section_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        error_type="media_blocked",
        error_message=reason,
        retry_attempt=state.rerender_count.get(section_id, 0),
        will_retry=False,
    )
    failed = FailedSectionRecord(
        section_id=section_id,
        title=plan.title if plan is not None else section_id,
        position=plan.position if plan is not None else 0,
        focus=plan.focus if plan is not None else None,
        bridges_from=plan.bridges_from if plan is not None else None,
        bridges_to=plan.bridges_to if plan is not None else None,
        needs_diagram=needs_diagram_from_placements(plan),
        visual_placements_count=count_visual_placements(plan),
        needs_worked_example=plan.needs_worked_example if plan is not None else False,
        failed_at_node="retry_media_frame",
        error_type="media_blocked",
        error_summary=reason,
        attempt_count=state.rerender_count.get(section_id, 0) + 1,
        can_retry=False,
        missing_components=slot_ids,
        failure_detail=detail,
    )
    publish_runtime_event(
        state.request.generation_id or "",
        SectionMediaBlockedEvent(
            generation_id=state.request.generation_id or "",
            section_id=section_id,
            slot_ids=slot_ids,
            reason=reason,
        ),
    )
    return {
        "failed_sections": {section_id: failed},
        "section_lifecycle": {section_id: "failed"},
        "section_pending_assets": {section_id: []},
        "current_media_retry": None,
    }


async def retry_media_frame(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    typed = TextbookPipelineState.parse(state)
    sid = typed.current_section_id
    retry_request = typed.pending_media_retry_for(sid)
    runtime_context = get_runtime_context(config)

    if runtime_context is not None and sid is not None:
        await runtime_context.progress.start_retry(sid)

    try:
        if sid is None or retry_request is None:
            return {"completed_nodes": ["retry_media_frame"], "current_media_retry": None}

        executor_name = retry_request.executor_node
        executor = {
            "diagram_generator": diagram_generator,
            "image_generator": image_generator,
            "interaction_generator": interaction_generator,
        }[executor_name]

        raw_state = typed.model_dump()
        section_counts = {
            slot_id: dict(frame_counts)
            for slot_id, frame_counts in typed.media_frame_retry_count.get(sid, {}).items()
        }
        slot_counts = dict(section_counts.get(retry_request.slot_id, {}))
        slot_counts[retry_request.frame_key] = slot_counts.get(retry_request.frame_key, 0) + 1
        section_counts[retry_request.slot_id] = slot_counts
        raw_state["media_frame_retry_count"] = {
            **typed.media_frame_retry_count,
            sid: section_counts,
        }
        raw_state["media_retry_count"] = {
            **typed.media_retry_count,
            sid: typed.media_retry_count.get(sid, 0) + 1,
        }
        raw_state["current_media_retry"] = retry_request.model_dump()

        result = await run_section_steps(
            raw_state,
            steps=[
                (executor_name, executor),
                ("section_assembler", section_assembler),
                ("qc_agent", qc_agent),
            ],
            model_overrides=model_overrides,
            increment_rerender_count=False,
            config=config,
        )
        merged_state = typed.model_dump()
        merge_state_updates(merged_state, result)
        merged_typed = TextbookPipelineState.parse(merged_state)
        blocked = blocked_required_media(merged_typed, section_id=sid)
        output = dict(result)
        output["media_retry_count"] = {
            sid: raw_state["media_retry_count"][sid],
        }
        output["media_frame_retry_count"] = {
            sid: raw_state["media_frame_retry_count"][sid],
        }
        output["current_media_retry"] = None
        if blocked.blocked:
            merge_state_updates(
                output,
                _media_blocked_updates(
                    merged_typed,
                    section_id=sid,
                    slot_ids=blocked.slot_ids,
                    reason=blocked.reason or "Required media retry budget exhausted.",
                ),
            )
        return output
    finally:
        if runtime_context is not None and sid is not None:
            await runtime_context.progress.finish_retry(sid)


async def retry_diagram(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    typed = TextbookPipelineState.parse(state)
    sid = typed.current_section_id
    if sid is None:
        return {"completed_nodes": ["retry_media_frame"], "current_media_retry": None}
    candidate = next_retry_request(
        typed,
        section_id=sid,
        blocking_issues=[{"block": "diagram", "message": "Compatibility retry"}],
    )
    if candidate is None:
        return {"completed_nodes": ["retry_media_frame"], "current_media_retry": None}
    raw_state = typed.model_dump()
    raw_state["current_media_retry"] = candidate.model_dump()
    return await retry_media_frame(
        raw_state,
        model_overrides=model_overrides,
        config=config,
    )


async def retry_interaction(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    typed = TextbookPipelineState.parse(state)
    sid = typed.current_section_id
    if sid is None:
        return {"completed_nodes": ["retry_media_frame"], "current_media_retry": None}
    candidate = next_retry_request(
        typed,
        section_id=sid,
        blocking_issues=[{"block": "simulation", "message": "Compatibility retry"}],
    )
    if candidate is None:
        return {"completed_nodes": ["retry_media_frame"], "current_media_retry": None}
    raw_state = typed.model_dump()
    raw_state["current_media_retry"] = candidate.model_dump()
    return await retry_media_frame(
        raw_state,
        model_overrides=model_overrides,
        config=config,
    )


async def retry_field(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    """Re-run field_regenerator -> section_assembler -> qc_agent only."""
    typed = TextbookPipelineState.parse(state)
    runtime_context = get_runtime_context(config)
    sid = typed.current_section_id
    if runtime_context is not None and sid is not None:
        await runtime_context.progress.start_retry(sid)
    try:
        return await run_section_steps(
            state,
            steps=[
                ("field_regenerator", field_regenerator),
                ("section_assembler", section_assembler),
                ("qc_agent", qc_agent),
            ],
            model_overrides=model_overrides,
            increment_rerender_count=True,
            config=config,
        )
    finally:
        if runtime_context is not None and sid is not None:
            await runtime_context.progress.finish_retry(sid)

def build_graph(checkpointer=None) -> StateGraph:
    workflow = StateGraph(TextbookPipelineState)

    # Register nodes
    workflow.add_node(
        "curriculum_planner",
        _normalize_langgraph_config_signature(_instrumented_curriculum_planner),
    )
    workflow.add_node(
        "process_section",
        _normalize_langgraph_config_signature(process_section),
    )
    workflow.add_node(
        "media_planner",
        _normalize_langgraph_config_signature(media_planner),
    )
    workflow.add_node(
        "retry_media_frame",
        _normalize_langgraph_config_signature(retry_media_frame),
    )
    workflow.add_node("retry_field", _normalize_langgraph_config_signature(retry_field))

    # Entry point
    workflow.set_entry_point("curriculum_planner")

    # After curriculum_planner: fan out per section
    workflow.add_conditional_edges(
        "curriculum_planner",
        fan_out_sections,
    )

    workflow.add_conditional_edges("process_section", route_after_qc)

    workflow.add_conditional_edges("retry_media_frame", route_after_qc)

    # Field-level retry: regenerate one text field, then re-evaluate.
    workflow.add_conditional_edges("retry_field", route_after_qc)

    return workflow.compile(checkpointer=checkpointer or MemorySaver())
