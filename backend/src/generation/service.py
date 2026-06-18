from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

import core.events as core_events
from core.events import (
    LLMCallFailedEvent,
    LLMCallStartedEvent,
    LLMCallSucceededEvent,
    TraceClosedEvent,
    TraceRegisteredEvent,
)
from core.auth.jwt_handler import JWTHandler
from core.dependencies import get_jwt_handler, get_settings
from core.ports.generation_engine import GenerationEngine
from pipeline.api import (
    FailedSectionEntry,
    PipelineCommand,
    PipelineDocument,
    PipelinePartialSectionEntry,
    PipelineSectionManifestItem,
)
from pipeline.contracts import get_contract, validate_preset_for_template
from pipeline.events import (
    CompleteEvent,
    ErrorEvent,
    GenerationFailedEvent,
    RuntimeProgressEvent,
    SectionAssetPendingEvent,
    SectionAssetReadyEvent,
    SectionFailedEvent,
    SectionFinalEvent,
    SectionPartialEvent,
    SectionReadyEvent,
    SectionStartedEvent,
)
from pipeline.runtime_context import (
    build_runtime_policy_event,
    get_runtime_context_by_generation,
)
from pipeline.runtime_diagnostics import clear_node_attempts
from pipeline.runtime_policy import (
    resolve_generation_max_concurrent_per_user,
    resolve_generation_timeout_seconds,
)
from pipeline.types.requests import (
    GenerationMode,
    SectionPlan,
    SectionVisualPolicy,
    count_visual_placements,
    needs_diagram_from_placements,
)
from planning.dtos import GenerationSpec
from planning.models import PlanningGenerationSpec, PlanningSectionPlan
from generation.dtos import (
    GenerationAcceptedResponse,
    GenerationRequest,
    GenerationReport,
)
from generation.entities.generation import Generation
from core.entities.student_profile import TeacherProfile
from core.entities.user import User
from generation.ports.document_repository import DocumentRepository
from generation.ports.generation_report_repository import (
    GenerationReportRepository,
)
from generation.ports.generation_repository import GenerationRepository
from core.ports.student_profile_repository import StudentProfileRepository
from core.ports.user_repository import UserRepository
from generation.failure import classify_generation_failure
from generation.logging import GenerationLogger
from generation.dependencies import (
    get_document_repository,
    get_generation_repository,
    get_report_repository,
)
from core.dependencies import (
    get_student_profile_repository,
    get_user_repository,
)
from generation.recovery import (
    INTERRUPTED_GENERATION_ERROR,
    INTERRUPTED_GENERATION_ERROR_CODE,
    INTERRUPTED_GENERATION_ERROR_TYPE,
)
from core.auth.middleware import get_current_user
from telemetry.service import hydrate_report_section_event_fallbacks

logger = logging.getLogger(__name__)

event_bus = core_events.event_bus

router = APIRouter(prefix="/api/v1", tags=["generation"])
_HEARTBEAT_INTERVAL_SECONDS = 30.0


def diag(tag: str, **fields) -> None:
    sys.stderr.write(f"DIAG::{tag}::{json.dumps(fields, default=str)}\n")
    sys.stderr.flush()


def _history_item(generation: Generation) -> dict:
    return {
        "id": generation.id,
        "subject": generation.subject,
        "mode": generation.mode.value,
        "status": generation.status,
        "error_type": generation.error_type,
        "error_code": generation.error_code,
        "requested_template_id": generation.requested_template_id,
        "resolved_template_id": generation.resolved_template_id,
        "requested_preset_id": generation.requested_preset_id,
        "resolved_preset_id": generation.resolved_preset_id,
        "section_count": generation.section_count,
        "quality_passed": generation.quality_passed,
        "generation_time_seconds": generation.generation_time_seconds,
        "created_at": generation.created_at.isoformat() if generation.created_at else None,
        "completed_at": generation.completed_at.isoformat() if generation.completed_at else None,
    }


def _planning_spec_payload(generation: Generation) -> dict | None:
    if not generation.planning_spec_json:
        return None
    try:
        payload = json.loads(generation.planning_spec_json)
        if "mode" not in payload:
            payload["mode"] = generation.mode.value
        source_brief = payload.get("source_brief")
        if isinstance(source_brief, dict) and "mode" not in source_brief:
            source_brief["mode"] = generation.mode.value
        return payload
    except json.JSONDecodeError:
        logger.warning(
            "Generation has invalid planning_spec_json payload",
            extra=_generation_log_extra(generation.id),
        )
        return None


def _planner_peek_payload(report: GenerationReport | None) -> dict:
    if report is None:
        return {
            "runtime_curriculum_outline": [],
            "planner_trace": None,
        }
    return {
        "runtime_curriculum_outline": [
            section.model_dump(mode="json", exclude_none=True)
            if hasattr(section, "model_dump")
            else section
            for section in report.runtime_curriculum_outline
        ],
        "planner_trace": (
            report.planner_trace.model_dump(mode="json", exclude_none=True)
            if report.planner_trace is not None
            else None
        ),
    }


def _detail_item(
    generation: Generation,
    *,
    report: GenerationReport | None = None,
) -> dict:
    _, _, report_url = _generation_urls(generation.id)
    return {
        "id": generation.id,
        "subject": generation.subject,
        "context": generation.context,
        "mode": generation.mode.value,
        "status": generation.status,
        "error": generation.error,
        "error_type": generation.error_type,
        "error_code": generation.error_code,
        "requested_template_id": generation.requested_template_id,
        "resolved_template_id": generation.resolved_template_id,
        "requested_preset_id": generation.requested_preset_id,
        "resolved_preset_id": generation.resolved_preset_id,
        "section_count": generation.section_count,
        "quality_passed": generation.quality_passed,
        "generation_time_seconds": generation.generation_time_seconds,
        "created_at": generation.created_at.isoformat() if generation.created_at else None,
        "completed_at": generation.completed_at.isoformat() if generation.completed_at else None,
        "document_path": generation.document_path,
        "report_url": report_url,
        "planning_spec": _planning_spec_payload(generation),
        **_planner_peek_payload(report),
    }


