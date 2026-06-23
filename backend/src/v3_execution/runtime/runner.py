from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from core.events import event_bus
from telemetry.v3_trace import event_types as trace_events
from telemetry.v3_trace.writer import V3TraceWriter
from v3_blueprint.models import ProductionBlueprint
from v3_execution.assembly.pack_builder import V3PackBuilder
from v3_execution.assembly.section_builder import V3SectionBuilder
from v3_execution.booklet_status import (
    collect_fatal_issue_categories,
    derive_booklet_status,
)
from v3_execution.compile_orders import compile_execution_bundle
from v3_execution.config import make_semaphores
from v3_execution.config.timeouts import V3_TIMEOUTS
from v3_execution.executors.answer_key_generator import execute_answer_key
from v3_execution.executors.question_writer import execute_questions
from v3_execution.executors.section_writer import execute_section
from v3_execution.executors.visual_executor import execute_visual
from v3_execution.models import (
    BookletStatus,
    CompiledWorkOrders,
    ExecutionResult,
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
)

from v3_execution.runtime import events
from v3_review import coherence_report_to_generation_summary, run_coherence_review


def _summarize_status_reason(status: str) -> str:
    messages = {
        "draft_ready": "Draft assembled; consistency review pending.",
        "draft_with_warnings": "Draft assembled with minor warnings.",
        "draft_needs_review": "Draft rendered, but major issues remain after review/repair.",
        "final_ready": "Final booklet passed review and is ready.",
        "final_with_warnings": "Final booklet is ready with minor warnings.",
        "failed_unusable": "No usable booklet could be assembled.",
        "streaming_preview": "Generation is still streaming preview content.",
    }
    return messages.get(status, "Booklet status updated.")


def _status_flags(status: str, section_count: int) -> tuple[bool, bool, bool, bool]:
    draft_available = section_count > 0 and status != "failed_unusable"
    final_available = status in {"final_ready", "final_with_warnings"}
    classroom_ready = final_available
    export_allowed = status in {
        "final_ready",
        "final_with_warnings",
        "draft_ready",
        "draft_with_warnings",
        "draft_needs_review",
    }
    return draft_available, final_available, classroom_ready, export_allowed


def _terminal_process_status(*, resource_status: str, booklet_status: str) -> str:
    if booklet_status == "final_ready":
        return "completed"
    if booklet_status == "final_with_warnings":
        return "completed_with_warnings"
    if booklet_status in {"draft_ready", "draft_with_warnings", "draft_needs_review"}:
        return "failed_finalisation"
    if resource_status == "failed":
        return "failed"
    return "failed_unusable"


