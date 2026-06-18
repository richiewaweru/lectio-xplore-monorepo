"""
pipeline.run -- public entrypoint for the generation engine.
"""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

import core.events as core_events
from core.dependencies import get_settings
from pipeline.console_diagnostics import force_console_log
from pipeline.api import (
    PipelineCommand,
    PipelineDocument,
    PipelineErrorInfo,
    FailedSectionEntry,
    PipelinePartialSectionEntry,
    PipelineResult,
    PipelineSectionManifestItem,
    PipelineSectionReport,
)
from pipeline.contracts import get_contract
from pipeline.events import (
    PipelineEvent,
    PipelineStartEvent,
    QCCompleteEvent,
    RuntimeProgressEvent,
    SectionFinalEvent,
    SectionReadyEvent,
    SectionStartedEvent,
)
from pipeline.graph import build_graph
from pipeline.runtime_context import (
    build_runtime_context,
    build_runtime_policy_event,
    register_runtime_context,
    runtime_config_for_context,
    unregister_runtime_context,
)
from pipeline.state import PipelineStatus, TextbookPipelineState, merge_state_updates
from pipeline.types.section_content import SectionContent
from pipeline.types.template_contract import TemplateContractSummary

__all__ = [
    "SectionContent",
    "PipelineCommand",
    "PipelineDocument",
    "PipelineResult",
    "PipelineStatus",
    "TemplateContractSummary",
    "run_pipeline",
    "run_pipeline_streaming",
    "build_graph",
]

async def _emit(
    event: PipelineEvent,
    on_event: Callable[[PipelineEvent], Awaitable[None] | None] | None,
) -> None:
    if on_event is None:
        return
    maybe_awaitable = on_event(event)
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


def _merge_state(final_state: dict[str, Any], output: dict[str, Any]) -> None:
    merge_state_updates(final_state, output)


def _normalize_partial_entry_payload(partial: Any) -> Any:
    if isinstance(partial, PipelinePartialSectionEntry):
        return partial
    if hasattr(partial, "model_dump"):
        return partial.model_dump(mode="json", exclude_none=True)
    if hasattr(partial, "dict"):
        return partial.dict()
    return partial


def _sorted_sections(
    state: TextbookPipelineState,
) -> list[SectionContent]:
    if not state.curriculum_outline:
        return list(state.assembled_sections.values())

    ordered: list[SectionContent] = []
    for plan in sorted(state.curriculum_outline, key=lambda item: item.position):
        section = state.assembled_sections.get(plan.section_id)
        if section is not None:
            ordered.append(section)
    return ordered


def _build_section_manifest(state: TextbookPipelineState) -> list[PipelineSectionManifestItem]:
    if not state.curriculum_outline:
        return []

    return [
        PipelineSectionManifestItem(
            section_id=plan.section_id,
            title=plan.title,
            position=plan.position,
        )
        for plan in sorted(state.curriculum_outline, key=lambda item: item.position)
    ]


def _build_reports(state: TextbookPipelineState) -> list[PipelineSectionReport]:
    reports = [
        PipelineSectionReport.from_qc_report(report)
        for report in state.qc_reports.values()
    ]
    reports.sort(key=lambda item: item.section_id)
    return reports


def _build_failed_sections(state: TextbookPipelineState) -> list[FailedSectionEntry]:
    ready_ids = set(state.assembled_sections)
    failed_sections = [
        FailedSectionEntry(
            section_id=record.section_id,
            title=record.title,
            position=record.position,
            focus=record.focus,
            bridges_from=record.bridges_from,
            bridges_to=record.bridges_to,
            needs_diagram=record.needs_diagram,
            visual_placements_count=record.visual_placements_count,
            needs_worked_example=record.needs_worked_example,
            failed_at_node=record.failed_at_node,
            error_type=record.error_type,
            error_summary=record.error_summary,
            attempt_count=record.attempt_count,
            can_retry=record.can_retry,
            missing_components=list(record.missing_components),
            failure_detail=record.failure_detail,
        )
        for record in state.failed_sections.values()
        if record.section_id not in ready_ids
    ]
    failed_sections.sort(key=lambda item: (item.position, item.section_id))
    return failed_sections


