from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from sqlalchemy import select
from starlette.background import BackgroundTask

from core.auth.jwt_handler import JWTHandler
from core.auth.middleware import get_current_user
from core.database.models import GenerationModel
from core.database.session import async_session_factory
from core.dependencies import get_jwt_handler, get_settings
from core.entities.user import User
from core.llm.runner import RetryPolicy, run_llm
from v3_blueprint.models import ProductionBlueprint
from v3_blueprint.planning.assembler import assemble_blueprint
from v3_blueprint.planning.models import (
    BlueprintAssemblyBlocked,
    SectionBrief,
    Stage1PlanFailure,
    StructuralPlan,
)
from v3_blueprint.planning.persistence import (
    load_chunked_state,
    persist_chunked_state,
    resume_stage2,
)
from v3_blueprint.planning.retry import (
    retry_failed_section,
    run_stage1_with_retry,
)
from v3_execution.config import get_v3_model, get_v3_slot, get_v3_spec
from v3_execution.config.timeouts import V3_TIMEOUTS
from v3_execution.runtime.runner import sse_event_stream

from generation.v3_studio.agents import (
    _validate_blueprint,
    adjust_production_blueprint,
    extract_signals,
)
from generation.pdf_export.cleanup import cleanup_files
from generation.pdf_export.rendering.playwright import PDFRenderError
from generation.pdf_export.service import PDFExportRequest, export_v3_studio_pdf
from generation.v3_studio.dtos import (
    AdjustBlueprintRequest,
    BlueprintPreviewDTO,
    V3ChunkedPlanStartRequest,
    V3ChunkedPlanStateDTO,
    V3ChunkedRegenerateRequest,
    V3ChunkedRetrySectionRequest,
    V3GenerationDetailDTO,
    V3GenerationHistoryItemDTO,
    V3GenerateStartRequest,
    V3GenerateStartResponse,
    V3InputForm,
    V3PdfExportRequest,
    V3SignalSummary,
)
from resource_specs.loader import get_spec, list_spec_ids
from resource_specs.renderer import render_spec_for_prompt
from generation.v3_studio.preview_mapper import blueprint_to_preview_dto
from generation.v3_studio.generation_writer import V3GenerationWriter
from generation.v3_studio.planning_artifact import build_planning_artifact
from generation.v3_studio.session_store import v3_studio_store
from telemetry.dependencies import get_v3_trace_repository
from telemetry.service import telemetry_monitor
from telemetry.v3_trace.repository import V3TraceRepository
from telemetry.v3_trace.writer import V3TraceWriter

logger = logging.getLogger(__name__)

_CALLER = "v3_studio"
v3_studio_router = APIRouter(prefix="/v3", tags=["v3-studio"])
_chunked_stage2_tasks: dict[str, asyncio.Task[None]] = {}


class V3NarrowRequest(BaseModel):
    model_config = {"extra": "forbid"}

    topic: str
    grade_level: str
    subject: str


