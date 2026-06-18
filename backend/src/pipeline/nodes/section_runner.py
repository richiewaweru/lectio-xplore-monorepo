from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from langchain_core.runnables.config import RunnableConfig
from core.llm.logging import NodeLogger
from pipeline.api import PipelineSectionReport
from pipeline.events import (
    NodeFinishedEvent,
    NodeStartedEvent,
    SectionAttemptStartedEvent,
    SectionFailedEvent,
    SectionReportUpdatedEvent,
    SectionRetryQueuedEvent,
)
from pipeline.runtime_context import get_runtime_context
from pipeline.runtime_diagnostics import (
    current_section_attempt,
    generation_id_from_state,
    node_error_messages,
    publish_runtime_event,
)
from pipeline.state import (
    FailedSectionRecord,
    NodeFailureDetail,
    PipelineError,
    QCReport,
    RerenderRequest,
    TextbookPipelineState,
    merge_state_updates,
)
from pipeline.types.requests import count_visual_placements, needs_diagram_from_placements
from pipeline.types.section_content import SectionContent

logger = logging.getLogger(__name__)

SectionStep = Callable[..., Awaitable[dict]]
NamedSectionStep = tuple[str, SectionStep]

_RESOURCE_LIMITERS = {
    "diagram_generator": "media",
    "image_generator": "media",
    "interaction_generator": "media",
    "qc_agent": "qc",
}