def _build_partial_sections(state: TextbookPipelineState) -> list[PipelinePartialSectionEntry]:
    final_ids = set(state.assembled_sections)
    failed_ids = set(state.failed_sections)
    manifest_positions = {
        item.section_id: item.position
        for item in _build_section_manifest(state)
    }

    partial_sections = [
        PipelinePartialSectionEntry(
            section_id=record.section_id,
            template_id=record.template_id,
            content=record.content,
            status=state.section_lifecycle.get(record.section_id, record.status),
            visual_mode=record.visual_mode,
            pending_assets=list(
                state.section_pending_assets.get(record.section_id, record.pending_assets)
            ),
            updated_at=record.updated_at,
        )
        for record in state.partial_sections.values()
        if record.section_id not in final_ids and record.section_id not in failed_ids
    ]
    partial_sections.sort(
        key=lambda item: (
            manifest_positions.get(item.section_id, len(manifest_positions) + 1),
            item.section_id,
        )
    )
    return partial_sections


def _build_document(
    command: PipelineCommand,
    state: TextbookPipelineState,
    *,
    status: str,
    generation_time_seconds: float,
    error: str | None = None,
) -> PipelineDocument:
    reports = _build_reports(state)
    partial_sections = _build_partial_sections(state)
    failed_sections = _build_failed_sections(state)
    final_sections = _sorted_sections(state)
    planned_sections = max(len(state.curriculum_outline or []), command.section_count or 0)
    if status != "completed":
        quality_passed = False if planned_sections else None
    elif not reports and planned_sections:
        quality_passed = False
    elif planned_sections and len(reports) < planned_sections:
        quality_passed = False
    elif reports:
        quality_passed = all(report.passed for report in reports)
    else:
        quality_passed = None
    completed_at = (
        datetime.now(timezone.utc)
        if status in {"completed", "failed", "partial"}
        else None
    )

    return PipelineDocument(
        generation_id=command.generation_id or "",
        subject=command.subject,
        context=command.context,
        mode=command.mode,
        template_id=command.template_id,
        preset_id=command.preset_id,
        status=status,
        section_manifest=_build_section_manifest(state),
        sections=final_sections,
        partial_sections=partial_sections,
        failed_sections=failed_sections,
        qc_reports=reports,
        quality_passed=quality_passed,
        error=error,
        updated_at=datetime.now(timezone.utc),
        completed_at=completed_at,
    )


def _document_error_summary(state: TextbookPipelineState) -> str | None:
    if state.errors:
        first = state.errors[0]
        if first.section_id:
            return f"Section {first.section_id}: {first.message}"
        return first.message

    failed_sections = _build_failed_sections(state)
    if failed_sections:
        first = failed_sections[0]
        return f"Section {first.section_id}: {first.error_summary}"

    partial_sections = _build_partial_sections(state)
    for partial in partial_sections:
        if partial.pending_assets:
            pending = ", ".join(partial.pending_assets)
            return (
                f"Section {partial.section_id} is still waiting on required assets: {pending}"
            )

    return None


def _resolve_terminal_status(
    command: PipelineCommand,
    state: TextbookPipelineState,
) -> str:
    planned_sections = max(len(state.curriculum_outline or []), command.section_count or 0)
    final_count = len(_sorted_sections(state))
    partial_count = len(_build_partial_sections(state))
    failed_count = len(_build_failed_sections(state))
    has_terminal_error = bool(state.errors or state.failed_sections)

    if planned_sections > 0 and final_count == planned_sections and partial_count == 0 and failed_count == 0:
        status = "completed"
    elif final_count == 0 and partial_count == 0 and (failed_count > 0 or has_terminal_error):
        status = "failed"
    else:
        status = "partial"

    force_console_log(
        "RUN_STATUS",
        "RESOLVED",
        generation_id=command.generation_id or "",
        planned_sections=planned_sections,
        final_count=final_count,
        partial_count=partial_count,
        failed_count=failed_count,
        status=status,
    )
    return status

def _build_result(
    command: PipelineCommand,
    raw_state: dict[str, Any],
    generation_time_seconds: float,
) -> PipelineResult:
    state = TextbookPipelineState.parse(raw_state)
    status = _resolve_terminal_status(command, state)
    document = _build_document(
        command,
        state,
        status=status,
        generation_time_seconds=generation_time_seconds,
        error=_document_error_summary(state) if status != "completed" else None,
    )
    return PipelineResult(
        document=document,
        completed_nodes=list(state.completed_nodes),
        errors=[
            PipelineErrorInfo(
                node=error.node,
                message=error.message,
                section_id=error.section_id,
                recoverable=error.recoverable,
            )
            for error in state.errors
        ],
        generation_time_seconds=generation_time_seconds,
    )