class V3SubtopicCandidate(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    title: str
    description: str


class V3NarrowResponse(BaseModel):
    model_config = {"extra": "forbid"}

    candidates: list[V3SubtopicCandidate]


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if isinstance(dt, datetime) else None


def _document_section_count(document_json: Any) -> int:
    if not isinstance(document_json, dict):
        return 0
    sections = document_json.get("sections")
    if not isinstance(sections, list):
        return 0
    return len([section for section in sections if isinstance(section, dict)])


def _booklet_status(model: GenerationModel) -> str:
    if isinstance(model.report_json, dict):
        value = model.report_json.get("booklet_status")
        if isinstance(value, str) and value:
            return value
    if isinstance(model.document_json, dict):
        value = model.document_json.get("status")
        if isinstance(value, str) and value:
            return value
    return "streaming_preview"


def _generation_title(model: GenerationModel) -> str:
    if isinstance(model.context, str) and model.context.strip():
        return model.context.strip()
    if isinstance(model.report_json, dict):
        candidate = model.report_json.get("title")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return model.subject


def _template_id(model: GenerationModel) -> str:
    return (
        model.resolved_template_id
        or model.requested_template_id
        or "guided-concept-path"
    )


def _render_chunked_sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _normalize_chunked_state(generation_id: str, state: dict[str, Any]) -> V3ChunkedPlanStateDTO:
    next_action: str | None = None
    stage = str(state.get("stage") or "unknown")
    context = state.get("context")
    signals = context.get("signals") if isinstance(context, dict) else None
    if stage == "plan_ready":
        next_action = "approve_or_regenerate"
    elif stage == "stage2_running":
        next_action = "wait_for_stage2"
    elif stage == "assembly_blocked":
        next_action = "retry_failed_sections"
    elif stage == "blueprint_ready":
        next_action = "generation_running"
    elif stage == "complete":
        next_action = "done"

    return V3ChunkedPlanStateDTO(
        generation_id=generation_id,
        stage=stage,
        structural_plan=state.get("structural_plan")
        if isinstance(state.get("structural_plan"), dict)
        else None,
        section_briefs=state.get("section_briefs")
        if isinstance(state.get("section_briefs"), dict)
        else {},
        failed_sections=[
            str(section)
            for section in state.get("failed_sections", [])
            if isinstance(section, str)
        ]
        if isinstance(state.get("failed_sections"), list)
        else [],
        blueprint_id=state.get("blueprint_id")
        if isinstance(state.get("blueprint_id"), str)
        else None,
        execution_started=bool(state.get("execution_started") is True),
        next_action=next_action,
        inferred_lesson_mode=signals.get("inferred_lesson_mode")
        if isinstance(signals, dict) and isinstance(signals.get("inferred_lesson_mode"), str)
        else None,
        lesson_mode_confidence=signals.get("lesson_mode_confidence")
        if isinstance(signals, dict) and isinstance(signals.get("lesson_mode_confidence"), str)
        else None,
    )


def _build_chunked_resource_spec(
    *,
    resource_type: str,
    duration_minutes: int,
) -> dict[str, Any]:
    resource_type = resource_type.lower().strip().replace(" ", "_")
    if resource_type not in list_spec_ids():
        resource_type = "lesson"
    depth = "quick" if duration_minutes < 20 else "deep" if duration_minutes > 45 else "standard"

    try:
        spec = get_spec(resource_type)
        rendered = render_spec_for_prompt(
            spec,
            depth=depth,
            active_roles=[],
            active_supports=[],
        )
        return {
            "resource_type": resource_type,
            "depth": depth,
            "spec": spec.model_dump(mode="json"),
            "rendered": rendered,
        }
    except Exception:
        return {
            "resource_type": resource_type,
            "depth": depth,
            "spec": {},
            "rendered": (
                f"Resource type: {resource_type}\n"
                "(Resource spec unavailable for this type - use judgment based on resource intent.)"
            ),
        }


@v3_studio_router.post("/signals", response_model=V3SignalSummary)
async def post_signals(
    body: V3InputForm,
    current_user: User = Depends(get_current_user),
) -> V3SignalSummary:
    _ = current_user
    return await extract_signals(body, trace_id=str(uuid.uuid4()))


@v3_studio_router.post("/narrow", response_model=V3NarrowResponse)
async def post_v3_narrow(
    body: V3NarrowRequest,
    current_user: User = Depends(get_current_user),
) -> V3NarrowResponse:
    class NarrowEnvelope(BaseModel):
        candidates: list[V3SubtopicCandidate] = Field(
            default_factory=list
        )

    node = "v3_narrow"
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)

    system = (
        "You break broad lesson topics into focused subtopic candidates. "
        "Each candidate must be teachable in a single 45-60 minute lesson. "
        "Return 3-5 candidates. Each has: id (short slug, no spaces), "
        "title (plain short name), description (one sentence). "
        "Output valid JSON only. No preamble."
    )

    user = (
        f"Topic: {body.topic.strip()}\n"
        f"Grade level: {body.grade_level}\n"
        f"Subject: {body.subject}\n\n"
        "Break this into 3-5 focused subtopics a teacher could build "
        "a single lesson around. Be specific."
    )

    agent = Agent(
        model=model,
        output_type=NarrowEnvelope,
        system_prompt=system,
    )

    try:
        result = await run_llm(
            trace_id=str(uuid.uuid4()),
            caller=_CALLER,
            generation_id=None,
            agent=agent,
            user_prompt=user,
            model=model,
            slot=slot,
            spec=spec,
            section_id=None,
            node=node,
            retry_policy=RetryPolicy(
                call_timeout_seconds=float(
                    V3_TIMEOUTS["narrow"]
                )
            ),
        )
        raw = result.output
        if isinstance(raw, NarrowEnvelope):
            candidates = raw.candidates
        elif hasattr(raw, "candidates"):
            raw_candidates = getattr(raw, "candidates", [])
            candidates = raw_candidates if isinstance(raw_candidates, list) else []
        else:
            candidates = []
    except Exception:
        logger.exception(
            "v3 narrow failed topic=%s user=%s",
            body.topic[:80],
            current_user.id,
        )
        candidates = []

    for i, c in enumerate(candidates):
        if not c.id:
            c.id = f"candidate-{i + 1}"

    return V3NarrowResponse(candidates=candidates[:5])


async def _ensure_chunked_generation_row(
    *,
    generation_id: str,
    user_id: str,
    subject: str,
    context: str,
    section_count: int | None = None,
) -> None:
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        if model is None:
            session.add(
                GenerationModel(
                    id=generation_id,
                    user_id=user_id,
                    subject=subject or "General",
                    context=context or "Chunked plan",
                    mode="v3",
                    status="pending",
                    requested_template_id="guided-concept-path",
                    resolved_template_id="guided-concept-path",
                    requested_preset_id="v3-studio",
                    resolved_preset_id="v3-studio",
                    section_count=section_count,
                )
            )
        else:
            model.user_id = user_id
            model.subject = subject or model.subject
            model.context = context or model.context
            model.mode = "v3"
            model.status = "pending"
            model.requested_template_id = "guided-concept-path"
            model.resolved_template_id = "guided-concept-path"
            model.requested_preset_id = "v3-studio"
            model.resolved_preset_id = "v3-studio"
            if section_count is not None:
                model.section_count = section_count
        await session.commit()


async def _chunked_emit_event(generation_id: str, event: str, payload: dict[str, Any]) -> None:
    queue = await v3_studio_store.get_chunked_queue(generation_id)
    if queue is None:
        return
    await queue.put(_render_chunked_sse(event, payload))


async def _load_owned_generation(
    generation_id: str,
    user_id: str,
) -> GenerationModel:
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        if model is None or model.user_id != user_id:
            raise HTTPException(status_code=404, detail="Generation not found")
        return model


def _section_briefs_from_state(plan: StructuralPlan, state: dict[str, Any]) -> list[SectionBrief]:
    section_briefs_raw = state.get("section_briefs")
    section_briefs_map = section_briefs_raw if isinstance(section_briefs_raw, dict) else {}
    failed_sections = {
        item for item in state.get("failed_sections", [])
        if isinstance(item, str)
    }

    briefs: list[SectionBrief] = []
    for section in plan.sections:
        persisted = section_briefs_map.get(section.id)
        if isinstance(persisted, dict):
            briefs.append(SectionBrief.model_validate(persisted))
            continue

        placeholder = SectionBrief(
            section_id=section.id,
            components=[],
            question_briefs=[],
            visual_strategy=None,
        )
        if section.id in failed_sections:
            placeholder._failed = True
            placeholder._errors = ["Section failed in prior attempt."]
        briefs.append(placeholder)
    return briefs


async def _maybe_mark_chunked_complete(
    generation_id: str,
    *,
    event_type: str,
) -> None:
    if event_type != "resource_finalised":
        return
    try:
        state = await load_chunked_state(generation_id)
    except Exception:  # noqa: BLE001
        return
    if not isinstance(state, dict) or not state:
        return
    await persist_chunked_state(
        generation_id,
        {
            "stage": "complete",
        },
    )