def _grade_band(profile: TeacherProfile) -> str:
    mapping = {
        "primary": "primary",
        "middle": "secondary",
        "high_school": "secondary",
        "undergraduate": "advanced",
        "adult": "advanced",
    }
    return mapping[profile.default_grade_band.value]


def _generation_urls(generation_id: str) -> tuple[str, str, str]:
    return (
        f"/api/v1/generations/{generation_id}/events",
        f"/api/v1/generations/{generation_id}/document",
        f"/api/v1/generations/{generation_id}/report",
    )


def _pipeline_section_from_planning(
    section: PlanningSectionPlan,
    *,
    always_present: list[str],
    generation_mode: GenerationMode,
) -> SectionPlan:
    selected = list(dict.fromkeys([*always_present, *section.selected_components]))
    bridges_from = None
    bridges_to = None
    needs_diagram = needs_diagram_from_placements(section)
    needs_worked_example = any(component == "worked-example-card" for component in selected)
    interaction_required = any(component == "simulation-block" for component in selected)
    focus = section.focus_note or section.objective or section.rationale or section.title
    computed_diagram_policy = "required" if needs_diagram else "allowed"
    pipeline_visual_policy = (
        SectionVisualPolicy(
            required=section.visual_policy.required,
            intent=section.visual_policy.intent,
            mode=section.visual_policy.mode,
            goal=section.visual_policy.goal,
            style_notes=section.visual_policy.style_notes,
        )
        if section.visual_policy is not None
        else None
    )
    if not focus:
        focus = f"Section {section.order}"
    diag(
        "PIPELINE_SECTION_FROM_PLANNING",
        source="generation_service",
        section_id=section.id,
        title=section.title,
        selected_components=selected,
        planning_visual_policy=(
            section.visual_policy.model_dump() if section.visual_policy else None
        ),
        visual_placements_count=count_visual_placements(section),
        computed_needs_diagram=needs_diagram,
        computed_diagram_policy=computed_diagram_policy,
        pipeline_visual_policy=(
            pipeline_visual_policy.model_dump() if pipeline_visual_policy else None
        ),
    )
    return SectionPlan(
        section_id=section.id,
        title=section.title,
        position=section.order,
        focus=focus,
        role=section.role,
        bridges_from=bridges_from,
        bridges_to=bridges_to,
        needs_diagram=needs_diagram,
        needs_worked_example=needs_worked_example,
        required_components=selected,
        optional_components=[],
        interaction_policy=(
            "disabled"
            if generation_mode == GenerationMode.DRAFT
            else "required" if interaction_required else "allowed"
        ),
        diagram_policy=computed_diagram_policy,
        visual_policy=pipeline_visual_policy,
        transition_note=section.transition_note,
        continuity_notes=section.transition_note or section.rationale,
        terms_to_define=list(section.terms_to_define),
        terms_assumed=list(section.terms_assumed),
        practice_target=section.practice_target,
        visual_placements=list(section.visual_placements),
    )


def _pipeline_sections_from_planning_spec(spec: PlanningGenerationSpec) -> list[SectionPlan]:
    contract = get_contract(spec.template_id)
    always_present = contract.always_present or contract.required_components
    sections = [
        _pipeline_section_from_planning(
            section,
            always_present=always_present,
            generation_mode=spec.mode,
        )
        for section in spec.sections
    ]
    for index, section in enumerate(sections):
        if index > 0:
            section.bridges_from = sections[index - 1].title
        if index + 1 < len(sections):
            section.bridges_to = sections[index + 1].title
    return sections


def _context_from_generation_spec(
    spec: GenerationSpec,
    *,
    subject: str,
) -> str:
    lines = [
        subject,
        f"Audience: {spec.source_brief.audience}",
    ]
    if spec.source_brief.extra_context:
        lines.append(f"Additional context: {spec.source_brief.extra_context}")
    lines.append("")
    lines.append("Reviewed lesson plan:")
    for section in spec.sections:
        suffix = f" [{section.role}]" if section.role else ""
        lines.append(
            f"Section {section.position}: {section.title}{suffix} - {section.focus}"
        )
        if section.continuity_notes:
            lines.append(f"Continuity: {section.continuity_notes}")
    if spec.warning:
        lines.append("")
        lines.append(f"Planning warning: {spec.warning}")
    return "\n".join(lines)


def _context_from_planning_spec(
    spec: PlanningGenerationSpec,
    *,
    subject: str,
) -> str:
    lines = [
        subject,
        f"Audience: {spec.source_brief.audience}",
    ]
    if spec.source_brief.prior_knowledge:
        lines.append(f"Prior knowledge: {spec.source_brief.prior_knowledge}")
    if spec.source_brief.extra_context:
        lines.append(f"Additional context: {spec.source_brief.extra_context}")
    lines.append("")
    lines.append("Reviewed lesson plan:")
    for section in spec.sections:
        suffix = f" [{section.role}]"
        summary = section.focus_note or section.objective or section.rationale
        lines.append(f"Section {section.order}: {section.title}{suffix} - {summary}")
        if section.transition_note:
            lines.append(f"Transition: {section.transition_note}")
    if spec.warning:
        lines.append("")
        lines.append(f"Planning warning: {spec.warning}")
    return "\n".join(lines)


def _effective_generation_spec(req: GenerationRequest) -> GenerationSpec | None:
    return req.generation_spec