async def run_pipeline(
    command: PipelineCommand,
) -> PipelineResult:
    return await run_pipeline_streaming(command)


async def run_pipeline_streaming(
    command: PipelineCommand,
    on_event: Callable[[PipelineEvent], Awaitable[None] | None] | None = None,
) -> PipelineResult:
    runtime_context = build_runtime_context(
        request=command,
        settings=get_settings(),
        emit_event_callback=on_event,
    )
    register_runtime_context(runtime_context)
    contract = get_contract(command.template_id)
    graph = build_graph()
    initial = TextbookPipelineState(
        request=command,
        contract=contract,
        max_rerenders=runtime_context.policy.max_section_rerenders,
        status=PipelineStatus.RUNNING,
    )
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            **runtime_config_for_context(runtime_context),
        }
    }

    try:
        await _emit(
            PipelineStartEvent(
                generation_id=command.generation_id or "",
                section_count=command.section_count,
                template_id=command.template_id,
                preset_id=command.preset_id,
            ),
            on_event,
        )
        core_events.event_bus.publish(
            command.generation_id or "",
            build_runtime_policy_event(runtime_context),
        )
        core_events.event_bus.publish(
            command.generation_id or "",
            RuntimeProgressEvent(
                generation_id=command.generation_id or "",
                snapshot=await runtime_context.progress.snapshot(),
            ),
        )

        final_state: dict[str, Any] = initial.model_dump()
        started = perf_counter()
        emitted_started_sections = False

        async for chunk in graph.astream(initial.model_dump(), config=config):
            for node_name, output in chunk.items():
                if node_name == "__end__":
                    continue

                if isinstance(output, dict):
                    _merge_state(final_state, output)

                typed_state = TextbookPipelineState.parse(final_state)

                if node_name == "curriculum_planner" and not emitted_started_sections:
                    for plan in typed_state.curriculum_outline or []:
                        await _emit(
                            SectionStartedEvent(
                                generation_id=command.generation_id or "",
                                section_id=plan.section_id,
                                title=plan.title,
                                position=plan.position,
                            ),
                            on_event,
                        )
                    emitted_started_sections = True

                if node_name in {"retry_media_frame", "retry_field"}:
                    assembled = output.get("assembled_sections", {}) if isinstance(output, dict) else {}
                    total_sections = len(typed_state.curriculum_outline or []) or command.section_count
                    completed_sections = len(typed_state.assembled_sections)
                    for section_id, section in assembled.items():
                        await runtime_context.progress.mark_section_ready(section_id)
                        section_content = (
                            section
                            if isinstance(section, SectionContent)
                            else SectionContent.model_validate(section)
                        )
                        final_event = SectionFinalEvent(
                            generation_id=command.generation_id or "",
                            section_id=section_id,
                            completed_sections=completed_sections,
                            total_sections=total_sections,
                        )
                        await _emit(final_event, on_event)
                        await _emit(
                            SectionReadyEvent(
                                generation_id=final_event.generation_id,
                                section_id=final_event.section_id,
                                section=section_content,
                                completed_sections=final_event.completed_sections,
                                total_sections=final_event.total_sections,
                            ),
                            on_event,
                        )

                if node_name in {"process_section", "retry_media_frame", "retry_field"}:
                    total_sections = len(typed_state.curriculum_outline or []) or command.section_count
                    completed_sections = len(typed_state.assembled_sections)
                    reports = typed_state.qc_reports
                    if (
                        reports
                        and total_sections
                        and completed_sections >= total_sections
                        and len(reports) >= total_sections
                        and not _build_partial_sections(typed_state)
                        and not _build_failed_sections(typed_state)
                    ):
                        await _emit(
                            QCCompleteEvent(
                                generation_id=command.generation_id or "",
                                passed=sum(1 for report in reports.values() if report.passed),
                                total=len(reports),
                            ),
                            on_event,
                        )

        return _build_result(command, final_state, perf_counter() - started)
    finally:
        unregister_runtime_context(runtime_context.id)