async def _start_generation_from_chunked_blueprint(
    *,
    generation_id: str,
    blueprint_id: str,
    blueprint: ProductionBlueprint,
    form: V3InputForm | None,
    user_id: str,
    queue: asyncio.Queue[str | None],
) -> None:
    trace_repo = get_v3_trace_repository()
    trace_id = str(uuid.uuid4())
    trace_writer = V3TraceWriter(
        repository=trace_repo,
        trace_id=trace_id,
        generation_id=generation_id,
    )
    generation_writer = V3GenerationWriter(async_session_factory)
    template_id = "guided-concept-path"
    try:
        await trace_writer.start_run(
            user_id=user_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
            title=blueprint.metadata.title,
            subject=blueprint.metadata.subject,
        )
        component_count = sum(len(section.components) for section in blueprint.sections)
        visual_required_count = sum(1 for section in blueprint.sections if section.visual_required)
        await trace_writer.record_blueprint_snapshot(
            blueprint_id=blueprint_id,
            template_id=template_id,
            section_count=len(blueprint.sections),
            section_ids=[section.section_id for section in blueprint.sections],
            component_count=component_count,
            visual_required_count=visual_required_count,
            question_count=len(blueprint.question_plan),
        )
        await telemetry_monitor.initialise_v3_recorder(
            generation_id=generation_id,
            user_id=str(user_id),
            blueprint_title=blueprint.metadata.title,
            subject=blueprint.metadata.subject,
            template_id=template_id,
        )
        await generation_writer.upsert_started(
            generation_id=generation_id,
            user_id=user_id,
            subject=blueprint.metadata.subject,
            context=blueprint.metadata.title,
            template_id=template_id,
            section_count=len(blueprint.sections),
            planned_visuals=visual_required_count,
            planned_questions=len(blueprint.question_plan),
            component_count=component_count,
        )
        artifact = build_planning_artifact(
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
            blueprint=blueprint,
            form=form,
            source={"kind": "teacher_approved_blueprint"},
        )
        await generation_writer.write_planning_artifact(
            generation_id=generation_id,
            user_id=user_id,
            artifact=artifact,
        )
        await _chunked_emit_event(
            generation_id,
            "generation_starting",
            {"generation_id": generation_id, "blueprint_id": blueprint_id},
        )
        asyncio.create_task(
            _pump_sse_to_queue(
                queue,
                blueprint=blueprint,
                generation_id=generation_id,
                blueprint_id=blueprint_id,
                template_id=template_id,
                trace_writer=trace_writer,
                generation_writer=generation_writer,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "chunked generation start failed generation_id=%s error=%s",
            generation_id,
            str(exc)[:400],
        )
        await _chunked_emit_event(
            generation_id,
            "generation_warning",
            {"generation_id": generation_id, "message": "Could not start generation."},
        )


async def _ensure_chunked_stream(
    *,
    generation_id: str,
    user_id: str,
    blueprint_id: str,
) -> asyncio.Queue[str | None]:
    existing_owner = await v3_studio_store.get_generation_owner(generation_id)
    if existing_owner is not None and existing_owner != user_id:
        raise HTTPException(status_code=404, detail="Generation not found")
    queue = await v3_studio_store.get_chunked_queue(generation_id)
    if queue is None:
        queue = asyncio.Queue()
    await v3_studio_store.register_chunked_stream(
        user_id=user_id,
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        queue=queue,
    )
    return queue


async def _ensure_generation_stream(
    *,
    generation_id: str,
    user_id: str,
    blueprint_id: str,
) -> asyncio.Queue[str | None]:
    existing_owner = await v3_studio_store.get_generation_owner(generation_id)
    if existing_owner is not None and existing_owner != user_id:
        raise HTTPException(status_code=404, detail="Generation not found")
    queue = await v3_studio_store.get_generation_queue(generation_id)
    if queue is None:
        queue = asyncio.Queue()
    await v3_studio_store.register_generation_stream(
        user_id=user_id,
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        queue=queue,
    )
    return queue


def _decode_chunked_context(
    state: dict[str, Any],
) -> tuple[V3SignalSummary, V3InputForm, dict[str, Any]]:
    context = state.get("context")
    if not isinstance(context, dict):
        raise ValueError("Chunked context is missing.")
    signals_raw = context.get("signals")
    form_raw = context.get("form")
    resource_spec = context.get("resource_spec")
    if not isinstance(signals_raw, dict) or not isinstance(form_raw, dict):
        raise ValueError("Chunked context is incomplete.")
    if not isinstance(resource_spec, dict):
        raise ValueError("Chunked resource_spec is missing.")
    return (
        V3SignalSummary.model_validate(signals_raw),
        V3InputForm.model_validate(form_raw),
        resource_spec,
    )


async def _attempt_chunked_assembly(
    *,
    generation_id: str,
    user_id: str,
    plan: StructuralPlan,
    briefs: list[SectionBrief],
    form: V3InputForm,
    resource_spec: dict[str, Any],
) -> None:
    failed_sections = [
        brief.section_id
        for brief in briefs
        if getattr(brief, "_failed", False)
    ]
    print(
        f"\n[ASSEMBLY ATTEMPT] generation_id={generation_id}"
        f" sections={len(briefs)}",
        flush=True,
    )
    try:
        blueprint = assemble_blueprint(
            plan,
            briefs,
            subject=form.subject.strip() or "General",
            title=form.topic.strip() or "Generated Lesson",
            resource_type=str(resource_spec.get("resource_type") or "lesson"),
        )
    except BlueprintAssemblyBlocked as exc:
        print(
            f"\n[ASSEMBLY BLOCKED] generation_id={generation_id}"
            f" failed_sections={exc.failed_sections}",
            flush=True,
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "assembly_blocked",
                "failed_sections": list(exc.failed_sections),
                "execution_started": False,
            },
        )
        await _chunked_emit_event(
            generation_id,
            "assembly_blocked",
            {
                "generation_id": generation_id,
                "failed_sections": list(exc.failed_sections),
            },
        )
        return

    print(
        f"\n[ASSEMBLY OK] generation_id={generation_id}",
        flush=True,
    )
    _validate_blueprint(blueprint)
    print(
        f"\n[BLUEPRINT VALIDATED] generation_id={generation_id}",
        flush=True,
    )
    blueprint_id = str(uuid.uuid4())
    await v3_studio_store.put_blueprint(
        user_id,
        blueprint_id,
        blueprint,
        "guided-concept-path",
        form=form,
        planning_source={"kind": "teacher_approved_blueprint"},
    )
    print(
        f"\n[EXECUTION QUEUE REGISTERING] generation_id={generation_id}",
        flush=True,
    )
    queue = await _ensure_generation_stream(
        generation_id=generation_id,
        user_id=user_id,
        blueprint_id=blueprint_id,
    )
    print(
        f"\n[EXECUTION QUEUE REGISTERED] generation_id={generation_id}"
        f" queue_exists={queue is not None}",
        flush=True,
    )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "blueprint_ready",
            "blueprint_id": blueprint_id,
            "failed_sections": failed_sections,
            "execution_started": True,
        },
    )
    print(
        f"\n[EXECUTION STARTING] generation_id={generation_id}"
        f" blueprint_id={blueprint_id}",
        flush=True,
    )
    try:
        await _start_generation_from_chunked_blueprint(
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            blueprint=blueprint,
            form=form,
            user_id=user_id,
            queue=queue,
        )
        print(
            f"\n[EXECUTION STARTED] generation_id={generation_id}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        import traceback

        print(
            f"\n[EXECUTION START FAILED] generation_id={generation_id}"
            f" type={type(exc).__name__}"
            f"\nmessage={str(exc)}"
            f"\n{traceback.format_exc()}",
            flush=True,
        )
        raise


async def _run_chunked_stage2_pipeline(
    *,
    generation_id: str,
    user_id: str,
) -> None:
    async def emit_event(event: str, payload: dict[str, Any]) -> None:
        await _chunked_emit_event(generation_id, event, payload)

    print(
        f"\n[STAGE2 PIPELINE START] generation_id={generation_id}",
        flush=True,
    )
    try:
        state = await load_chunked_state(generation_id)
        plan_raw = state.get("structural_plan")
        if not isinstance(plan_raw, dict):
            await persist_chunked_state(
                generation_id,
                {"stage": "assembly_blocked", "failed_sections": []},
            )
            await emit_event(
                "generation_warning",
                {
                    "generation_id": generation_id,
                    "message": "No structural plan found for this chunked generation.",
                },
            )
            return

        plan = StructuralPlan.model_validate(plan_raw)
        signals, form, resource_spec = _decode_chunked_context(state)

        briefs = await resume_stage2(
            generation_id,
            emit_event=emit_event,
        )
        print(
            f"\n[STAGE2 PIPELINE BRIEFS DONE] generation_id={generation_id}"
            f" briefs={len(briefs)}",
            flush=True,
        )
        await _attempt_chunked_assembly(
            generation_id=generation_id,
            user_id=user_id,
            plan=plan,
            briefs=briefs,
            form=form,
            resource_spec=resource_spec,
        )
        print(
            f"\n[STAGE2 PIPELINE ASSEMBLY CALLED] generation_id={generation_id}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        import traceback

        print(
            f"\n[STAGE2 PIPELINE ERROR] generation_id={generation_id}"
            f" type={type(exc).__name__}"
            f"\nmessage={str(exc)}"
            f"\n{traceback.format_exc()}",
            flush=True,
        )
        logger.exception(
            "chunked stage2 pipeline failed generation_id=%s error=%s",
            generation_id,
            str(exc)[:400],
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "assembly_blocked",
                "execution_started": False,
            },
        )
        await _chunked_emit_event(
            generation_id,
            "generation_warning",
            {
                "generation_id": generation_id,
                "message": "Chunked expansion failed. Retry a failed section or regenerate the plan.",
            },
        )
    finally:
        _chunked_stage2_tasks.pop(generation_id, None)
        print(
            f"\n[STAGE2 PIPELINE DONE] generation_id={generation_id}",
            flush=True,
        )


@v3_studio_router.post("/chunked/plan/start", response_model=V3ChunkedPlanStateDTO)
async def post_chunked_plan_start(
    body: V3ChunkedPlanStartRequest,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    generation_id = str(uuid.uuid4())
    form = body.form
    resource_spec = _build_chunked_resource_spec(
        resource_type=form.resource_type,
        duration_minutes=form.duration_minutes,
    )

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=current_user.id,
        subject=form.subject.strip() or "General",
        context=form.topic.strip() or "Chunked plan",
    )
    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=current_user.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "stage1_running",
            "execution_started": False,
            "failed_sections": [],
        },
    )

    async def emit_event(event: str, payload: dict[str, Any]) -> None:
        await _chunked_emit_event(generation_id, event, payload)

    try:
        await run_stage1_with_retry(
            signals=body.signals,
            form=form,
            resource_spec=resource_spec,
            emit_event=emit_event,
            generation_id=generation_id,
            trace_id=str(uuid.uuid4()),
        )
    except Stage1PlanFailure as exc:
        await persist_chunked_state(
            generation_id,
            {
                "stage": "stage1_failed",
                "errors": list(exc.errors),
                "execution_started": False,
            },
        )
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Could not generate a valid lesson plan.",
                "errors": exc.errors,
            },
        ) from exc
    except Exception as exc:  # noqa: BLE001
        import traceback
        tb = traceback.format_exc()
        print(
            f"\n[CHUNKED STAGE1 ERROR] generation_id={generation_id}\n"
            f"type={type(exc).__name__}\n"
            f"message={str(exc)}\n"
            f"traceback:\n{tb}",
            flush=True,
        )
        logger.exception(
            "chunked stage1 failed generation_id=%s type=%s error=%s",
            generation_id,
            type(exc).__name__,
            str(exc)[:800],
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "stage1_failed",
                "errors": [f"{type(exc).__name__}: {str(exc)[:400]}"],
                "execution_started": False,
            },
        )
        raise HTTPException(
            status_code=500,
            detail=f"[{type(exc).__name__}] {str(exc)[:600]}",
        ) from exc

    state = await load_chunked_state(generation_id)
    return _normalize_chunked_state(generation_id, state)


