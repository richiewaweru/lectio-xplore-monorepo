from __future__ import annotations

import asyncio
from copy import deepcopy
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


def _format_exception(exc: Exception) -> str:
    """Return an actionable warning even for exceptions with an empty message."""
    detail = str(exc).strip() or repr(exc)
    return f"{type(exc).__name__}: {detail}"


def _build_skeleton_pack(
    *,
    blueprint: ProductionBlueprint,
    bundle: CompiledWorkOrders,
    generation_id: str,
    blueprint_id: str,
    template_id: str,
) -> dict[str, Any]:
    section_plan_by_id = {section.section_id: section for section in blueprint.sections}
    sections: list[dict[str, Any]] = []
    for index, order in enumerate(bundle.section_orders):
        section = order.section
        section_plan = section_plan_by_id.get(section.id)
        role = section_plan.role if section_plan is not None else ""
        sections.append(
            {
                "section_id": section.id,
                "template_id": template_id,
                "title": section.title,
                "role": role,
                "order": index,
                "visual_required": bool(
                    section_plan.visual_required if section_plan is not None else False
                ),
                "components": [
                    {
                        "component_id": component.component_id,
                        "intent": component.content_intent,
                    }
                    for component in section.components
                ],
                "header": {
                    "title": section.title,
                },
            }
        )
    return {
        "generation_id": generation_id,
        "blueprint_id": blueprint_id,
        "template_id": template_id,
        "subject": blueprint.metadata.subject,
        "status": "streaming_preview",
        "sections": sections,
        "warnings": [],
        "section_diagnostics": [],
        "booklet_issues": [],
    }