def _effective_generation_payload(
    req: GenerationRequest,
) -> tuple[str, str, GenerationMode, str, str, int, list | None, str | None]:
    spec = _effective_generation_spec(req)
    if spec is None:
        return (
            req.subject,
            req.context,
            req.mode,
            req.template_id,
            req.preset_id,
            req.section_count,
            None,
            None,
        )

    return (
        req.subject or spec.source_brief.intent,
        _context_from_generation_spec(
            spec,
            subject=req.subject or spec.source_brief.intent,
        ),
        spec.mode,
        spec.template_id,
        spec.preset_id,
        spec.section_count,
        spec.sections,
        spec.model_dump_json(),
    )


def _progress_updates_for_event(event: dict) -> list[dict]:
    event_type = event.get("type")
    if event_type == "pipeline_start":
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": "planning",
            "label": "Planning lesson structure",
        }]
    if event_type == "section_asset_pending":
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": "awaiting_assets",
            "section_id": event.get("section_id"),
            "label": "Generating media",
        }]
    if event_type == "section_asset_ready":
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": "finalizing_section",
            "section_id": event.get("section_id"),
            "label": "Finalizing section",
        }]
    if event_type == "section_retry_queued":
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": "repairing",
            "section_id": event.get("section_id"),
            "label": "Repairing section",
        }]
    if event_type == "section_attempt_started":
        trigger = event.get("trigger", "initial")
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": "repairing" if trigger == "rerender" else "generating_section",
            "section_id": event.get("section_id"),
            "label": (
                "Repairing section"
                if trigger == "rerender"
                else "Generating section"
            ),
        }]
    if event_type == "qc_complete":
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": "finalizing",
            "label": "Finalizing lesson",
        }]
    if event_type == "complete":
        final_status = event.get("final_status", "completed")
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": (
                "complete"
                if final_status == "completed"
                else "failed" if final_status == "failed" else "finalizing"
            ),
            "label": (
                "Lesson ready"
                if final_status == "completed"
                else "Generation failed"
                if final_status == "failed"
                else "Lesson partially generated"
            ),
        }]
    if event_type == "generation_failed":
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": "failed",
            "label": event.get("message", "Generation failed"),
        }]
    if event_type == "error":
        return [{
            "type": "progress_update",
            "generation_id": event.get("generation_id", ""),
            "stage": "failed",
            "label": event.get("message", "Generation failed"),
        }]
    return []


def _initial_document(
    generation: Generation,
    *,
    section_manifest: list[PipelineSectionManifestItem] | None = None,
    sections: list | None = None,
    partial_sections: list | None = None,
    failed_sections: list | None = None,
    qc_reports: list | None = None,
    status_value: str = "pending",
) -> PipelineDocument:
    now = datetime.now(timezone.utc)
    return PipelineDocument(
        generation_id=generation.id,
        subject=generation.subject,
        context=generation.context,
        mode=generation.mode,
        template_id=generation.requested_template_id,
        preset_id=generation.requested_preset_id,
        status=status_value,
        section_manifest=section_manifest or [],
        sections=sections or [],
        partial_sections=partial_sections or [],
        failed_sections=failed_sections or [],
        qc_reports=qc_reports or [],
        created_at=generation.created_at,
        updated_at=now,
    )


def _sort_sections_by_manifest(
    sections: list,
    section_manifest: list[PipelineSectionManifestItem],
) -> list:
    manifest = _normalize_manifest_items(section_manifest)
    if not manifest:
        return sections

    positions = {item.section_id: item.position for item in manifest}
    fallback_position = len(positions) + 1
    return sorted(
        sections,
        key=lambda section: (
            positions.get(section.section_id, fallback_position),
            section.section_id,
        ),
    )


def _replace_or_append_manifest_item(
    document: PipelineDocument,
    section_id: str,
    title: str,
    position: int,
) -> PipelineDocument:
    manifest = _normalize_manifest_items(document.section_manifest)
    next_item = PipelineSectionManifestItem(
        section_id=section_id,
        title=title,
        position=position,
    )
    for index, existing in enumerate(manifest):
        if existing.section_id == section_id:
            manifest[index] = next_item
            break
    else:
        manifest.append(next_item)

    manifest.sort(key=lambda item: (item.position, item.section_id))
    return document.model_copy(
        update={
            "section_manifest": manifest,
            "updated_at": datetime.now(timezone.utc),
            "status": "running",
        }
    )


def _replace_or_append_section(document: PipelineDocument, section) -> PipelineDocument:
    sections = list(document.sections)
    for index, existing in enumerate(sections):
        if existing.section_id == section.section_id:
            sections[index] = section
            break
    else:
        sections.append(section)
    return document.model_copy(
        update={
            "sections": _sort_sections_by_manifest(sections, document.section_manifest),
            "partial_sections": [
                partial
                for partial in document.partial_sections
                if partial.section_id != section.section_id
            ],
            "failed_sections": [
                failed
                for failed in document.failed_sections
                if failed.section_id != section.section_id
            ],
            "updated_at": datetime.now(timezone.utc),
            "status": "running",
        }
    )


def _sort_partial_sections_by_manifest(
    partial_sections: list[PipelinePartialSectionEntry],
    section_manifest: list[PipelineSectionManifestItem],
) -> list[PipelinePartialSectionEntry]:
    manifest = _normalize_manifest_items(section_manifest)
    if not manifest:
        return partial_sections

    positions = {item.section_id: item.position for item in manifest}
    fallback_position = len(positions) + 1
    return sorted(
        partial_sections,
        key=lambda section: (
            positions.get(section.section_id, fallback_position),
            section.section_id,
        ),
    )