@v3_studio_router.get("/chunked/{generation_id}/status", response_model=V3ChunkedPlanStateDTO)
async def get_chunked_plan_status(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    await _load_owned_generation(generation_id, current_user.id)
    try:
        state = await load_chunked_state(generation_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Chunked state not found") from exc
    return _normalize_chunked_state(generation_id, state)


@v3_studio_router.get("/chunked/{generation_id}/events")
async def get_chunked_generation_events(
    generation_id: str,
    current_user: User = Depends(get_current_user),
):
    owns_stream = await v3_studio_store.owns_generation(current_user.id, generation_id)
    if not owns_stream:
        raise HTTPException(status_code=404, detail="Chunked stream not found")
    queue = await v3_studio_store.get_chunked_queue(generation_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Chunked stream not found")

    async def event_generator():
        finished = False
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    finished = True
                    break
                yield chunk
        finally:
            if finished:
                await v3_studio_store.cleanup_chunked_stream(generation_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@v3_studio_router.post("/chunked/{generation_id}/approve", response_model=V3ChunkedPlanStateDTO)
async def post_chunked_plan_approve(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    await _load_owned_generation(generation_id, current_user.id)
    state = await load_chunked_state(generation_id)
    if not isinstance(state.get("structural_plan"), dict):
        raise HTTPException(status_code=409, detail="Structural plan is not ready yet")

    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=current_user.id,
        blueprint_id=str(state.get("blueprint_id") or f"chunked-plan-{generation_id}"),
    )

    running_task = _chunked_stage2_tasks.get(generation_id)
    if running_task is not None and not running_task.done():
        latest = await load_chunked_state(generation_id)
        return _normalize_chunked_state(generation_id, latest)

    await persist_chunked_state(
        generation_id,
        {
            "stage": "stage2_running",
            "execution_started": False,
        },
    )
    task = asyncio.create_task(
        _run_chunked_stage2_pipeline(
            generation_id=generation_id,
            user_id=current_user.id,
        )
    )
    _chunked_stage2_tasks[generation_id] = task
    latest = await load_chunked_state(generation_id)
    return _normalize_chunked_state(generation_id, latest)


@v3_studio_router.post("/chunked/{generation_id}/regenerate", response_model=V3ChunkedPlanStateDTO)
async def post_chunked_plan_regenerate(
    generation_id: str,
    body: V3ChunkedRegenerateRequest,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    await _load_owned_generation(generation_id, current_user.id)
    state = await load_chunked_state(generation_id)

    signals, form, resource_spec = _decode_chunked_context(state)
    if body.note.strip():
        note_prefix = "Teacher adjustment note:"
        existing = form.free_text.strip()
        note = f"{note_prefix} {body.note.strip()}"
        merged = f"{existing}\n\n{note}" if existing else note
        form = form.model_copy(update={"free_text": merged})

    running_task = _chunked_stage2_tasks.pop(generation_id, None)
    if running_task is not None and not running_task.done():
        running_task.cancel()

    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=current_user.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "stage1_running",
            "section_briefs": {},
            "failed_sections": [],
            "blueprint_id": None,
            "execution_started": False,
            "errors": [],
        },
    )

    async def emit_event(event: str, payload: dict[str, Any]) -> None:
        await _chunked_emit_event(generation_id, event, payload)

    try:
        await run_stage1_with_retry(
            signals=signals,
            form=form,
            resource_spec=resource_spec,
            emit_event=emit_event,
            generation_id=generation_id,
            trace_id=str(uuid.uuid4()),
        )
    except Stage1PlanFailure as exc:
        await persist_chunked_state(
            generation_id,
            {
                "stage": "stage1_failed",
                "errors": list(exc.errors),
                "execution_started": False,
            },
        )
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Could not regenerate a valid lesson plan.",
                "errors": exc.errors,
            },
        ) from exc

    latest = await load_chunked_state(generation_id)
    return _normalize_chunked_state(generation_id, latest)


@v3_studio_router.post("/chunked/{generation_id}/retry-section", response_model=V3ChunkedPlanStateDTO)
async def post_chunked_retry_section(
    generation_id: str,
    body: V3ChunkedRetrySectionRequest,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    await _load_owned_generation(generation_id, current_user.id)
    state = await load_chunked_state(generation_id)
    plan_raw = state.get("structural_plan")
    if not isinstance(plan_raw, dict):
        raise HTTPException(status_code=409, detail="No structural plan available.")
    failed_sections = [
        section for section in state.get("failed_sections", [])
        if isinstance(section, str)
    ]
    if body.section_id not in failed_sections:
        raise HTTPException(status_code=409, detail="Section is not marked as failed.")

    running_task = _chunked_stage2_tasks.get(generation_id)
    if running_task is not None and not running_task.done():
        raise HTTPException(status_code=409, detail="Stage 2 is already running for this generation.")

    plan = StructuralPlan.model_validate(plan_raw)
    signals, form, resource_spec = _decode_chunked_context(state)
    stored_briefs = _section_briefs_from_state(plan, state)

    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=current_user.id,
        blueprint_id=str(state.get("blueprint_id") or f"chunked-plan-{generation_id}"),
    )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "stage2_running",
            "execution_started": False,
        },
    )
    await _chunked_emit_event(
        generation_id,
        "stage2_section_start",
        {
            "generation_id": generation_id,
            "section_id": body.section_id,
        },
    )

    async def emit_event(event: str, payload: dict[str, Any]) -> None:
        await _chunked_emit_event(generation_id, event, payload)

    updated_briefs = await retry_failed_section(
        section_id=body.section_id,
        plan=plan,
        stored_briefs=stored_briefs,
        signals=signals,
        form=form,
        resource_spec=resource_spec,
        emit_event=emit_event,
        generation_id=generation_id,
        trace_id=str(uuid.uuid4()),
    )
    retried = next((brief for brief in updated_briefs if brief.section_id == body.section_id), None)
    if retried is not None and getattr(retried, "_failed", False):
        await _chunked_emit_event(
            generation_id,
            "stage2_section_failed",
            {
                "generation_id": generation_id,
                "section_id": body.section_id,
                "errors": getattr(retried, "_errors", []),
            },
        )
    else:
        await _chunked_emit_event(
            generation_id,
            "stage2_section_done",
            {
                "generation_id": generation_id,
                "section_id": body.section_id,
            },
        )

    failed_after_retry = [
        brief.section_id
        for brief in updated_briefs
        if getattr(brief, "_failed", False)
    ]
    await _chunked_emit_event(
        generation_id,
        "stage2_complete",
        {
            "generation_id": generation_id,
            "failed_sections": failed_after_retry,
        },
    )

    await _attempt_chunked_assembly(
        generation_id=generation_id,
        user_id=current_user.id,
        plan=plan,
        briefs=updated_briefs,
        form=form,
        resource_spec=resource_spec,
    )
    latest = await load_chunked_state(generation_id)
    return _normalize_chunked_state(generation_id, latest)


