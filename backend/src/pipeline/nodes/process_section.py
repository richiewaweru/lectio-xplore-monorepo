"""
Graph-visible per-section orchestration.

process_section is now the canonical 4-phase section flow:
    1. content_generator -> schema_validator
    2. media_planner
    3. diagram_generator || image_generator || interaction_generator
    4. section_assembler -> qc_agent

Partial section emission is an inline side effect between phases, not a
separate graph node.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.runnables.config import RunnableConfig

from pipeline.events import (
    MediaPlanReadyEvent,
    SectionAssetPendingEvent,
    SectionAssetReadyEvent,
    SectionFinalEvent,
    SectionPartialEvent,
    SectionReadyEvent,
)
from pipeline.nodes.content_generator import content_generator
from pipeline.nodes.diagram_generator import diagram_generator
from pipeline.nodes.media_planner import media_planner
from pipeline.nodes.image_generator import image_generator
from pipeline.nodes.interaction_generator import interaction_generator
from pipeline.nodes.qc_agent import qc_agent
from pipeline.nodes.schema_validator import schema_validator
from pipeline.nodes.section_assembler import section_assembler
from pipeline.nodes.section_runner import _run_parallel_phase, run_section_steps
from pipeline.runtime_context import get_runtime_context
from pipeline.runtime_diagnostics import publish_runtime_event
from pipeline.media.slot_state import pending_required_slot_ids, visual_mode
from pipeline.state import PartialSectionRecord, TextbookPipelineState, merge_state_updates


async def _run_interaction_path(
    state: TextbookPipelineState,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    _ = config
    return await interaction_generator(
        state,
        model_overrides=model_overrides,
    )


async def _start_section_flow(
    state: TextbookPipelineState,
    *,
    config: RunnableConfig | None = None,
) -> tuple[object | None, bool]:
    runtime_context = get_runtime_context(config)
    section_id = state.current_section_id
    is_retry = section_id is not None and state.pending_rerender_for(section_id) is not None

    if runtime_context is not None and section_id is not None:
        await runtime_context.progress.queue_section(section_id)
        await runtime_context.limiters.section.acquire()
        await runtime_context.progress.start_section(section_id)
        if is_retry:
            await runtime_context.progress.start_retry(section_id)

    return runtime_context, is_retry


async def _finish_section_flow(
    runtime_context,
    *,
    section_id: str | None,
    is_retry: bool,
) -> None:
    if runtime_context is not None and section_id is not None:
        runtime_context.limiters.section.release()
        await runtime_context.progress.finish_section(section_id)
        if is_retry:
            await runtime_context.progress.finish_retry(section_id)


def _merge_phase_outputs(*phases: dict) -> dict:
    output: dict = {}
    for phase in phases:
        merge_state_updates(output, phase)
    return output


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_partial_snapshot(
    state: TextbookPipelineState,
    *,
    status: str,
    pending_assets: list[str] | None = None,
    updated_at: str | None = None,
) -> dict:
    section_id = state.current_section_id
    if section_id is None:
        return {}

    section = state.generated_sections.get(section_id)
    if section is None:
        return {}

    next_pending_assets = list(
        pending_required_slot_ids(state) if pending_assets is None else pending_assets
    )
    lifecycle = "awaiting_assets" if next_pending_assets else status
    timestamp = updated_at or _utc_now_iso()

    return {
        "partial_sections": {
            section_id: PartialSectionRecord(
                section_id=section.section_id,
                template_id=section.template_id,
                content=section,
                status=lifecycle,
                visual_mode=visual_mode(state.media_plans.get(section_id)),
                pending_assets=next_pending_assets,
                updated_at=timestamp,
            )
        },
        "section_pending_assets": {section_id: next_pending_assets},
        "section_lifecycle": {section_id: lifecycle},
    }


async def _emit_partial_snapshot(
    state: TextbookPipelineState,
    *,
    runtime_context,
    status: str,
) -> None:
    section_id = state.current_section_id
    section = state.generated_sections.get(section_id) if section_id is not None else None
    partial = state.partial_sections.get(section_id) if section_id is not None else None
    if runtime_context is None or section_id is None or section is None or partial is None:
        return

    await runtime_context.emit_event(
        SectionPartialEvent(
            generation_id=state.request.generation_id or "",
            section_id=section_id,
            section=section,
            template_id=partial.template_id,
            status=status,
            visual_mode=partial.visual_mode,
            pending_assets=list(partial.pending_assets),
            updated_at=partial.updated_at,
        )
    )


async def _emit_asset_pending(
    state: TextbookPipelineState,
    *,
    runtime_context,
) -> None:
    section_id = state.current_section_id
    partial = state.partial_sections.get(section_id) if section_id is not None else None
    if runtime_context is None or section_id is None or partial is None:
        return
    if not partial.pending_assets:
        return

    await runtime_context.emit_event(
        SectionAssetPendingEvent(
            generation_id=state.request.generation_id or "",
            section_id=section_id,
            pending_assets=list(partial.pending_assets),
            status=partial.status,
            visual_mode=partial.visual_mode,
            updated_at=partial.updated_at,
        )
    )


async def _emit_asset_ready(
    state: TextbookPipelineState,
    *,
    runtime_context,
    ready_assets: list[str],
) -> None:
    section_id = state.current_section_id
    partial = state.partial_sections.get(section_id) if section_id is not None else None
    if runtime_context is None or section_id is None or partial is None:
        return
    if not ready_assets:
        return

    await runtime_context.emit_event(
        SectionAssetReadyEvent(
            generation_id=state.request.generation_id or "",
            section_id=section_id,
            ready_assets=list(ready_assets),
            pending_assets=list(partial.pending_assets),
            visual_mode=partial.visual_mode,
            updated_at=partial.updated_at,
        )
    )


async def _emit_final_section_events(
    state: TextbookPipelineState,
    *,
    runtime_context,
) -> None:
    section_id = state.current_section_id
    section = state.assembled_sections.get(section_id) if section_id is not None else None
    if runtime_context is None or section_id is None or section is None:
        return

    await runtime_context.progress.mark_section_ready(section_id)
    total_sections = len(state.curriculum_outline or []) or state.request.section_count
    completed_sections = len(state.assembled_sections)

    await runtime_context.emit_event(
        SectionFinalEvent(
            generation_id=state.request.generation_id or "",
            section_id=section_id,
            completed_sections=completed_sections,
            total_sections=total_sections,
        )
    )
    await runtime_context.emit_event(
        SectionReadyEvent(
            generation_id=state.request.generation_id or "",
            section_id=section_id,
            section=section,
            completed_sections=completed_sections,
            total_sections=total_sections,
        )
    )


async def process_section(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    typed = TextbookPipelineState.parse(state)
    raw_state = typed.model_dump()
    section_id = typed.current_section_id
    runtime_context, is_retry = await _start_section_flow(typed, config=config)

    try:
        phase1 = await run_section_steps(
            typed,
            steps=[
                ("content_generator", content_generator),
                ("schema_validator", schema_validator),
            ],
            model_overrides=model_overrides,
            config=config,
        )
        merge_state_updates(raw_state, phase1)
        typed = TextbookPipelineState.parse(raw_state)
        if typed.current_section_id not in typed.generated_sections:
            return phase1
        if any(
            error.node == "schema_validator" and error.section_id == section_id
            for error in typed.errors
        ):
            return phase1

        phase2 = await run_section_steps(
            typed,
            steps=[("media_planner", media_planner)],
            model_overrides=model_overrides,
            config=config,
        )
        merge_state_updates(raw_state, phase2)
        typed = TextbookPipelineState.parse(raw_state)
        if section_id is not None and section_id in typed.media_plans:
            publish_runtime_event(
                typed.request.generation_id or "",
                MediaPlanReadyEvent(
                    generation_id=typed.request.generation_id or "",
                    section_id=section_id,
                    slot_count=len(typed.media_plans[section_id].slots),
                ),
            )

        phase2_partial = _build_partial_snapshot(
            typed,
            status="partial",
            updated_at=_utc_now_iso(),
        )
        merge_state_updates(raw_state, phase2_partial)
        typed = TextbookPipelineState.parse(raw_state)
        await _emit_partial_snapshot(typed, runtime_context=runtime_context, status=typed.section_lifecycle.get(section_id, "partial"))
        await _emit_asset_pending(typed, runtime_context=runtime_context)

        initial_pending_assets = list(typed.section_pending_assets.get(section_id, []))

        phase3 = await _run_parallel_phase(
            typed,
            steps=[
                ("diagram_generator", diagram_generator),
                ("image_generator", image_generator),
                ("interaction_generator", interaction_generator),
            ],
            model_overrides=model_overrides,
            config=config,
        )
        merge_state_updates(raw_state, phase3)
        typed = TextbookPipelineState.parse(raw_state)

        final_pending_assets = list(pending_required_slot_ids(typed))
        phase3_partial = _build_partial_snapshot(
            typed,
            status="finalizing",
            pending_assets=final_pending_assets,
            updated_at=_utc_now_iso(),
        )
        merge_state_updates(raw_state, phase3_partial)
        typed = TextbookPipelineState.parse(raw_state)
        await _emit_partial_snapshot(
            typed,
            runtime_context=runtime_context,
            status=typed.section_lifecycle.get(section_id, "finalizing"),
        )

        ready_assets = [
            asset for asset in initial_pending_assets if asset not in set(final_pending_assets)
        ]
        await _emit_asset_ready(
            typed,
            runtime_context=runtime_context,
            ready_assets=ready_assets,
        )

        phase4 = await run_section_steps(
            typed,
            steps=[
                ("section_assembler", section_assembler),
                ("qc_agent", qc_agent),
            ],
            model_overrides=model_overrides,
            config=config,
        )
        merge_state_updates(raw_state, phase4)
        typed = TextbookPipelineState.parse(raw_state)

        if section_id in typed.assembled_sections:
            await _emit_final_section_events(typed, runtime_context=runtime_context)

        return _merge_phase_outputs(phase1, phase2, phase2_partial, phase3, phase3_partial, phase4)
    finally:
        await _finish_section_flow(
            runtime_context,
            section_id=section_id,
            is_retry=is_retry,
        )


__all__ = ["process_section"]