def _missing_summary(items: list[list[str]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for values in items:
        for value in values:
            summary[value] = summary.get(value, 0) + 1
    return summary


async def _record_visual_trace(
    *,
    trace_writer: V3TraceWriter | None,
    generation_id: str,
    order: Any,
    blocks: list[Any],
    error_summary: str | None = None,
) -> None:
    if trace_writer is None:
        return
    frame_count = len(order.visual.frames) if order.visual.frames else 1
    failed_blocks = [
        block
        for block in blocks
        if isinstance(block, GeneratedVisualBlock) and block.status == "failed"
    ]
    if error_summary or failed_blocks:
        await trace_writer.record_visual_failed(
            generation_id=generation_id,
            visual_id=order.visual.id,
            attaches_to=order.visual.attaches_to,
            component_id=order.visual.component_id,
            parent_visual_id=None,
            mode=order.visual.mode,
            frame_count=frame_count,
            error_summary=error_summary
            or failed_blocks[0].error_message
            or "visual generation failed",
        )
        return
    await trace_writer.record_visual_completed(
        generation_id=generation_id,
        visual_id=order.visual.id,
        attaches_to=order.visual.attaches_to,
        component_id=order.visual.component_id,
        parent_visual_id=None,
        mode=order.visual.mode,
        frame_count=frame_count,
    )


async def run_generation(
    *,
    blueprint: ProductionBlueprint,
    generation_id: str,
    blueprint_id: str,
    template_id: str,
    emit_event: Callable[[str, dict[str, Any]], Awaitable[None]],
    trace_id: str | None = None,
    model_overrides: dict | None = None,
    trace_writer: V3TraceWriter | None = None,
) -> ExecutionResult:
    def _booklet_issues_from_report(report: Any) -> list[dict[str, Any]]:
        return [
            {
                "issue_id": issue.issue_id,
                "severity": issue.severity,
                "category": issue.category,
                "message": issue.message,
                "section_id": issue.generated_ref,
            }
            for issue in report.issues
        ]

    async def _inner() -> ExecutionResult:
        bundle = compile_execution_bundle(
            blueprint,
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
        )
        await emit_event(
            events.WORK_ORDERS_COMPILED,
            {"generation_id": generation_id, "blueprint_id": blueprint_id},
        )
        if trace_writer is not None:
            await trace_writer.record_work_orders(
                section_order_count=len(bundle.section_orders),
                visual_order_count=len(bundle.visual_orders),
                question_order_count=len(bundle.question_orders),
                answer_key_required=bundle.answer_key_order is not None,
            )

        result = ExecutionResult(
            generation_id=generation_id,
            blueprint_id=blueprint_id,
        )
        sem = make_semaphores()

        async def _guard(label: str, coro: Awaitable[list[Any]]) -> list[Any]:
            try:
                return await coro
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"{label}: {exc}")
                return []

        async def _timed_section(order: Any) -> list[Any]:
            async with sem["section_writer"]:
                return await asyncio.wait_for(
                    execute_section(
                        order,
                        emit_event,
                        trace_id=trace_id,
                        generation_id=generation_id,
                        model_overrides=model_overrides,
                    ),
                    timeout=V3_TIMEOUTS["section_writer"],
                )

        async def _timed_questions(order: Any) -> list[Any]:
            async with sem["question_writer"]:
                return await asyncio.wait_for(
                    execute_questions(
                        order,
                        emit_event,
                        trace_id=trace_id,
                        generation_id=generation_id,
                        model_overrides=model_overrides,
                    ),
                    timeout=V3_TIMEOUTS["question_writer"],
                )

        def _visual_deadline(order: Any) -> int:
            if order.visual.mode == "diagram_series" and order.visual.frames:
                return V3_TIMEOUTS["visual_executor_frame"] * max(1, len(order.visual.frames))
            return V3_TIMEOUTS["visual_executor_frame"]

        async def _timed_visual(order: Any) -> list[Any]:
            async with sem["visual_executor"]:
                return await asyncio.wait_for(
                    execute_visual(
                        order,
                        emit_event,
                        trace_id=trace_id,
                        generation_id=generation_id,
                    ),
                    timeout=_visual_deadline(order),
                )

        async def _run_visual_order(order: Any, *, label: str) -> list[Any]:
            try:
                blocks = await _timed_visual(order)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"{label}: {exc}")
                await _record_visual_trace(
                    trace_writer=trace_writer,
                    generation_id=generation_id,
                    order=order,
                    blocks=[],
                    error_summary=str(exc),
                )
                return []
            await _record_visual_trace(
                trace_writer=trace_writer,
                generation_id=generation_id,
                order=order,
                blocks=blocks,
            )
            return blocks

        blueprint_only_visuals = [v for v in bundle.visual_orders if v.dependency == "blueprint_only"]
        section_tasks = [
            _guard(f"section:{order.section.id}", _timed_section(order))
            for order in bundle.section_orders
        ]
        question_tasks = [
            _guard(f"questions:{order.section_id}", _timed_questions(order))
            for order in bundle.question_orders
        ]
        visual_tasks_wave1 = [
            _run_visual_order(order, label=f"visual:{order.visual.id}")
            for order in blueprint_only_visuals
        ]

        wave1 = await asyncio.gather(*(section_tasks + question_tasks + visual_tasks_wave1))
        for batch in wave1:
            if not isinstance(batch, list):
                continue
            for item in batch:
                if isinstance(item, GeneratedComponentBlock):
                    result.component_blocks.append(item)
                elif isinstance(item, GeneratedQuestionBlock):
                    result.question_blocks.append(item)
                elif isinstance(item, GeneratedVisualBlock):
                    result.visual_blocks.append(item)

        text_visuals = [v for v in bundle.visual_orders if v.dependency != "blueprint_only"]
        if text_visuals:
            wave2 = await asyncio.gather(
                *[
                    _run_visual_order(order, label=f"visual:{order.visual.id}:late")
                    for order in text_visuals
                ]
            )
            for batch in wave2:
                if not isinstance(batch, list):
                    continue
                for item in batch:
                    if isinstance(item, GeneratedVisualBlock):
                        result.visual_blocks.append(item)

        try:

            async def _answer_key():
                async with sem["answer_key_generator"]:
                    return await asyncio.wait_for(
                        execute_answer_key(
                            bundle.answer_key_order,
                            emit_event,
                            trace_id=trace_id,
                            generation_id=generation_id,
                            model_overrides=model_overrides,
                        ),
                        timeout=V3_TIMEOUTS["answer_key_generator"],
                    )

            result.answer_key = await _answer_key()
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"answer_key: {exc}")

        if trace_writer is not None:
            sections_attempted = len(bundle.section_orders)
            sections_succeeded = len({block.section_id for block in result.component_blocks})
            await trace_writer.record_execution_summary(
                sections_attempted=sections_attempted,
                sections_succeeded=sections_succeeded,
                sections_failed=max(sections_attempted - sections_succeeded, 0),
                components_planned=sum(len(order.section.components) for order in bundle.section_orders),
                components_delivered=len(result.component_blocks),
                questions_planned=sum(len(order.questions) for order in bundle.question_orders),
                questions_delivered=len(result.question_blocks),
                visuals_planned=len(bundle.visual_orders),
                visuals_delivered=len(result.visual_blocks),
                warnings=list(result.warnings),
            )

        await emit_event(events.ASSEMBLY_STARTED, {"generation_id": generation_id})
        assembler = V3SectionBuilder()

        def _build_sections():
            return assembler.build_sections(
                blueprint,
                result.component_blocks,
                result.question_blocks,
                result.visual_blocks,
                template_id=template_id,
                answer_key=result.answer_key,
            )

        try:
            sections, asm_warnings, section_diagnostics = await asyncio.wait_for(
                asyncio.to_thread(_build_sections),
                timeout=V3_TIMEOUTS["assembly"],
            )
            result.warnings.extend(asm_warnings)
        except Exception as exc:  # noqa: BLE001
            sections = []
            section_diagnostics = []
            result.warnings.append(f"assembly: {exc}")

        pack_builder = V3PackBuilder()
        initial_booklet_status = derive_booklet_status(
            draft_section_count=len(sections),
            render_valid=bool(sections),
            review_done=False,
            finalised=False,
            blocking_count=0,
            major_count=0,
            minor_count=0,
            fatal_issue_categories=set(),
        )
        draft_pack = pack_builder.build(
            blueprint=blueprint,
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
            sections=sections,
            visual_blocks=result.visual_blocks,
            answer_key=result.answer_key,
            warnings=list(result.warnings),
            booklet_status=initial_booklet_status,  # type: ignore[arg-type]
            section_diagnostics=section_diagnostics,
        )

        await emit_event(
            events.DRAFT_PACK_READY,
            {
                "generation_id": generation_id,
                "booklet_status": draft_pack.status,
                "section_count": len(draft_pack.sections),
                "pack": draft_pack.model_dump(mode="json", exclude_none=True),
            },
        )
        if trace_writer is not None:
            incomplete_sections = [
                diag.section_id
                for diag in section_diagnostics
                if diag.status in {"incomplete", "failed"}
            ]
            await trace_writer.record_draft_pack(
                booklet_status=draft_pack.status,
                planned_section_count=len(blueprint.sections),
                assembled_section_count=len(draft_pack.sections),
                renderable=bool(draft_pack.sections),
                incomplete_sections=incomplete_sections,
                missing_components_summary=_missing_summary(
                    [diag.missing_components for diag in section_diagnostics]
                ),
                missing_visuals_summary=_missing_summary(
                    [diag.missing_visuals for diag in section_diagnostics]
                ),
                warnings=list(draft_pack.warnings),
            )
            draft_available, final_available, classroom_ready, export_allowed = _status_flags(
                draft_pack.status,
                len(draft_pack.sections),
            )
            await trace_writer.record_booklet_status(
                booklet_status=draft_pack.status,
                reason=_summarize_status_reason(draft_pack.status),
                draft_available=draft_available,
                final_available=final_available,
                classroom_ready=classroom_ready,
                export_allowed=export_allowed,
            )

        coherence_report_payload: dict | None = None
        resource_final_status = "failed"
        artifact_status: BookletStatus = draft_pack.status
        try:
            coherence_report = await run_coherence_review(
                blueprint,
                draft_pack,
                emit_event,
                trace_id=trace_id or generation_id,
                generation_id=generation_id,
                model_overrides=model_overrides,
            )
            await emit_event(
                events.COHERENCE_REPORT_READY,
                {
                    "generation_id": generation_id,
                    "status": coherence_report.status,
                    "blocking_count": coherence_report.blocking_count,
                    "major_count": coherence_report.major_count,
                    "minor_count": coherence_report.minor_count,
                    "coherence_report": coherence_report.model_dump(mode="json"),
                },
            )
            finalised = coherence_report.status in {"passed", "passed_with_warnings"}
            fatal_categories = collect_fatal_issue_categories(coherence_report.issues)
            artifact_status = derive_booklet_status(
                draft_section_count=len(draft_pack.sections),
                render_valid=bool(draft_pack.sections),
                review_done=True,
                finalised=finalised,
                blocking_count=coherence_report.blocking_count,
                major_count=coherence_report.major_count,
                minor_count=coherence_report.minor_count,
                fatal_issue_categories=fatal_categories,
            )  # type: ignore[assignment]
            draft_pack = draft_pack.model_copy(
                update={
                    "status": artifact_status,
                    "booklet_issues": _booklet_issues_from_report(coherence_report),
                }
            )
            coherence_report_payload = coherence_report_to_generation_summary(coherence_report)
            resource_final_status = coherence_report.status
            if trace_writer is not None:
                await trace_writer.record_review_summary(
                    minor_count=coherence_report.minor_count,
                    major_count=coherence_report.major_count,
                    blocking_count=coherence_report.blocking_count,
                    fatal_categories=sorted(fatal_categories),
                )
                draft_available, final_available, classroom_ready, export_allowed = _status_flags(
                    artifact_status,
                    len(draft_pack.sections),
                )
                await trace_writer.record_booklet_status(
                    booklet_status=artifact_status,
                    reason=_summarize_status_reason(artifact_status),
                    draft_available=draft_available,
                    final_available=final_available,
                    classroom_ready=classroom_ready,
                    export_allowed=export_allowed,
                )

            if artifact_status in {"final_ready", "final_with_warnings"}:
                await emit_event(
                    events.FINAL_PACK_READY,
                    {
                        "generation_id": generation_id,
                        "booklet_status": artifact_status,
                        "pack": draft_pack.model_dump(mode="json", exclude_none=True),
                    },
                )
                if trace_writer is not None:
                    draft_available, final_available, classroom_ready, export_allowed = _status_flags(
                        artifact_status,
                        len(draft_pack.sections),
                    )
                    await trace_writer.record_final_pack(
                        booklet_status=artifact_status,
                        final_section_count=len(draft_pack.sections),
                        warnings=list(draft_pack.warnings),
                        classroom_ready=classroom_ready,
                        export_allowed=export_allowed,
                    )
            else:
                await emit_event(
                    events.DRAFT_STATUS_UPDATED,
                    {
                        "generation_id": generation_id,
                        "booklet_status": artifact_status,
                        "pack": draft_pack.model_dump(mode="json", exclude_none=True),
                    },
                )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"coherence_review: {exc}")
            artifact_status = draft_pack.status
            await emit_event(
                events.DRAFT_STATUS_UPDATED,
                {
                    "generation_id": generation_id,
                    "booklet_status": artifact_status,
                    "pack": draft_pack.model_dump(mode="json", exclude_none=True),
                    "message": "Coherence review did not complete; draft remains available.",
                },
            )
            if trace_writer is not None:
                draft_available, final_available, classroom_ready, export_allowed = _status_flags(
                    artifact_status,
                    len(draft_pack.sections),
                )
                await trace_writer.record_booklet_status(
                    booklet_status=artifact_status,
                    reason="Coherence review did not complete; draft remains available.",
                    draft_available=draft_available,
                    final_available=final_available,
                    classroom_ready=classroom_ready,
                    export_allowed=export_allowed,
                )

        await emit_event(
            events.RESOURCE_FINALISED,
            {
                "generation_id": generation_id,
                "status": resource_final_status,
                "booklet_status": artifact_status,
            },
        )
        if trace_writer is not None:
            draft_available, final_available, classroom_ready, export_allowed = _status_flags(
                artifact_status,
                len(draft_pack.sections),
            )
            await trace_writer.record_terminal(
                terminal_event_type=trace_events.RESOURCE_FINALISED,
                process_status=_terminal_process_status(
                    resource_status=resource_final_status,
                    booklet_status=artifact_status,
                ),
                booklet_status=artifact_status,
                draft_available=draft_available,
                final_available=final_available,
                classroom_ready=classroom_ready,
                export_allowed=export_allowed,
                error_summary=None,
            )

        await emit_event(
            events.GENERATION_COMPLETE,
            {
                "generation_id": generation_id,
                "booklet_status": artifact_status,
                "warnings": result.warnings,
                **({"coherence_review": coherence_report_payload} if coherence_report_payload else {}),
            },
        )
        return result

    try:
        return await asyncio.wait_for(_inner(), timeout=V3_TIMEOUTS["generation_total"])
    except asyncio.TimeoutError:
        timeout_message = (
            f"generation_total: exceeded {V3_TIMEOUTS['generation_total']}s cap"
        )
        if trace_writer is not None:
            await trace_writer.record_terminal(
                terminal_event_type=trace_events.GENERATION_TIMEOUT,
                process_status="generation_timeout",
                booklet_status="failed_unusable",
                draft_available=False,
                final_available=False,
                classroom_ready=False,
                export_allowed=False,
                error_summary=timeout_message,
            )
        await emit_event(
            events.GENERATION_WARNING,
            {"generation_id": generation_id, "message": timeout_message},
        )
        return ExecutionResult(
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            warnings=[timeout_message],
        )


async def sse_event_stream(
    *,
    blueprint: ProductionBlueprint,
    generation_id: str,
    blueprint_id: str,
    template_id: str,
    trace_id: str | None = None,
    model_overrides: dict | None = None,
    trace_writer: V3TraceWriter | None = None,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        body = dict(payload)
        body["type"] = event_type
        await queue.put(events.format_sse_payload(event_type, body))
        event_bus.publish(generation_id, body)

    async def worker() -> None:
        try:
            await emit(events.GENERATION_STARTED, {"generation_id": generation_id})
            await run_generation(
                blueprint=blueprint,
                generation_id=generation_id,
                blueprint_id=blueprint_id,
                template_id=template_id,
                emit_event=emit,
                trace_id=trace_id or generation_id,
                model_overrides=model_overrides,
                trace_writer=trace_writer,
            )
        except Exception as exc:  # noqa: BLE001
            await emit(
                events.GENERATION_WARNING,
                {"generation_id": generation_id, "message": str(exc)},
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(worker())

    try:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk
    finally:
        await task


def execution_bundle_summary(bundle: CompiledWorkOrders) -> dict[str, Any]:
    return bundle.model_dump(mode="json")


__all__ = ["execution_bundle_summary", "run_generation", "sse_event_stream"]