@v3_studio_router.post("/blueprint/adjust", response_model=BlueprintPreviewDTO)
async def post_blueprint_adjust(
    body: AdjustBlueprintRequest,
    current_user: User = Depends(get_current_user),
) -> BlueprintPreviewDTO:
    stored = await v3_studio_store.get_blueprint(current_user.id, body.blueprint_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    revised = await adjust_production_blueprint(
        stored.blueprint,
        body.adjustment,
        trace_id=str(uuid.uuid4()),
    )
    await v3_studio_store.put_blueprint(
        current_user.id,
        body.blueprint_id,
        revised,
        stored.template_id,
        form=stored.form,
        planning_source=stored.planning_source,
    )
    return blueprint_to_preview_dto(
        blueprint_id=body.blueprint_id,
        blueprint=revised,
        template_id=stored.template_id,
        form=stored.form,
    )


async def _pump_sse_to_queue(
    queue: asyncio.Queue[str | None],
    *,
    blueprint: ProductionBlueprint,
    generation_id: str,
    blueprint_id: str,
    template_id: str,
    trace_writer: V3TraceWriter | None = None,
    generation_writer: V3GenerationWriter | None = None,
) -> None:
    def _parse_sse_chunk(chunk: str) -> tuple[str | None, dict[str, Any] | None]:
        event_type: str | None = None
        data_lines: list[str] = []
        for line in chunk.splitlines():
            if line.startswith("event:"):
                event_type = line.partition(":")[2].strip() or None
            elif line.startswith("data:"):
                data_lines.append(line.partition(":")[2].strip())
        if not data_lines:
            return event_type, None
        try:
            payload = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            return event_type, None
        if not isinstance(payload, dict):
            return event_type, None
        return event_type, payload

    async def _write_generation_snapshot(event_type: str, payload: dict[str, Any]) -> None:
        if generation_writer is None:
            return
        if event_type in {"draft_pack_ready", "draft_status_updated"}:
            await generation_writer.write_draft(generation_id, payload)
            return
        if event_type == "final_pack_ready":
            await generation_writer.write_final(generation_id, payload)
            return
        if event_type == "generation_complete":
            await generation_writer.write_generation_complete(generation_id, payload)
            return
        if event_type == "coherence_report_ready":
            coherence = payload.get("coherence_report")
            if isinstance(coherence, dict):
                await generation_writer.write_coherence_result(generation_id, coherence)
            else:
                await generation_writer.write_coherence_result(generation_id, payload)
            return
        if event_type == "resource_finalised":
            await generation_writer.write_resource_finalised(generation_id, payload)
            return
        if event_type == "generation_warning":
            message = str(payload.get("message") or "Generation warning")
            await generation_writer.write_failure(generation_id, message=message)

    try:
        async for chunk in sse_event_stream(
            blueprint=blueprint,
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
            trace_id=trace_writer.trace_id if trace_writer is not None else generation_id,
            trace_writer=trace_writer,
        ):
            event_type, payload = _parse_sse_chunk(chunk)
            if event_type and payload is not None:
                try:
                    await _write_generation_snapshot(event_type, payload)
                    await _maybe_mark_chunked_complete(
                        generation_id,
                        event_type=event_type,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "v3 generation writer failed generation_id=%s event_type=%s",
                        generation_id,
                        event_type,
                    )
            await queue.put(chunk)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        pass
    finally:
        await queue.put(None)


@v3_studio_router.post("/generate/start", response_model=V3GenerateStartResponse)
async def post_v3_generate_start(
    body: V3GenerateStartRequest,
    current_user: User = Depends(get_current_user),
    trace_repo: V3TraceRepository = Depends(get_v3_trace_repository),
) -> V3GenerateStartResponse:
    existing = await v3_studio_store.get_generation_queue(body.generation_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="generation_id already started")

    stored = await v3_studio_store.get_blueprint(current_user.id, body.blueprint_id)
    template_id = body.template_id
    blueprint: ProductionBlueprint | None = None
    if stored is not None:
        blueprint = stored.blueprint
        template_id = stored.template_id
    elif body.blueprint is not None:
        blueprint = ProductionBlueprint.model_validate(body.blueprint)
    else:
        raise HTTPException(status_code=404, detail="Blueprint not found for user")

    trace_id = str(uuid.uuid4())
    trace_writer = V3TraceWriter(
        repository=trace_repo,
        trace_id=trace_id,
        generation_id=body.generation_id,
    )
    generation_writer = V3GenerationWriter(async_session_factory)
    try:
        await trace_writer.start_run(
            user_id=current_user.id,
            blueprint_id=body.blueprint_id,
            template_id=template_id,
            title=blueprint.metadata.title,
            subject=blueprint.metadata.subject,
        )
        component_count = sum(len(section.components) for section in blueprint.sections)
        visual_required_count = sum(1 for section in blueprint.sections if section.visual_required)
        await trace_writer.record_blueprint_snapshot(
            blueprint_id=body.blueprint_id,
            template_id=template_id,
            section_count=len(blueprint.sections),
            section_ids=[section.section_id for section in blueprint.sections],
            component_count=component_count,
            visual_required_count=visual_required_count,
            question_count=len(blueprint.question_plan),
        )
        await telemetry_monitor.initialise_v3_recorder(
            generation_id=body.generation_id,
            user_id=str(current_user.id),
            blueprint_title=blueprint.metadata.title,
            subject=blueprint.metadata.subject,
            template_id=template_id,
        )
        await generation_writer.upsert_started(
            generation_id=body.generation_id,
            user_id=current_user.id,
            subject=blueprint.metadata.subject,
            context=blueprint.metadata.title,
            template_id=template_id,
            section_count=len(blueprint.sections),
            planned_visuals=visual_required_count,
            planned_questions=len(blueprint.question_plan),
            component_count=component_count,
        )
        artifact = build_planning_artifact(
            generation_id=body.generation_id,
            blueprint_id=body.blueprint_id,
            template_id=template_id,
            blueprint=blueprint,
            form=stored.form if stored is not None else None,
            source=stored.planning_source if stored is not None else None,
        )
        await generation_writer.write_planning_artifact(
            generation_id=body.generation_id,
            user_id=current_user.id,
            artifact=artifact,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "v3 generation start failed generation_id=%s trace_id=%s error=%s",
            body.generation_id,
            trace_id,
            str(exc)[:400],
        )
        raise HTTPException(
            status_code=500,
            detail="Could not start generation.",
        ) from exc

    queue = await _ensure_generation_stream(
        generation_id=body.generation_id,
        user_id=current_user.id,
        blueprint_id=body.blueprint_id,
    )
    asyncio.create_task(
        _pump_sse_to_queue(
            queue,
            blueprint=blueprint,
            generation_id=body.generation_id,
            blueprint_id=body.blueprint_id,
            template_id=template_id,
            trace_writer=trace_writer,
            generation_writer=generation_writer,
        )
    )
    return V3GenerateStartResponse(generation_id=body.generation_id)


@v3_studio_router.get("/generations", response_model=list[V3GenerationHistoryItemDTO])
async def list_v3_generations(
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
) -> list[V3GenerationHistoryItemDTO]:
    generation_writer = V3GenerationWriter(async_session_factory)
    models = await generation_writer.list_by_user(
        current_user.id,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
    )
    items: list[V3GenerationHistoryItemDTO] = []
    for model in models:
        items.append(
            V3GenerationHistoryItemDTO(
                id=model.id,
                subject=model.subject,
                title=_generation_title(model),
                status=model.status,
                booklet_status=_booklet_status(model),
                section_count=int(model.section_count or 0),
                document_section_count=_document_section_count(model.document_json),
                template_id=_template_id(model),
                created_at=_iso(model.created_at),
                completed_at=_iso(model.completed_at),
            )
        )
    return items


@v3_studio_router.get("/generations/{generation_id}", response_model=V3GenerationDetailDTO)
async def get_v3_generation_detail(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> V3GenerationDetailDTO:
    generation_writer = V3GenerationWriter(async_session_factory)
    model = await generation_writer.get_generation_model(generation_id, current_user.id)
    if model is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    artifact = await generation_writer.read_planning_artifact(
        generation_id,
        current_user.id,
    )
    return V3GenerationDetailDTO(
        id=model.id,
        subject=model.subject,
        title=_generation_title(model),
        status=model.status,
        booklet_status=_booklet_status(model),
        template_id=_template_id(model),
        section_count=int(model.section_count or 0),
        document_section_count=_document_section_count(model.document_json),
        report_json=model.report_json if isinstance(model.report_json, dict) else {},
        blueprint_id=artifact.get("blueprint_id") if artifact else None,
        planning_artifact=artifact,
        created_at=_iso(model.created_at),
        completed_at=_iso(model.completed_at),
    )


@v3_studio_router.get("/generations/{generation_id}/supplements/options")
async def get_generation_supplement_options(
    generation_id: str,
    current_user: User = Depends(get_current_user),
):
    _ = generation_id, current_user
    raise HTTPException(status_code=410, detail="Companion resources are parked for Lectio v4.")


@v3_studio_router.post("/generations/{generation_id}/supplements/blueprint")
async def post_generation_supplement_blueprint(
    generation_id: str,
    body: dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    _ = generation_id, body, current_user
    raise HTTPException(status_code=410, detail="Companion resources are parked for Lectio v4.")


@v3_studio_router.get("/generations/{generation_id}/events")
async def get_v3_generation_events(
    generation_id: str,
    current_user: User = Depends(get_current_user),
):
    owns_stream = await v3_studio_store.owns_generation(current_user.id, generation_id)
    if not owns_stream:
        generation_writer = V3GenerationWriter(async_session_factory)
        model = await generation_writer.get_generation_model(generation_id, current_user.id)
        if model is None:
            raise HTTPException(status_code=404, detail="Generation stream not found")
    queue = await v3_studio_store.get_generation_queue(generation_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Generation stream not found")
    stored = await v3_studio_store.get_blueprint_for_generation(generation_id)
    if stored is not None:
        await telemetry_monitor.initialise_v3_recorder(
            generation_id=generation_id,
            user_id=str(current_user.id),
            blueprint_title=stored.blueprint.metadata.title,
            subject=stored.blueprint.metadata.subject,
            template_id=stored.template_id,
        )

    async def event_generator():
        finished = False
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    finished = True
                    break
                yield chunk
        finally:
            if finished:
                await v3_studio_store.cleanup_generation_stream(generation_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@v3_studio_router.get("/generations/{generation_id}/blueprint", response_model=BlueprintPreviewDTO)
async def get_v3_generation_blueprint(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> BlueprintPreviewDTO:
    generation_writer = V3GenerationWriter(async_session_factory)

    artifact = await generation_writer.read_planning_artifact(
        generation_id,
        current_user.id,
    )
    if artifact is not None:
        blueprint = ProductionBlueprint.model_validate(artifact["blueprint"])
        form_raw = artifact.get("form")
        form = V3InputForm.model_validate(form_raw) if isinstance(form_raw, dict) else None
        return blueprint_to_preview_dto(
            blueprint_id=str(artifact["blueprint_id"]),
            blueprint=blueprint,
            template_id=str(artifact.get("template_id") or "guided-concept-path"),
            form=form,
        )

    owner = await v3_studio_store.get_generation_owner(generation_id)
    if owner != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    blueprint_id = await v3_studio_store.get_blueprint_id_for_generation(generation_id)
    stored = await v3_studio_store.get_blueprint_for_generation(generation_id)
    if stored is None or blueprint_id is None:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return blueprint_to_preview_dto(
        blueprint_id=blueprint_id,
        blueprint=stored.blueprint,
        template_id=stored.template_id,
        form=stored.form,
    )


@v3_studio_router.get("/generations/{generation_id}/document")
async def get_v3_generation_document(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    generation_writer = V3GenerationWriter(async_session_factory)
    document_json = await generation_writer.get_document_json(generation_id, current_user.id)
    if document_json is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    sections = document_json.get("sections")
    if not isinstance(sections, list) or not sections:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_json


@v3_studio_router.get("/generations/{generation_id}/print-snapshot")
async def get_v3_print_snapshot(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    if not await v3_studio_store.owns_generation(current_user.id, generation_id):
        raise HTTPException(status_code=404, detail="Generation not found")
    snap = await v3_studio_store.get_print_snapshot(generation_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Print snapshot not available")
    return snap


@v3_studio_router.post("/generations/{generation_id}/export/pdf")
async def post_v3_export_pdf(
    generation_id: str,
    body: V3PdfExportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
):
    generation_writer = V3GenerationWriter(async_session_factory)
    async with async_session_factory() as session:
        result = await session.execute(
            select(GenerationModel).where(GenerationModel.id == generation_id)
        )
        model = result.scalar_one_or_none()
    if model is None or model.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    document_json = await generation_writer.get_document_json(generation_id, current_user.id)
    if document_json is None:
        raise HTTPException(status_code=404, detail="Document not found")
    sections = document_json.get("sections")
    if not isinstance(sections, list) or not sections:
        raise HTTPException(status_code=404, detail="Document not found")
    template_id = (
        model.resolved_template_id
        or model.requested_template_id
        or "guided-concept-path"
    )

    auth_token = jwt_handler.create_access_token(current_user.id, current_user.email)
    pdf_request = PDFExportRequest(
        school_name=body.school_name,
        teacher_name=body.teacher_name,
        date=body.date,
        include_toc=body.include_toc,
        include_answers=body.include_answers,
    )
    try:
        result = await export_v3_studio_pdf(
            generation_id=generation_id,
            user_id=current_user.id,
            title=model.context or model.subject or "Lesson",
            subject=model.subject or "",
            template_id=template_id,
            document_json=document_json,
            auth_token=auth_token,
            request=pdf_request,
            settings=get_settings(),
            request_id=getattr(request.state, "request_id", None),
        )
    except Exception as exc:  # noqa: BLE001
        debug: dict[str, Any] = {}
        if isinstance(exc, PDFRenderError):
            debug = exc.debug
        error_message = f"{type(exc).__name__}: {str(exc)[:300]}"
        try:
            await generation_writer.write_pdf_status(
                generation_id,
                status="failed",
                error=error_message,
                debug=debug,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to persist PDF failure status generation_id=%s",
                generation_id,
            )
        logger.exception("PDF export failed generation_id=%s", generation_id)
        raise HTTPException(
            status_code=500,
            detail={"message": error_message, "debug": debug},
        ) from exc
    try:
        ak_block = document_json.get("answer_key")
        ak_entries = ak_block.get("entries") if isinstance(ak_block, dict) else None
        entry_count = len(ak_entries) if isinstance(ak_entries, list) else 0
        await generation_writer.write_pdf_status(
            generation_id,
            status="completed",
            error=None,
            debug={
                "print_page": result.print_page_debug or {},
                "answer_key_present": isinstance(ak_block, dict),
                "answer_key_entry_count": entry_count,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to persist PDF completion status generation_id=%s",
            generation_id,
        )

    async def _cleanup() -> None:
        cleanup_files(result.cleanup_paths)

    return FileResponse(
        path=result.pdf_path,
        media_type="application/pdf",
        filename=result.filename,
        background=BackgroundTask(_cleanup),
        headers={
            "X-Page-Count": str(result.page_count),
            "X-File-Size": str(result.file_size_bytes),
            "X-Generation-Time-Ms": str(result.generation_time_ms),
        },
    )


def _compact_trace(trace: dict[str, Any]) -> dict[str, Any]:
    report = trace.get("report") or {}
    summary = report.get("summary") if isinstance(report, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    return {
        "trace_id": trace.get("trace_id"),
        "generation_id": trace.get("generation_id"),
        "status": trace.get("status"),
        "title": trace.get("title"),
        "subject": trace.get("subject"),
        "template_id": trace.get("template_id"),
        "booklet_status": report.get("booklet_status"),
        "draft_available": report.get("draft_available"),
        "final_available": report.get("final_available"),
        "classroom_ready": report.get("classroom_ready"),
        "export_allowed": report.get("export_allowed"),
        "summary": summary,
        "events": trace.get("events", []),
    }


@v3_studio_router.get("/generations/{generation_id}/trace")
async def get_v3_generation_trace(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    trace_repo: V3TraceRepository = Depends(get_v3_trace_repository),
) -> dict[str, Any]:
    run = await trace_repo.get_run_by_generation(generation_id)
    if run is None or run.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Trace not found")
    trace = await trace_repo.get_full_trace(run.trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _compact_trace(trace)


@v3_studio_router.get("/traces/{trace_id}")
async def get_v3_trace_by_id(
    trace_id: str,
    current_user: User = Depends(get_current_user),
    trace_repo: V3TraceRepository = Depends(get_v3_trace_repository),
) -> dict[str, Any]:
    run = await trace_repo.get_run(trace_id)
    if run is None or run.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Trace not found")
    trace = await trace_repo.get_full_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _compact_trace(trace)


__all__ = ["v3_studio_router"]