def _missing_summary(items: list[list[str]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for values in items:
        for value in values:
            summary[value] = summary.get(value, 0) + 1
    return summary


def _replace_by_section_id(items: list[dict[str, Any]], next_item: dict[str, Any]) -> list[dict[str, Any]]:
    section_id = str(next_item.get("section_id") or "")
    replaced = False
    next_items: list[dict[str, Any]] = []
    for item in items:
        if item.get("section_id") == section_id:
            next_items.append(next_item)
            replaced = True
        else:
            next_items.append(item)
    if not replaced:
        next_items.append(next_item)
    return next_items


def _section_ids_for_visual(
    *,
    order: Any,
    section_ids: set[str],
    question_section_lookup: dict[str, str],
    visual_component_section_lookup: dict[str, set[str]],
) -> set[str]:
    visual = order.visual
    related: set[str] = set()
    if visual.attaches_to in section_ids:
        related.add(visual.attaches_to)
    mapped = question_section_lookup.get(visual.attaches_to)
    if mapped:
        related.add(mapped)
    for question_id in getattr(visual, "source_question_ids", []) or []:
        mapped = question_section_lookup.get(question_id)
        if mapped:
            related.add(mapped)
    if visual.component_id:
        related.update(visual_component_section_lookup.get(visual.component_id, set()))
    return related


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
    preserved_ready_sections: list[dict[str, Any]] | None = None,
) -> ExecutionResult:
    def _booklet_issues_from_report(report: Any) -> list[dict[str, Any]]:
        return [
            {
                "issue_id": issue.issue_id,
                "severity": issue.severity,
                "category": issue.category,
                "message": issue.message,
                "section_id": issue.generated_ref,
                "repair_target_id": issue.repair_target_id,
                "qc_correction_hint": issue.qc_correction_hint,
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
        skeleton_pack = _build_skeleton_pack(
            blueprint=blueprint,
            bundle=bundle,
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
        )
        preserved_sections = {
            str(section.get("section_id")): deepcopy(section)
            for section in preserved_ready_sections or []
            if isinstance(section, dict) and isinstance(section.get("section_id"), str)
        }
        if preserved_sections:
            skeleton_pack["sections"] = [
                deepcopy(preserved_sections.get(str(section.get("section_id")), section))
                for section in skeleton_pack["sections"]
            ]
        await emit_event(
            events.SKELETON_READY,
            {
                "generation_id": generation_id,
                "section_count": len(skeleton_pack["sections"]),
                "booklet_status": "streaming_preview",
                "pack": deepcopy(skeleton_pack),
            },
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
        # Streaming assembly may run before executor tasks complete, so bind this
        # dependency before the closure below captures it.
        assembler = V3SectionBuilder()
        sem = make_semaphores()

        async def _guard(label: str, coro: Awaitable[list[Any]]) -> list[Any]:
            try:
                return await coro
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"{label}: {_format_exception(exc)}")
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
                result.warnings.append(f"{label}: {_format_exception(exc)}")
                await _record_visual_trace(
                    trace_writer=trace_writer,
                    generation_id=generation_id,
                    order=order,
                    blocks=[],
                    error_summary=_format_exception(exc),
                )
                return []
            await _record_visual_trace(
                trace_writer=trace_writer,
                generation_id=generation_id,
                order=order,
                blocks=blocks,
            )
            return blocks

        section_ids = {order.section.id for order in bundle.section_orders}
        question_section_lookup = {
            question.question_id: question.section_id for question in blueprint.question_plan
        }
        visual_component_section_lookup: dict[str, set[str]] = {}
        for section in blueprint.sections:
            for component in section.components:
                visual_component_section_lookup.setdefault(component.component, set()).add(
                    section.section_id
                )
        visual_sections: dict[str, set[str]] = {}
        visuals_by_section: dict[str, list[Any]] = {section_id: [] for section_id in section_ids}
        for order in bundle.visual_orders:
            related = _section_ids_for_visual(
                order=order,
                section_ids=section_ids,
                question_section_lookup=question_section_lookup,
                visual_component_section_lookup=visual_component_section_lookup,
            )
            visual_sections[order.work_order_id] = related
            for section_id in related:
                visuals_by_section.setdefault(section_id, []).append(order)

        question_sections = {order.section_id for order in bundle.question_orders}
        section_done: set[str] = set(preserved_sections)
        question_done: set[str] = set(section_ids - question_sections) | set(preserved_sections)
        visual_done: set[str] = {
            section_id for section_id in section_ids if not visuals_by_section.get(section_id)
        } | set(preserved_sections)
        emitted_sections: set[str] = set(preserved_sections)
        scheduled_visual_orders: set[str] = set()
        completed_visual_orders: set[str] = set()
        task_meta: dict[asyncio.Task[list[Any]], tuple[str, str, Any]] = {}

        def _schedule_task(kind: str, section_id: str, label: str, coro: Awaitable[list[Any]], order: Any) -> None:
            task = asyncio.create_task(_guard(label, coro))
            task_meta[task] = (kind, section_id, order)

        def _schedule_visual(order: Any, *, label: str) -> None:
            if order.work_order_id in scheduled_visual_orders:
                return
            scheduled_visual_orders.add(order.work_order_id)
            task = asyncio.create_task(_run_visual_order(order, label=label))
            task_meta[task] = ("visual", "", order)

        def _mark_visual_sections_ready(order: Any) -> None:
            for section_id in visual_sections.get(order.work_order_id, set()):
                required = visuals_by_section.get(section_id, [])
                if required and all(v.work_order_id in completed_visual_orders for v in required):
                    visual_done.add(section_id)

        async def _emit_ready_sections() -> None:
            nonlocal partial_pack
            ready_ids = section_done & question_done & visual_done
            for section_plan in blueprint.sections:
                section_id = section_plan.section_id
                if section_id not in ready_ids or section_id in emitted_sections:
                    continue
                single_blueprint = blueprint.model_copy(update={"sections": [section_plan]})

                def _build_single_section():
                    return assembler.build_sections(
                        single_blueprint,
                        result.component_blocks,
                        result.question_blocks,
                        result.visual_blocks,
                        template_id=template_id,
                    )

                try:
                    single_sections, single_warnings, single_diagnostics = await asyncio.to_thread(
                        _build_single_section
                    )
                except Exception as exc:  # noqa: BLE001
                    result.warnings.append(f"assembly:{section_id}: {_format_exception(exc)}")
                    emitted_sections.add(section_id)
                    continue
                result.warnings.extend(single_warnings)
                if not single_sections:
                    emitted_sections.add(section_id)
                    continue
                current_pack = partial_pack["pack"]
                current_pack["sections"] = _replace_by_section_id(
                    list(current_pack.get("sections") or []),
                    single_sections[0],
                )
                diagnostics = [d.model_dump(mode="json") for d in single_diagnostics]
                for diagnostic in diagnostics:
                    current_pack["section_diagnostics"] = _replace_by_section_id(
                        list(current_pack.get("section_diagnostics") or []),
                        diagnostic,
                    )
                current_pack["visual_blocks"] = [
                    block.model_dump(mode="json", exclude_none=True)
                    for block in result.visual_blocks
                ]
                current_pack["warnings"] = list(result.warnings)
                emitted_sections.add(section_id)
                await emit_event(
                    events.SECTION_READY,
                    {
                        "generation_id": generation_id,
                        "section_id": section_id,
                        "booklet_status": "streaming_preview",
                        "pack": current_pack,
                    },
                )

        partial_pack: dict[str, Any] = {"pack": skeleton_pack}

        for order in bundle.section_orders:
            if order.section.id in preserved_sections:
                continue
            _schedule_task(
                "section",
                order.section.id,
                f"section:{order.section.id}",
                _timed_section(order),
                order,
            )
        for order in bundle.question_orders:
            if order.section_id in preserved_sections:
                continue
            _schedule_task(
                "question",
                order.section_id,
                f"questions:{order.section_id}",
                _timed_questions(order),
                order,
            )
        for order in bundle.visual_orders:
            related = visual_sections.get(order.work_order_id, set())
            if related and related.issubset(preserved_sections):
                scheduled_visual_orders.add(order.work_order_id)
                completed_visual_orders.add(order.work_order_id)
                _mark_visual_sections_ready(order)
                continue
            if order.dependency == "blueprint_only":
                _schedule_visual(order, label=f"visual:{order.visual.id}")

        while task_meta:
            done, _pending = await asyncio.wait(task_meta.keys(), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                kind, section_id, order = task_meta.pop(task)
                batch = task.result()
                if isinstance(batch, list):
                    for item in batch:
                        if isinstance(item, GeneratedComponentBlock):
                            result.component_blocks.append(item)
                        elif isinstance(item, GeneratedQuestionBlock):
                            result.question_blocks.append(item)
                        elif isinstance(item, GeneratedVisualBlock):
                            result.visual_blocks.append(item)
                if kind == "section":
                    section_done.add(section_id)
                elif kind == "question":
                    question_done.add(section_id)
                elif kind == "visual":
                    completed_visual_orders.add(order.work_order_id)
                    _mark_visual_sections_ready(order)

            for order in bundle.visual_orders:
                if order.dependency == "blueprint_only":
                    continue
                related = visual_sections.get(order.work_order_id, set())
                if related and all(
                    section_id in section_done and section_id in question_done
                    for section_id in related
                ):
                    _schedule_visual(order, label=f"visual:{order.visual.id}:late")

            for section_id, orders in visuals_by_section.items():
                if not orders:
                    visual_done.add(section_id)
                    continue
                if all(order.work_order_id in completed_visual_orders for order in orders):
                    visual_done.add(section_id)

            await _emit_ready_sections()

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
            result.warnings.append(f"answer_key: {_format_exception(exc)}")

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
        remaining_blueprint = blueprint.model_copy(
            update={
                "sections": [
                    section
                    for section in blueprint.sections
                    if section.section_id not in preserved_sections
                ]
            }
        )

        def _build_sections():
            return assembler.build_sections(
                remaining_blueprint,
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
            result.warnings.append(f"assembly: {_format_exception(exc)}")

        generated_sections = {
            str(section.get("section_id")): section
            for section in sections
            if isinstance(section, dict) and isinstance(section.get("section_id"), str)
        }
        sections = [
            deepcopy(preserved_sections.get(section.section_id))
            if section.section_id in preserved_sections
            else generated_sections[section.section_id]
            for section in blueprint.sections
            if section.section_id in preserved_sections or section.section_id in generated_sections
        ]

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

        for section in draft_pack.sections:
            section_id = str(section.get("section_id") or "")
            if not section_id or section_id in emitted_sections:
                continue
            current_pack = partial_pack["pack"]
            current_pack["sections"] = _replace_by_section_id(
                list(current_pack.get("sections") or []),
                section,
            )
            for diagnostic in section_diagnostics:
                if diagnostic.section_id != section_id:
                    continue
                current_pack["section_diagnostics"] = _replace_by_section_id(
                    list(current_pack.get("section_diagnostics") or []),
                    diagnostic.model_dump(mode="json"),
                )
            current_pack["visual_blocks"] = [
                block.model_dump(mode="json", exclude_none=True)
                for block in result.visual_blocks
            ]
            current_pack["warnings"] = list(result.warnings)
            emitted_sections.add(section_id)
            await emit_event(
                events.SECTION_READY,
                {
                    "generation_id": generation_id,
                    "section_id": section_id,
                    "booklet_status": "streaming_preview",
                    "pack": current_pack,
                },
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
            result.warnings.append(f"coherence_review: {_format_exception(exc)}")
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
    preserved_ready_sections: list[dict[str, Any]] | None = None,
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
                preserved_ready_sections=preserved_ready_sections,
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