def _replace_or_append_partial_section(
    document: PipelineDocument,
    partial_section,
) -> PipelineDocument:
    entry = (
        partial_section
        if isinstance(partial_section, PipelinePartialSectionEntry)
        else PipelinePartialSectionEntry.model_validate(partial_section)
    )
    partial_sections = list(document.partial_sections)
    for index, existing in enumerate(partial_sections):
        if existing.section_id == entry.section_id:
            partial_sections[index] = entry
            break
    else:
        partial_sections.append(entry)
    return document.model_copy(
        update={
            "partial_sections": _sort_partial_sections_by_manifest(
                partial_sections,
                document.section_manifest,
            ),
            "failed_sections": [
                failed
                for failed in document.failed_sections
                if failed.section_id != entry.section_id
            ],
            "updated_at": datetime.now(timezone.utc),
            "status": "running",
        }
    )


def _update_partial_section_assets(
    document: PipelineDocument,
    *,
    section_id: str,
    pending_assets: list[str],
    visual_mode: str | None = None,
    status_value: str | None = None,
) -> PipelineDocument:
    partial_sections = list(document.partial_sections)
    updated = False
    for index, existing in enumerate(partial_sections):
        if existing.section_id != section_id:
            continue
        partial_sections[index] = existing.model_copy(
            update={
                "pending_assets": list(pending_assets),
                "visual_mode": visual_mode or existing.visual_mode,
                "status": status_value or ("awaiting_assets" if pending_assets else "partial"),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        updated = True
        break
    if not updated:
        return document
    return document.model_copy(
        update={
            "partial_sections": _sort_partial_sections_by_manifest(
                partial_sections,
                document.section_manifest,
            ),
            "updated_at": datetime.now(timezone.utc),
            "status": "running",
        }
    )


def _remove_partial_section(document: PipelineDocument, section_id: str) -> PipelineDocument:
    partial_sections = [
        partial
        for partial in document.partial_sections
        if partial.section_id != section_id
    ]
    if len(partial_sections) == len(document.partial_sections):
        return document
    return document.model_copy(
        update={
            "partial_sections": partial_sections,
            "updated_at": datetime.now(timezone.utc),
            "status": "running",
        }
    )


def _replace_or_append_failed_section(
    document: PipelineDocument,
    failed_section,
) -> PipelineDocument:
    entry = (
        failed_section
        if isinstance(failed_section, FailedSectionEntry)
        else FailedSectionEntry.model_validate(failed_section)
    )
    failed_sections = list(document.failed_sections)
    for index, existing in enumerate(failed_sections):
        if existing.section_id == entry.section_id:
            failed_sections[index] = entry
            break
    else:
        failed_sections.append(entry)
    failed_sections.sort(key=lambda item: (item.position, item.section_id))
    return document.model_copy(
        update={
            "failed_sections": failed_sections,
            "partial_sections": [
                partial
                for partial in document.partial_sections
                if partial.section_id != entry.section_id
            ],
            "sections": [
                section
                for section in document.sections
                if section.section_id != entry.section_id
            ],
            "updated_at": datetime.now(timezone.utc),
            "status": "running",
        }
    )


def _normalize_manifest_items(section_manifest: list) -> list[PipelineSectionManifestItem]:
    return [
        item
        if isinstance(item, PipelineSectionManifestItem)
        else PipelineSectionManifestItem.model_validate(item)
        for item in section_manifest
    ]


async def _stream_user_from_token(
    request: Request,
    jwt_handler: JWTHandler,
    user_repo: UserRepository,
) -> User:
    token = request.query_params.get("token")
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing stream token",
        )

    try:
        payload = jwt_handler.decode_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await user_repo.find_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def _sse_payload(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


def _generation_log_extra(
    generation_id: str,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {"generation_id": generation_id}
    payload.update(extra)
    return payload


def _log_trace_event(generation_id: str, event) -> None:
    if isinstance(event, LLMCallStartedEvent):
        logger.info(
            "LLM trace started",
            extra=_generation_log_extra(
                generation_id,
                trace_id=event.trace_id,
                node=event.node,
                section_id=event.section_id or "-",
                attempt=event.attempt,
                family=event.family or "-",
                model_name=event.model_name or "-",
                endpoint_host=event.endpoint_host or "-",
            ),
        )
        return

    if isinstance(event, LLMCallSucceededEvent):
        logger.info(
            "LLM trace succeeded",
            extra=_generation_log_extra(
                generation_id,
                trace_id=event.trace_id,
                node=event.node,
                section_id=event.section_id or "-",
                attempt=event.attempt,
                latency_ms=event.latency_ms,
                tokens_in=event.tokens_in,
                tokens_out=event.tokens_out,
                cost_usd=event.cost_usd,
                family=event.family or "-",
                model_name=event.model_name or "-",
                endpoint_host=event.endpoint_host or "-",
            ),
        )
        return

    if isinstance(event, LLMCallFailedEvent):
        logger.warning(
            "LLM trace failed",
            extra=_generation_log_extra(
                generation_id,
                trace_id=event.trace_id,
                node=event.node,
                section_id=event.section_id or "-",
                attempt=event.attempt,
                retryable=event.retryable,
                latency_ms=event.latency_ms,
                family=event.family or "-",
                model_name=event.model_name or "-",
                endpoint_host=event.endpoint_host or "-",
                error=event.error,
            ),
        )




def _generation_job_timeout(section_count: int) -> float:
    """Compute generation timeout based on section count.

    Formula: 120 + 90 * N, capped at 720s.
    1 section â†’ 210s, 2 â†’ 300s, 4 â†’ 480s, 7+ â†’ 720s.
    """
    return resolve_generation_timeout_seconds(get_settings(), section_count)
_SSE_KEEPALIVE_TIMEOUT_SECONDS = 15.0
_GENERATION_TIMEOUT_ERROR_CODE = "generation_timeout"
_ORPHANED_GENERATION_ERROR_CODE = "orphaned_generation"
_ORPHANED_GENERATION_ERROR_MESSAGE = "Pipeline ended without completion."


async def _update_generation_heartbeat(
    gen_repo: GenerationRepository,
    generation_id: str,
) -> None:
    await gen_repo.update_heartbeat(generation_id)


async def _heartbeat_loop(
    gen_repo: GenerationRepository,
    generation_id: str,
) -> None:
    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)
        await _update_generation_heartbeat(gen_repo, generation_id)


def _complete_event(
    generation_id: str,
    *,
    final_status: str = "completed",
    quality_passed: bool | None = None,
    completed_sections: int | None = None,
    total_sections: int | None = None,
) -> CompleteEvent:
    _, document_url, report_url = _generation_urls(generation_id)
    return CompleteEvent(
        generation_id=generation_id,
        final_status=(
            "failed"
            if final_status == "failed"
            else "partial" if final_status == "partial" else "completed"
        ),
        quality_passed=quality_passed,
        completed_sections=completed_sections,
        total_sections=total_sections,
        document_url=document_url,
        report_url=report_url,
    )


def _error_event(generation_id: str, message: str) -> ErrorEvent:
    _, _, report_url = _generation_urls(generation_id)
    return ErrorEvent(
        generation_id=generation_id,
        message=message,
        report_url=report_url,
    )


def _generation_failed_event(
    generation_id: str,
    *,
    message: str,
    error_type: str | None = None,
    error_code: str | None = None,
) -> GenerationFailedEvent:
    _, _, report_url = _generation_urls(generation_id)
    return GenerationFailedEvent(
        generation_id=generation_id,
        message=message,
        error_type=error_type,
        error_code=error_code,
        report_url=report_url,
    )


async def _emit_event_payloads(event_payload: dict) -> AsyncIterator[str]:
    yield _sse_payload(event_payload)
    for progress_update in _progress_updates_for_event(event_payload):
        yield _sse_payload(progress_update)


def _terminal_event_payloads(
    generation: Generation | None,
    generation_id: str,
) -> list[dict] | None:
    if generation is None:
        return None
    if generation.status in {"completed", "partial"}:
        return [
            _complete_event(
                generation_id,
                final_status=generation.status,
                quality_passed=generation.quality_passed,
            ).model_dump(mode="json", exclude_none=True)
        ]
    if generation.status == "failed":
        return [
            _generation_failed_event(
                generation_id,
                message=generation.error or "Generation failed",
                error_type=generation.error_type,
                error_code=generation.error_code,
            ).model_dump(mode="json", exclude_none=True),
            _error_event(
                generation_id,
                generation.error or "Generation failed",
            ).model_dump(mode="json", exclude_none=True),
        ]
    return None


async def _stream_generation_events(
    *,
    generation_id: str,
    gen_repo: GenerationRepository,
) -> AsyncIterator[str]:
    queue = core_events.event_bus.subscribe(generation_id)
    try:
        current = await gen_repo.find_by_id(generation_id)
        runtime_context = get_runtime_context_by_generation(generation_id)
        if runtime_context is not None:
            policy_payload = build_runtime_policy_event(runtime_context).model_dump(
                mode="json",
                exclude_none=True,
            )
            async for payload in _emit_event_payloads(policy_payload):
                yield payload
            progress_payload = RuntimeProgressEvent(
                generation_id=generation_id,
                snapshot=await runtime_context.progress.snapshot(),
            ).model_dump(mode="json", exclude_none=True)
            async for payload in _emit_event_payloads(progress_payload):
                yield payload

        while not queue.empty():
            event = queue.get_nowait()
            async for payload in _emit_event_payloads(event):
                yield payload
            if event.get("type") in {"complete", "error"}:
                return

        terminal_payloads = _terminal_event_payloads(current, generation_id)
        if terminal_payloads is not None:
            for terminal in terminal_payloads:
                async for payload in _emit_event_payloads(terminal):
                    yield payload
            return

        while True:
            try:
                event = await asyncio.wait_for(
                    queue.get(),
                    timeout=_SSE_KEEPALIVE_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                current = await gen_repo.find_by_id(generation_id)
                terminal_payloads = _terminal_event_payloads(current, generation_id)
                if terminal_payloads is not None:
                    for terminal in terminal_payloads:
                        async for payload in _emit_event_payloads(terminal):
                            yield payload
                    return
                yield ": keep-alive\n\n"
                continue

            async for payload in _emit_event_payloads(event):
                yield payload
            if event["type"] in {"complete", "error"}:
                break
    finally:
        core_events.event_bus.unsubscribe(generation_id, queue)


def _failed_document_snapshot(
    document: PipelineDocument,
    *,
    error_message: str,
    completed_at: datetime,
) -> PipelineDocument:
    return document.model_copy(
        update={
            "status": "failed",
            "quality_passed": False,
            "error": error_message,
            "updated_at": completed_at,
            "completed_at": completed_at,
        }
    )


async def _persist_failed_generation_state(
    *,
    generation: Generation,
    gen_repo: GenerationRepository,
    document_repo: DocumentRepository,
    document: PipelineDocument,
    error_message: str,
    error_type: str,
    error_code: str | None,
    generation_time_seconds: float | None,
) -> PipelineDocument:
    completed_at = datetime.now(timezone.utc)
    failed_document = _failed_document_snapshot(
        document,
        error_message=error_message,
        completed_at=completed_at,
    )
    document_path = await document_repo.save_document(failed_document)
    await gen_repo.update_status(
        generation.id,
        status="failed",
        document_path=document_path,
        error=error_message,
        error_type=error_type,
        error_code=error_code,
        quality_passed=False,
        generation_time_seconds=generation_time_seconds,
    )
    return failed_document


async def _run_generation_job(
    generation: Generation,
    command: PipelineCommand,
    engine: GenerationEngine,
    gen_repo: GenerationRepository,
    document_repo: DocumentRepository,
    report_repo: GenerationReportRepository,
    initial_document: PipelineDocument,
) -> None:
    _ = report_repo
    job_logger = GenerationLogger(
        generation_id=generation.id,
        user_id=generation.user_id,
    )
    document = initial_document.model_copy(
        update={"status": "running", "updated_at": datetime.now(timezone.utc)}
    )
    started = perf_counter()
    heartbeat_task: asyncio.Task[None] | None = None
    saw_pipeline_progress = False

    async def on_event(event) -> None:
        nonlocal document, saw_pipeline_progress
        if isinstance(event, SectionStartedEvent):
            saw_pipeline_progress = True
            document = _replace_or_append_manifest_item(
                document,
                section_id=event.section_id,
                title=event.title,
                position=event.position,
            )
            await document_repo.save_document(document)
        if isinstance(event, SectionPartialEvent):
            saw_pipeline_progress = True
            document = _replace_or_append_partial_section(
                document,
                PipelinePartialSectionEntry(
                    section_id=event.section_id,
                    template_id=event.template_id,
                    content=event.section,
                    status=event.status,
                    visual_mode=event.visual_mode,
                    pending_assets=list(event.pending_assets),
                    updated_at=event.updated_at,
                ),
            )
            await document_repo.save_document(document)
        if isinstance(event, SectionAssetPendingEvent):
            saw_pipeline_progress = True
            document = _update_partial_section_assets(
                document,
                section_id=event.section_id,
                pending_assets=list(event.pending_assets),
                visual_mode=event.visual_mode,
                status_value=event.status,
            )
            await document_repo.save_document(document)
        if isinstance(event, SectionAssetReadyEvent):
            saw_pipeline_progress = True
            document = _update_partial_section_assets(
                document,
                section_id=event.section_id,
                pending_assets=list(event.pending_assets),
                visual_mode=event.visual_mode,
                status_value="finalizing" if not event.pending_assets else "awaiting_assets",
            )
            await document_repo.save_document(document)
        if isinstance(event, SectionFinalEvent):
            saw_pipeline_progress = True
            document = _remove_partial_section(document, event.section_id)
            await document_repo.save_document(document)
        if isinstance(event, SectionReadyEvent):
            saw_pipeline_progress = True
            document = _replace_or_append_section(document, event.section)
            await document_repo.save_document(document)
        if isinstance(event, SectionFailedEvent):
            saw_pipeline_progress = True
            document = _replace_or_append_failed_section(
                document,
                FailedSectionEntry(
                    section_id=event.section_id,
                    title=event.title,
                    position=event.position,
                    focus=event.focus,
                    bridges_from=event.bridges_from,
                    bridges_to=event.bridges_to,
                    needs_diagram=event.needs_diagram,
                    visual_placements_count=event.visual_placements_count,
                    needs_worked_example=event.needs_worked_example,
                    failed_at_node=event.failed_at_node,
                    error_type=event.error_type,
                    error_summary=event.error_summary,
                    attempt_count=event.attempt_count,
                    can_retry=event.can_retry,
                    missing_components=list(event.missing_components),
                    failure_detail=event.failure_detail,
                ),
            )
            await document_repo.save_document(document)
        if isinstance(event, (LLMCallStartedEvent, LLMCallSucceededEvent, LLMCallFailedEvent)):
            _log_trace_event(generation.id, event)
        core_events.event_bus.publish(generation.id, event)

    async def finalize_failure(
        *,
        error_message: str,
        error_type: str,
        error_code: str | None,
        generation_time_seconds: float | None,
        ) -> None:
        nonlocal document
        document = await _persist_failed_generation_state(
            generation=generation,
            gen_repo=gen_repo,
            document_repo=document_repo,
            document=document,
            error_message=error_message,
            error_type=error_type,
            error_code=error_code,
            generation_time_seconds=generation_time_seconds,
        )
        core_events.event_bus.publish(
            generation.id,
            _generation_failed_event(
                generation.id,
                message=error_message,
                error_type=error_type,
                error_code=error_code,
            ),
        )
        core_events.event_bus.publish(
            generation.id,
            _error_event(generation.id, error_message),
        )

    timeout_seconds = _generation_job_timeout(command.section_count)

    try:
        job_logger.info(
            "Generation job started template=%s preset=%s sections=%s",
            command.template_id,
            command.preset_id,
            command.section_count,
        )
        document_path = await document_repo.save_document(document)
        await gen_repo.update_status(
            generation.id,
            status="running",
            document_path=document_path,
        )
        await _update_generation_heartbeat(gen_repo, generation.id)
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(gen_repo, generation.id),
            name=f"generation-heartbeat-{generation.id}",
        )

        result = await asyncio.wait_for(
            engine.run_streaming(command, on_event=on_event),
            timeout=timeout_seconds,
        )
        completed_at = datetime.now(timezone.utc)
        final_status = result.document.status
        terminal_error = result.document.error
        document = result.document.model_copy(
            update={
                "created_at": initial_document.created_at,
                "updated_at": completed_at,
                "completed_at": completed_at,
                "status": final_status,
            }
        )
        document_path = await document_repo.save_document(document)
        await gen_repo.update_status(
            generation.id,
            status=final_status,
            document_path=document_path,
            error=terminal_error,
            error_type=(
                "incomplete_generation"
                if final_status == "partial"
                else "pipeline_failed" if final_status == "failed" else None
            ),
            error_code=(
                "generation_partial"
                if final_status == "partial"
                else "generation_failed" if final_status == "failed" else None
            ),
            resolved_template_id=document.template_id,
            resolved_preset_id=document.preset_id,
            quality_passed=document.quality_passed,
            generation_time_seconds=result.generation_time_seconds,
        )
        if final_status == "completed":
            job_logger.info(
                "Generation completed in %.1fs quality_passed=%s",
                result.generation_time_seconds,
                document.quality_passed,
            )
        elif final_status == "partial":
            job_logger.info(
                "Generation partially generated in %.1fs quality_passed=%s",
                result.generation_time_seconds,
                document.quality_passed,
            )
        elif final_status == "failed":
            job_logger.error(
                "Generation failed in %.1fs quality_passed=%s",
                result.generation_time_seconds,
                document.quality_passed,
            )
        else:
            job_logger.info(
                "Generation finished with status=%s in %.1fs quality_passed=%s",
                final_status,
                result.generation_time_seconds,
                document.quality_passed,
            )
        if final_status == "failed":
            core_events.event_bus.publish(
                generation.id,
                _generation_failed_event(
                    generation.id,
                    message=terminal_error or "Generation failed",
                    error_type="pipeline_failed",
                    error_code="generation_failed",
                ),
            )
            core_events.event_bus.publish(
                generation.id,
                _error_event(
                    generation.id,
                    terminal_error or "Generation failed",
                ),
            )
        else:
            core_events.event_bus.publish(
                generation.id,
                _complete_event(
                    generation.id,
                    final_status=final_status,
                    quality_passed=document.quality_passed,
                    completed_sections=len(document.sections),
                    total_sections=len(document.section_manifest) or generation.section_count,
                ),
            )
    except asyncio.TimeoutError:
        job_logger.error(
            "Generation timed out after %.0fs",
            timeout_seconds,
            extra={"timeout_seconds": timeout_seconds},
        )
        # The pipeline may have completed moments before the asyncio timeout fired
        # (race between pipeline finishing and wait_for deadline). If all sections
        # reached a terminal state, treat this as success/partial rather than failure.
        manifest_count = len(document.section_manifest)
        completed_count = len(document.sections)
        failed_count = len(document.failed_sections)
        partial_count = len(document.partial_sections)
        accounted_for = completed_count + failed_count
        all_done = (
            saw_pipeline_progress
            and document.status == "running"
            and
            manifest_count > 0
            and accounted_for >= manifest_count
            and partial_count == 0
        )
        if all_done:
            gen_time = perf_counter() - started
            final_status = "completed" if failed_count == 0 else "partial"
            completed_at = datetime.now(timezone.utc)
            document = document.model_copy(
                update={
                    "status": final_status,
                    "updated_at": completed_at,
                    "completed_at": completed_at,
                }
            )
            document_path = await document_repo.save_document(document)
            await gen_repo.update_status(
                generation.id,
                status=final_status,
                document_path=document_path,
                quality_passed=document.quality_passed,
                generation_time_seconds=gen_time,
            )
            core_events.event_bus.publish(
                generation.id,
                _complete_event(
                    generation.id,
                    final_status=final_status,
                    quality_passed=document.quality_passed,
                    completed_sections=completed_count,
                    total_sections=manifest_count,
                ),
            )
            job_logger.info(
                "Timeout race recovered — pipeline completed just before deadline; "
                "status=%s sections=%d",
                final_status,
                completed_count,
            )
        else:
            try:
                await finalize_failure(
                    error_message=(
                        f"Generation timed out after {int(timeout_seconds)} seconds."
                    ),
                    error_type="runtime_error",
                    error_code=_GENERATION_TIMEOUT_ERROR_CODE,
                    generation_time_seconds=perf_counter() - started,
                )
            except Exception:
                job_logger.exception("Generation failed while finalizing timeout state")
    except asyncio.CancelledError:
        job_logger.warning("Generation was interrupted before completion")
        try:
            await finalize_failure(
                error_message=INTERRUPTED_GENERATION_ERROR,
                error_type=INTERRUPTED_GENERATION_ERROR_TYPE,
                error_code=INTERRUPTED_GENERATION_ERROR_CODE,
                generation_time_seconds=perf_counter() - started,
            )
        except Exception:
            job_logger.exception("Generation failed while finalizing interrupted state")
    except Exception as exc:
        job_logger.exception("Generation failed", extra={"error": str(exc)})
        classification = classify_generation_failure(exc)
        try:
            await finalize_failure(
                error_message=str(exc),
                error_type=classification.error_type,
                error_code=classification.error_code,
                generation_time_seconds=perf_counter() - started,
            )
        except Exception:
            job_logger.exception("Generation failed while finalizing exception state")
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        clear_node_attempts(generation.id)
        try:
            current = await gen_repo.find_by_id(generation.id)
            if current is not None and current.status in {"pending", "running"}:
                job_logger.error("Generation ended without completion; forcing orphan failure")
                document = await _persist_failed_generation_state(
                    generation=generation,
                    gen_repo=gen_repo,
                    document_repo=document_repo,
                    document=document,
                    error_message=_ORPHANED_GENERATION_ERROR_MESSAGE,
                    error_type="runtime_error",
                    error_code=_ORPHANED_GENERATION_ERROR_CODE,
                    generation_time_seconds=perf_counter() - started,
                )
                core_events.event_bus.publish(
                    generation.id,
                    _error_event(generation.id, _ORPHANED_GENERATION_ERROR_MESSAGE),
                )
        except Exception:
            job_logger.exception("Generation failed during orphan cleanup")
        finally:
            core_events.event_bus.publish(
                generation.id,
                TraceClosedEvent(trace_id=generation.id, source="generation"),
            )


def _validate_template_and_preset(template_id: str, preset_id: str) -> None:
    try:
        get_contract(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not validate_preset_for_template(template_id, preset_id):
        raise HTTPException(
            status_code=400,
            detail=f"Preset '{preset_id}' is not allowed for template '{template_id}'",
        )


async def enqueue_generation(
    *,
    current_user: User,
    profile: TeacherProfile | None,
    engine: GenerationEngine,
    gen_repo: GenerationRepository,
    document_repo: DocumentRepository,
    report_repo: GenerationReportRepository,
    subject: str,
    context: str,
    mode: GenerationMode,
    template_id: str,
    preset_id: str,
    section_count: int,
    section_plans: list | None,
    planning_spec_json: str | None,
) -> GenerationAcceptedResponse:
    _validate_template_and_preset(template_id, preset_id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete your profile first")
    active_generations = await gen_repo.count_active_by_user(current_user.id)
    generation_limit = resolve_generation_max_concurrent_per_user(get_settings())
    if active_generations >= generation_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Maximum {generation_limit} concurrent generations allowed. "
                "Please wait for a running generation to complete."
            ),
        )

    generation_id = str(uuid.uuid4())
    generation = Generation(
        id=generation_id,
        user_id=current_user.id,
        subject=subject,
        context=context,
        mode=mode,
        requested_template_id=template_id,
        requested_preset_id=preset_id,
        section_count=section_count,
        planning_spec_json=planning_spec_json,
    )
    await gen_repo.create(generation)
    initial_document = _initial_document(generation)
    document_path = await document_repo.save_document(initial_document)
    generation.document_path = document_path
    await gen_repo.update_status(
        generation.id,
        status="pending",
        document_path=document_path,
    )
    await gen_repo.update_heartbeat(generation.id)
    logger.info(
        "Generation accepted",
        extra=_generation_log_extra(
            generation.id,
            user_id=current_user.id,
            mode=mode.value,
            template_id=template_id,
            preset_id=preset_id,
            section_count=section_count,
        ),
    )

    command = PipelineCommand(
        generation_id=generation_id,
        subject=subject,
        context=context,
        grade_band=_grade_band(profile),
        mode=mode,
        template_id=template_id,
        preset_id=preset_id,
        learner_fit="general",
        section_count=section_count,
        section_plans=section_plans,
    )

    async def run_generation_job() -> None:
        await _run_generation_job(
            generation,
            command,
            engine,
            gen_repo,
            document_repo,
            report_repo,
            initial_document,
        )

    core_events.event_bus.publish(
        generation.id,
        TraceRegisteredEvent(
            trace_id=generation.id,
            user_id=current_user.id,
            source="generation",
        ),
    )
    asyncio.create_task(run_generation_job())

    events_url, document_url, report_url = _generation_urls(generation_id)
    return GenerationAcceptedResponse(
        generation_id=generation_id,
        status="pending",
        events_url=events_url,
        document_url=document_url,
        report_url=report_url,
    )


@router.post("/generations", status_code=202, response_model=GenerationAcceptedResponse)
async def create_generation(
    req: GenerationRequest,
    current_user: User = Depends(get_current_user),
    profile_repo: StudentProfileRepository = Depends(get_student_profile_repository),
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    report_repo: GenerationReportRepository = Depends(get_report_repository),
):
    (
        effective_subject,
        effective_context,
        effective_mode,
        effective_template_id,
        effective_preset_id,
        effective_section_count,
        effective_section_plans,
        planning_spec_json,
    ) = _effective_generation_payload(req)

    profile = await profile_repo.find_by_user_id(current_user.id)
    return await enqueue_generation(
        current_user=current_user,
        profile=profile,
        gen_repo=gen_repo,
        document_repo=document_repo,
        report_repo=report_repo,
        subject=effective_subject,
        context=effective_context,
        mode=effective_mode,
        template_id=effective_template_id,
        preset_id=effective_preset_id,
        section_count=effective_section_count,
        section_plans=effective_section_plans,
        planning_spec_json=planning_spec_json,
    )


@router.get("/generations")
async def list_generations(
    current_user: User = Depends(get_current_user),
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    limit: int = get_settings().default_pagination_limit,
    offset: int = 0,
):
    generations = await gen_repo.list_by_user(current_user.id, limit=limit, offset=offset)
    return [_history_item(generation) for generation in generations]


@router.get("/generations/{generation_id}")
async def get_generation_detail(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    report_repo: GenerationReportRepository = Depends(get_report_repository),
):
    generation = await gen_repo.find_by_id(generation_id)
    if generation is None or generation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    try:
        report = await report_repo.load_report(generation_id)
    except (FileNotFoundError, KeyError):
        report = None
    return _detail_item(generation, report=report)


@router.get("/generations/{generation_id}/document")
async def get_generation_document(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
):
    generation = await gen_repo.find_by_id(generation_id)
    if generation is None or generation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    document_ref = generation.document_path or generation.id
    try:
        document = await document_repo.load_document(document_ref)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    return document.model_dump(mode="json", exclude_none=True)


@router.get("/generations/{generation_id}/report")
async def get_generation_report(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    report_repo: GenerationReportRepository = Depends(get_report_repository),
):
    generation = await gen_repo.find_by_id(generation_id)
    if generation is None or generation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    try:
        report = await report_repo.load_report(generation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    report = hydrate_report_section_event_fallbacks(report)
    return report.model_dump(mode="json", exclude_none=True)


@router.get("/generations/{generation_id}/events")
async def get_generation_events(
    generation_id: str,
    request: Request,
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    user_repo: UserRepository = Depends(get_user_repository),
):
    current_user = await _stream_user_from_token(request, jwt_handler, user_repo)
    generation = await gen_repo.find_by_id(generation_id)
    if generation is None or generation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")

    return StreamingResponse(
        _stream_generation_events(
            generation_id=generation_id,
            gen_repo=gen_repo,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