_SECTION_REPORT_SOURCES = {
    "section_assembler": "assembler",
    "qc_agent": "qc_agent",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report_source_for(node_name: str) -> str | None:
    return _SECTION_REPORT_SOURCES.get(node_name)


def _node_logger(generation_id: str, section_id: str | None, node_name: str) -> NodeLogger:
    return NodeLogger(
        generation_id=generation_id,
        section_id=section_id,
        node_name=node_name,
    )


def _coerce_report(report: Any) -> PipelineSectionReport:
    qc_report = report if isinstance(report, QCReport) else QCReport.model_validate(report)
    return PipelineSectionReport.from_qc_report(qc_report)


def _coerce_rerender_request(request: Any) -> RerenderRequest:
    return request if isinstance(request, RerenderRequest) else RerenderRequest.model_validate(request)


def _coerce_failed_section(record: Any) -> FailedSectionRecord:
    return record if isinstance(record, FailedSectionRecord) else FailedSectionRecord.model_validate(record)


def _step_accepts_config(step: SectionStep) -> bool:
    return "config" in inspect.signature(step).parameters


async def _invoke_step(
    step: SectionStep,
    state: Any,
    *,
    model_overrides: dict | None,
    config: RunnableConfig | None,
) -> dict:
    kwargs: dict[str, Any] = {"model_overrides": model_overrides}
    if config is not None and _step_accepts_config(step):
        kwargs["config"] = config
    return await step(state, **kwargs)


def _rerender_request_changed(before: RerenderRequest | None, after: RerenderRequest | None) -> bool:
    if before is None and after is None:
        return False
    if before is None or after is None:
        return True
    return before.model_dump() != after.model_dump()


def _rerender_request_updates(
    before_state: TextbookPipelineState,
    after_state: TextbookPipelineState,
    section_id: str | None,
) -> dict[str, RerenderRequest | None]:
    if not section_id:
        return {}

    before_request = before_state.pending_rerender_for(section_id)
    after_request = after_state.pending_rerender_for(section_id)
    if not _rerender_request_changed(before_request, after_request):
        return {}
    return {section_id: after_request}


def _build_section_output(
    before_state: TextbookPipelineState,
    after_state: TextbookPipelineState,
    *,
    section_id: str | None,
    completed_nodes: Sequence[str],
) -> dict[str, Any]:
    output: dict[str, Any] = {"completed_nodes": list(completed_nodes)}

    if section_id and section_id in after_state.generated_sections:
        output["generated_sections"] = {section_id: after_state.generated_sections[section_id]}
    if section_id and section_id in after_state.media_plans:
        output["media_plans"] = {section_id: after_state.media_plans[section_id]}
    if section_id and section_id in after_state.media_slot_results:
        output["media_slot_results"] = {section_id: after_state.media_slot_results[section_id]}
    if section_id and section_id in after_state.media_frame_results:
        output["media_frame_results"] = {
            section_id: after_state.media_frame_results[section_id]
        }
    if section_id and section_id in after_state.media_lifecycle:
        output["media_lifecycle"] = {section_id: after_state.media_lifecycle[section_id]}
    if section_id and section_id in after_state.interaction_specs:
        output["interaction_specs"] = {section_id: after_state.interaction_specs[section_id]}
    if section_id and section_id in after_state.partial_sections:
        output["partial_sections"] = {section_id: after_state.partial_sections[section_id]}
    if section_id and section_id in after_state.assembled_sections:
        output["assembled_sections"] = {section_id: after_state.assembled_sections[section_id]}
    if section_id and section_id in after_state.section_pending_assets:
        output["section_pending_assets"] = {
            section_id: after_state.section_pending_assets[section_id]
        }
    if section_id and section_id in after_state.section_lifecycle:
        output["section_lifecycle"] = {section_id: after_state.section_lifecycle[section_id]}
    if section_id and section_id in after_state.qc_reports:
        output["qc_reports"] = {section_id: after_state.qc_reports[section_id]}
    if section_id and section_id in after_state.failed_sections:
        output["failed_sections"] = {section_id: after_state.failed_sections[section_id]}
    if section_id and section_id in after_state.diagram_outcomes:
        output["diagram_outcomes"] = {section_id: after_state.diagram_outcomes[section_id]}
    if (
        section_id
        and after_state.media_retry_count.get(section_id)
        != before_state.media_retry_count.get(section_id)
    ):
        output["media_retry_count"] = {
            section_id: after_state.media_retry_count.get(section_id, 0)
        }

    if (
        section_id
        and after_state.media_frame_retry_count.get(section_id)
        != before_state.media_frame_retry_count.get(section_id)
    ):
        output["media_frame_retry_count"] = {
            section_id: after_state.media_frame_retry_count.get(section_id, {})
        }

    if before_state.current_media_retry != after_state.current_media_retry:
        output["current_media_retry"] = after_state.current_media_retry

    rerender_updates = _rerender_request_updates(before_state, after_state, section_id)
    if rerender_updates:
        output["rerender_requests"] = rerender_updates

    if (
        section_id
        and after_state.rerender_count.get(section_id)
        != before_state.rerender_count.get(section_id)
    ):
        output["rerender_count"] = {
            section_id: after_state.rerender_count.get(section_id, 0)
        }

    new_errors = after_state.errors[len(before_state.errors) :]
    if new_errors:
        output["errors"] = new_errors

    new_failures = after_state.node_failures[len(before_state.node_failures) :]
    if new_failures:
        output["node_failures"] = new_failures

    return output


def _failure_detail_from_messages(
    *,
    node_name: str,
    section_id: str,
    messages: list[str],
) -> NodeFailureDetail:
    return NodeFailureDetail(
        node=node_name,
        section_id=section_id,
        timestamp=_utc_now_iso(),
        error_type="missing_content",
        error_message=" | ".join(messages) if messages else "Section output missing after node execution.",
        retry_attempt=0,
        will_retry=False,
    )


def _synthetic_failed_section(
    *,
    state: TextbookPipelineState,
    node_name: str,
    section_id: str,
    messages: list[str],
    missing_components: list[str],
) -> FailedSectionRecord:
    plan = state.current_section_plan
    detail = _failure_detail_from_messages(
        node_name=node_name,
        section_id=section_id,
        messages=messages,
    )
    return FailedSectionRecord(
        section_id=section_id,
        title=plan.title if plan is not None else section_id,
        position=plan.position if plan is not None else 0,
        focus=plan.focus if plan is not None else None,
        bridges_from=plan.bridges_from if plan is not None else None,
        bridges_to=plan.bridges_to if plan is not None else None,
        needs_diagram=needs_diagram_from_placements(plan),
        visual_placements_count=count_visual_placements(plan),
        needs_worked_example=plan.needs_worked_example if plan is not None else False,
        failed_at_node=node_name,
        error_type="missing_content",
        error_summary=detail.error_message,
        attempt_count=(state.rerender_count.get(section_id, 0) + 1),
        can_retry=True,
        missing_components=missing_components,
        failure_detail=detail,
    )


def _publish_section_failed(
    *,
    generation_id: str,
    record: FailedSectionRecord,
) -> None:
    publish_runtime_event(
        generation_id,
        SectionFailedEvent(
            generation_id=generation_id,
            section_id=record.section_id,
            title=record.title,
            position=record.position,
            failed_at_node=record.failed_at_node,
            error_type=record.error_type,
            error_summary=record.error_summary,
            focus=record.focus,
            bridges_from=record.bridges_from,
            bridges_to=record.bridges_to,
            needs_diagram=record.needs_diagram,
            visual_placements_count=record.visual_placements_count,
            needs_worked_example=record.needs_worked_example,
            attempt_count=record.attempt_count,
            can_retry=record.can_retry,
            missing_components=record.missing_components,
            failure_detail=record.failure_detail,
        ),
    )


def _merge_parallel_sections(
    *,
    base_state: TextbookPipelineState,
    left: dict[str, SectionContent],
    right: dict[str, SectionContent],
) -> dict[str, SectionContent]:
    merged: dict[str, SectionContent] = {}
    section_ids = set(left) | set(right)
    for section_id in section_ids:
        base_section = (
            right.get(section_id)
            or left.get(section_id)
            or base_state.generated_sections.get(section_id)
        )
        if base_section is None:
            continue
        payload = base_section.model_dump(exclude_none=True)
        if section_id in left:
            payload.update(left[section_id].model_dump(exclude_none=True))
        if section_id in right:
            payload.update(right[section_id].model_dump(exclude_none=True))
        merged[section_id] = SectionContent.model_validate(payload)
    return merged


async def _run_parallel_phase(
    state: TextbookPipelineState,
    *,
    steps: Sequence[NamedSectionStep],
    model_overrides: dict | None = None,
    pre_instrumented: frozenset[str] = frozenset(),
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    generation_id = generation_id_from_state(state)
    attempt, _ = current_section_attempt(state, state.current_section_id)
    base_state = state.model_dump()
    runtime_context = get_runtime_context(config)
    section_id = state.current_section_id

    async def _call(name: str, fn: SectionStep) -> dict:
        if name in pre_instrumented:
            return await _invoke_step(
                fn,
                dict(base_state),
                model_overrides=model_overrides,
                config=config,
            )
        limiter_name = _RESOURCE_LIMITERS.get(name)
        limiter = None
        if (
            runtime_context is not None
            and limiter_name is not None
            and section_id is not None
        ):
            await runtime_context.progress.queue_node(limiter_name, section_id)
            limiter = getattr(runtime_context.limiters, limiter_name)
            await limiter.acquire()
            await runtime_context.progress.start_node(limiter_name, section_id)
        started = perf_counter()
        publish_runtime_event(
            generation_id,
            NodeStartedEvent(
                generation_id=generation_id,
                node=name,
                section_id=section_id,
                attempt=attempt,
            ),
        )
        try:
            result = await _invoke_step(
                fn,
                dict(base_state),
                model_overrides=model_overrides,
                config=config,
            )
        except Exception as exc:
            publish_runtime_event(
                generation_id,
                NodeFinishedEvent(
                    generation_id=generation_id,
                    node=name,
                    section_id=section_id,
                    attempt=attempt,
                    status="failed",
                    latency_ms=(perf_counter() - started) * 1000.0,
                    error=str(exc),
                ),
            )
            if (
                runtime_context is not None
                and limiter_name is not None
                and limiter is not None
                and section_id is not None
            ):
                limiter.release()
                await runtime_context.progress.finish_node(limiter_name, section_id)
            raise
        msgs = node_error_messages(
            result.get("errors"),
            node=name,
            section_id=section_id,
        )
        publish_runtime_event(
            generation_id,
            NodeFinishedEvent(
                generation_id=generation_id,
                node=name,
                section_id=section_id,
                attempt=attempt,
                status="failed" if msgs else "succeeded",
                latency_ms=(perf_counter() - started) * 1000.0,
                error=" | ".join(msgs) if msgs else None,
            ),
        )
        if (
            runtime_context is not None
            and limiter_name is not None
            and limiter is not None
            and section_id is not None
        ):
            limiter.release()
            await runtime_context.progress.finish_node(limiter_name, section_id)
        return result

    results = await asyncio.gather(
        *[_call(name, fn) for name, fn in steps],
        return_exceptions=True,
    )

    merged: dict[str, Any] = {}
    generated_sections: dict[str, SectionContent] = {}
    for (step_name, _), result in zip(steps, results):
        if isinstance(result, Exception):
            merged.setdefault("errors", []).append(
                PipelineError(
                    node=step_name,
                    section_id=state.current_section_id,
                    message=str(result),
                    recoverable=True,
                )
            )
            continue

        for key, value in result.items():
            if key == "generated_sections":
                generated_sections = _merge_parallel_sections(
                    base_state=state,
                    left=generated_sections,
                    right=value,
                )
                merged["generated_sections"] = generated_sections
            elif key in {
                "media_plans",
                "media_slot_results",
                "media_frame_results",
                "media_lifecycle",
                "media_retry_count",
                "media_frame_retry_count",
                "interaction_specs",
                "partial_sections",
                "assembled_sections",
                "section_pending_assets",
                "section_lifecycle",
                "qc_reports",
                "failed_sections",
                "diagram_outcomes",
                "rerender_requests",
                "rerender_count",
            }:
                merged.setdefault(key, {}).update(value)
            elif key == "current_media_retry":
                merged[key] = value
            elif key in {"completed_nodes", "errors", "node_failures"}:
                merged.setdefault(key, []).extend(value)
            else:
                merged[key] = value

    return merged


async def run_section_steps(
    state: TextbookPipelineState | dict,
    *,
    steps: Sequence[NamedSectionStep | SectionStep],
    model_overrides: dict | None = None,
    increment_rerender_count: bool = False,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    Run a section-scoped composite node and publish per-step diagnostics.

    The helper keeps section outputs isolated so concurrent fan-out branches do
    not leak unrelated sections back into LangGraph state.
    """

    before_state = TextbookPipelineState.parse(state)
    raw = before_state.model_dump()
    section_id = before_state.current_section_id
    generation_id = generation_id_from_state(before_state)
    runtime_context = get_runtime_context(config)
    attempt, trigger = current_section_attempt(before_state, section_id)

    if increment_rerender_count and trigger == "rerender" and section_id:
        rerender_count = dict(before_state.rerender_count)
        rerender_count[section_id] = before_state.rerender_count.get(section_id, 0) + 1
        raw["rerender_count"] = rerender_count

    if generation_id and section_id and attempt is not None:
        publish_runtime_event(
            generation_id,
            SectionAttemptStartedEvent(
                generation_id=generation_id,
                section_id=section_id,
                attempt=attempt,
                trigger=trigger,
            ),
        )

    normalized_steps: list[NamedSectionStep] = []
    for step in steps:
        if isinstance(step, tuple):
            normalized_steps.append(step)
        else:
            normalized_steps.append((step.__name__, step))

    completed_node_names: list[str] = []
    for node_name, step in normalized_steps:
        limiter_name = _RESOURCE_LIMITERS.get(node_name)
        limiter = None

        if generation_id:
            if (
                runtime_context is not None
                and limiter_name is not None
                and section_id is not None
            ):
                await runtime_context.progress.queue_node(limiter_name, section_id)
                limiter = getattr(runtime_context.limiters, limiter_name)
                await limiter.acquire()
                await runtime_context.progress.start_node(limiter_name, section_id)
            step_started = perf_counter()
            publish_runtime_event(
                generation_id,
                NodeStartedEvent(
                    generation_id=generation_id,
                    node=node_name,
                    section_id=section_id,
                    attempt=attempt,
                ),
            )
        else:
            step_started = perf_counter()

        try:
            result = await _invoke_step(
                step,
                raw,
                model_overrides=model_overrides,
                config=config,
            )
        except Exception as exc:
            publish_runtime_event(
                generation_id,
                NodeFinishedEvent(
                    generation_id=generation_id,
                    node=node_name,
                    section_id=section_id,
                    attempt=attempt,
                    status="failed",
                    latency_ms=(perf_counter() - step_started) * 1000.0,
                    error=str(exc),
                ),
            )
            if (
                runtime_context is not None
                and limiter_name is not None
                and limiter is not None
                and section_id is not None
            ):
                limiter.release()
                await runtime_context.progress.finish_node(limiter_name, section_id)
            raise

        merge_state_updates(raw, result)
        step_state = TextbookPipelineState.parse(raw)
        completed_node_names.append(node_name)

        step_errors = node_error_messages(
            result.get("errors"),
            node=node_name,
            section_id=section_id,
        )
        publish_runtime_event(
            generation_id,
            NodeFinishedEvent(
                generation_id=generation_id,
                node=node_name,
                section_id=section_id,
                attempt=attempt,
                status="failed" if step_errors else "succeeded",
                latency_ms=(perf_counter() - step_started) * 1000.0,
                error=" | ".join(step_errors) if step_errors else None,
            ),
        )
        if (
            runtime_context is not None
            and limiter_name is not None
            and limiter is not None
            and section_id is not None
        ):
            limiter.release()
            await runtime_context.progress.finish_node(limiter_name, section_id)

        source = _report_source_for(node_name)
        if (
            source is not None
            and generation_id
            and section_id
            and section_id in result.get("qc_reports", {})
        ):
            publish_runtime_event(
                generation_id,
                SectionReportUpdatedEvent(
                    generation_id=generation_id,
                    section_id=section_id,
                    source=source,
                    report=_coerce_report(result["qc_reports"][section_id]),
                ),
            )

        if node_name == "qc_agent" and generation_id:
            for rerender in result.get("rerender_requests", {}).values():
                if rerender is None:
                    continue
                request = _coerce_rerender_request(rerender)
                should_queue_retry = True
                if (
                    runtime_context is not None
                    and should_queue_retry
                ):
                    await runtime_context.progress.queue_retry(request.section_id)
                if should_queue_retry:
                    publish_runtime_event(
                        generation_id,
                        SectionRetryQueuedEvent(
                            generation_id=generation_id,
                            section_id=request.section_id,
                            reason=request.reason,
                            block_type=request.block_type,
                            next_attempt=step_state.rerender_count.get(request.section_id, 0) + 2,
                            max_attempts=step_state.max_rerenders + 1,
                        ),
                    )

        if (
            node_name == "content_generator"
            and section_id
            and section_id not in step_state.generated_sections
        ):
            node_logger = _node_logger(generation_id, section_id, node_name)
            emitted_by_node = section_id in result.get("failed_sections", {})
            record = step_state.failed_sections.get(section_id)
            if record is None:
                record = _synthetic_failed_section(
                    state=step_state,
                    node_name=node_name,
                    section_id=section_id,
                    messages=step_errors,
                    missing_components=list(step_state.contract.required_components),
                )
                step_state.failed_sections[section_id] = record
                raw["failed_sections"] = dict(step_state.failed_sections)
                section_lifecycle = dict(step_state.section_lifecycle)
                section_lifecycle[section_id] = "failed"
                raw["section_lifecycle"] = section_lifecycle
                section_pending_assets = dict(step_state.section_pending_assets)
                section_pending_assets[section_id] = []
                raw["section_pending_assets"] = section_pending_assets
            node_logger.warning(
                "Short-circuiting section %s after content_generator produced no content",
                section_id,
            )
            if not emitted_by_node:
                _publish_section_failed(
                    generation_id=generation_id,
                    record=_coerce_failed_section(record),
                )
            break

        if (
            node_name == "section_assembler"
            and section_id
            and section_id not in step_state.assembled_sections
        ):
            node_logger = _node_logger(generation_id, section_id, node_name)
            pending_assets = step_state.section_pending_assets.get(section_id, [])
            lifecycle = step_state.section_lifecycle.get(section_id)
            if pending_assets and lifecycle in {"partial", "awaiting_assets", "finalizing"}:
                node_logger.info(
                    "Deferring final assembly for section %s while assets are still pending: %s",
                    section_id,
                    pending_assets,
                )
                break
            record = step_state.failed_sections.get(section_id)
            if record is None:
                record = _synthetic_failed_section(
                    state=step_state,
                    node_name=node_name,
                    section_id=section_id,
                    messages=step_errors,
                    missing_components=list(step_state.contract.required_components),
                )
                step_state.failed_sections[section_id] = record
                raw["failed_sections"] = dict(step_state.failed_sections)
                section_lifecycle = dict(step_state.section_lifecycle)
                section_lifecycle[section_id] = "failed"
                raw["section_lifecycle"] = section_lifecycle
                section_pending_assets = dict(step_state.section_pending_assets)
                section_pending_assets[section_id] = []
                raw["section_pending_assets"] = section_pending_assets
            node_logger.warning(
                "Short-circuiting section %s after %s produced no section output",
                section_id,
                node_name,
            )
            _publish_section_failed(generation_id=generation_id, record=_coerce_failed_section(record))
            break

    after_state = TextbookPipelineState.parse(raw)
    return _build_section_output(
        before_state,
        after_state,
        section_id=section_id,
        completed_nodes=completed_node_names,
    )


__all__ = ["run_section_steps", "_run_parallel_phase"]
