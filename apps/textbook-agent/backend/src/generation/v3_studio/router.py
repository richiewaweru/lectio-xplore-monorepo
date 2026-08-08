from __future__ import annotations

import asyncio
from copy import deepcopy
import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from sqlalchemy import select, update
from starlette.background import BackgroundTask

from core.auth.jwt_handler import JWTHandler
from core.auth.middleware import get_current_user
from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LearningPackModel,
    PackItemModel,
)
from core.database.session import async_session_factory
from core.dependencies import get_jwt_handler, get_settings
from core.entities.user import User
from core.llm.runner import RetryPolicy, run_llm
from v3_blueprint.models import ProductionBlueprint
from v3_blueprint.planning.assembler import assemble_blueprint
from v3_blueprint.planning.models import (
    BlueprintAssemblyBlocked,
    ConceptCard,
    ItemOption,
    Misconception,
    QuestionBrief,
    SectionBrief,
    Stage1PlanFailure,
    StructuralPlan,
    VariantSpec,
    adapt_legacy_structural_plan,
    core_variant_spec,
    stage2_brief_preview_payload,
)
from v3_blueprint.planning.persistence import (
    append_item_attempt_records,
    load_chunked_state,
    persist_chunked_state,
)
from v3_blueprint.planning.retry import (
    retry_failed_section,
    run_stage1_with_retry,
)
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.timeouts import V3_TIMEOUTS
from v3_execution.config.policy import ship_with_holes_enabled
from v3_execution.compile_orders import compile_execution_bundle
from v3_execution.executors.visual_executor import execute_visual
from v3_execution.executors.item_executor import ItemGenerationResult, execute_items
from v3_execution.executors.section_writer import execute_section
from v3_execution.models import (
    Correction,
    GeneratedComponentBlock,
    GeneratedVisualBlock,
    SectionWriterWorkOrder,
    VisualGeneratorWorkOrder,
)
from v3_execution.runtime.runner import sse_event_stream

from generation.v3_studio.agents import (
    _validate_blueprint,
    adjust_production_blueprint,
    extract_signals,
)
from generation.pdf_export.cleanup import cleanup_files
from generation.pdf_export.rendering.playwright import PDFRenderError
from generation.pdf_export.service import PDFExportRequest, export_v3_studio_pdf
from generation.pdf_export.components.answers_v3 import (
    build_diagnostic_answer_key_content,
)
from generation.v3_studio.dtos import (
    AdjustBlueprintRequest,
    BlueprintPreviewDTO,
    V3ChunkedApproveRequest,
    V3ChunkedPlanDTO,
    V3ChunkedPlanStartRequest,
    V3ChunkedPlanStateDTO,
    V3ChunkedRegenerateRequest,
    V3ChunkedRetrySectionRequest,
    V3ChunkedStatusDTO,
    V3CardItemReviewDTO,
    V3CardLibraryItemDTO,
    V3ConceptCardDTO,
    V3ConceptCardPatchRequest,
    V3ReuseConceptCardRequest,
    V3GenerationDetailDTO,
    V3GenerationHistoryItemDTO,
    V3PackItemDTO,
    V3PackItemOptionDTO,
    V3PackItemPatchRequest,
    V3PackVariantDTO,
    V3XplorePackDTO,
    V3GenerateStartRequest,
    V3GenerateStartResponse,
    V3InputForm,
    V3PdfExportRequest,
    V3ProposeIntentRequest,
    V3ProposeIntentResponse,
    V3SignalSummary,
)
from generation.v3_studio.prompts import PROPOSE_INTENT_SYSTEM, build_propose_intent_user_prompt
from generation.path_preparation import enforce_path_owned_card_objective
from resource_specs.loader import get_spec, list_spec_ids
from resource_specs.renderer import render_spec_for_prompt
from generation.v3_studio.preview_mapper import blueprint_to_preview_dto
from generation.v3_studio.generation_writer import V3GenerationWriter, bump_document_version
from generation.v3_studio.planning_artifact import build_planning_artifact
from generation.v3_studio.session_store import v3_studio_store
from telemetry.dependencies import get_v3_trace_repository
from telemetry.service import telemetry_monitor
from telemetry.v3_trace.repository import V3TraceRepository
from telemetry.v3_trace.writer import V3TraceWriter
from core.events import TraceClosedEvent, TraceRegisteredEvent, event_bus
from v3_execution.llm_helpers import structured_output_type_for_model
from v3_review.card_reviewer import review_card_content

logger = logging.getLogger(__name__)

_CALLER = "v3_studio"
HEARTBEAT_SECONDS = 15
v3_studio_router = APIRouter(prefix="/v3", tags=["v3-studio"])
_chunked_stage2_tasks: dict[str, asyncio.Task[None]] = {}
_visual_regenerate_locks: dict[str, asyncio.Lock] = {}
_snapshot_write_locks: dict[str, asyncio.Lock] = {}
# Fire-and-forget tasks must be retained or the event loop may GC them mid-run.
_background_tasks: set[asyncio.Task[Any]] = set()


def _retain_background_task(task: asyncio.Task[Any]) -> None:
    _background_tasks.add(task)

    def _on_done(done: asyncio.Task[Any]) -> None:
        _background_tasks.discard(done)
        if done.cancelled():
            return
        exc = done.exception()
        if exc is not None:
            logger.error("v3 background task failed", exc_info=exc)

    task.add_done_callback(_on_done)


def _spawn_background_task(coro: Any) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro)
    _retain_background_task(task)
    return task


def _register_pre_generation_trace(*, trace_id: str, user_id: str) -> None:
    event_bus.publish(
        trace_id,
        TraceRegisteredEvent(
            trace_id=trace_id,
            user_id=user_id,
            source="planning",
        ),
    )


def _close_pre_generation_trace(*, trace_id: str) -> None:
    event_bus.publish(
        trace_id,
        TraceClosedEvent(
            trace_id=trace_id,
            source="planning",
        ),
    )


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


class V3VisualRegenerateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    teacher_hint: str | None = Field(default=None, max_length=500)


class V3ComponentPatchRequest(BaseModel):
    model_config = {"extra": "forbid"}

    teacher_instruction: str = Field(min_length=1, max_length=2000)


class V3CardRepairRequest(BaseModel):
    model_config = {"extra": "forbid"}

    correction_hint: str | None = Field(default=None, max_length=2000)


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
    if isinstance(model.report_json, dict):
        planning = model.report_json.get("planning")
        if isinstance(planning, dict):
            display_title = planning.get("display_title")
            if isinstance(display_title, str) and display_title.strip():
                return display_title.strip()
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
    form = context.get("form") if isinstance(context, dict) else None
    display_title = state.get("display_title")
    if not isinstance(display_title, str) or not display_title.strip():
        display_title = form.get("topic") if isinstance(form, dict) else None
    if stage in {"awaiting_review", "plan_ready"}:
        next_action = "approve_or_regenerate"
    elif stage == "stage2_running":
        next_action = "wait_for_stage2"
    elif stage == "variants_running":
        next_action = "wait_for_variants"
    elif stage == "assembly_blocked":
        next_action = "retry_failed_sections"
    elif stage == "stage2_error":
        next_action = "resume_stage2"
    elif stage == "blueprint_ready":
        next_action = "generation_running"
    elif stage == "complete":
        next_action = "done"

    return V3ChunkedPlanStateDTO(
        generation_id=generation_id,
        pack_id=state.get("pack_id") if isinstance(state.get("pack_id"), str) else None,
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
        display_title=display_title.strip() if isinstance(display_title, str) else None,
        error=state.get("error") if isinstance(state.get("error"), str) else None,
        error_type=state.get("error_type") if isinstance(state.get("error_type"), str) else None,
        inferred_lesson_mode=signals.get("inferred_lesson_mode")
        if isinstance(signals, dict) and isinstance(signals.get("inferred_lesson_mode"), str)
        else None,
        lesson_mode_confidence=signals.get("lesson_mode_confidence")
        if isinstance(signals, dict) and isinstance(signals.get("lesson_mode_confidence"), str)
        else None,
        variants=state.get("variants") if isinstance(state.get("variants"), list) else [],
        variant_generation_ids=state.get("variant_generation_ids")
        if isinstance(state.get("variant_generation_ids"), dict)
        else {},
    )


def _normalize_chunked_status(
    generation_id: str,
    state: dict[str, Any],
    document_json: Any,
    *,
    generation_status: str | None = None,
) -> V3ChunkedStatusDTO:
    from planning.whole_lesson.native_status import project_native_status

    full_state = _normalize_chunked_state(generation_id, state)
    progress = document_json.get("progress") if isinstance(document_json, dict) else None
    doc_version = progress.get("updated_at") if isinstance(progress, dict) else None
    if not isinstance(doc_version, str) and isinstance(document_json, dict):
        canonical = json.dumps(document_json, sort_keys=True, separators=(",", ":"), default=str)
        doc_version = f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"

    native = project_native_status(
        generation_id,
        state,
        document_json,
        generation_status=generation_status,
    )
    if native is not None:
        # Prefer monotonic document_revision so pollers see streaming/visual patches.
        revision = native.get("document_revision")
        if revision is not None:
            doc_version = f"rev:{int(revision)}"
        failed_sections = list(native.get("failed_section_ids") or full_state.failed_sections)
        return V3ChunkedStatusDTO(
            generation_id=generation_id,
            pack_id=full_state.pack_id,
            stage=str(native.get("stage") or full_state.stage),
            doc_version=doc_version if isinstance(doc_version, str) else None,
            failed_sections=failed_sections,
            blueprint_id=full_state.blueprint_id,
            execution_started=bool(native.get("execution_started", full_state.execution_started)),
            next_action=native.get("next_action"),
            error=native.get("error") if isinstance(native.get("error"), str) else full_state.error,
            error_type=native.get("error_type")
            if isinstance(native.get("error_type"), str)
            else full_state.error_type,
            variant_generation_ids=full_state.variant_generation_ids,
            document_version=native.get("document_version"),
            document_exists=bool(native.get("document_exists")),
            sections_total=int(native.get("sections_total") or 0),
            sections_ready=int(native.get("sections_ready") or 0),
            sections_failed=int(native.get("sections_failed") or 0),
            blocks_total=int(native.get("blocks_total") or 0),
            blocks_ready=int(native.get("blocks_ready") or 0),
            blocks_failed=int(native.get("blocks_failed") or 0),
            failed_section_ids=list(native.get("failed_section_ids") or []),
            failed_block_ids=list(native.get("failed_block_ids") or []),
            error_detail=native.get("error_detail")
            if isinstance(native.get("error_detail"), dict)
            else None,
        )

    return V3ChunkedStatusDTO(
        generation_id=generation_id,
        pack_id=full_state.pack_id,
        stage=full_state.stage,
        doc_version=doc_version if isinstance(doc_version, str) else None,
        failed_sections=full_state.failed_sections,
        blueprint_id=full_state.blueprint_id,
        execution_started=full_state.execution_started,
        next_action=full_state.next_action,
        error=full_state.error,
        error_type=full_state.error_type,
        variant_generation_ids=full_state.variant_generation_ids,
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
    trace_id = str(uuid.uuid4())
    _register_pre_generation_trace(trace_id=trace_id, user_id=str(current_user.id))
    try:
        return await extract_signals(body, trace_id=trace_id)
    finally:
        _close_pre_generation_trace(trace_id=trace_id)


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
        "title (3-6 words that name the method or approach), description (one sentence). "
        "Each candidate must be a self-contained teachable slice, not a modifier or scope variant "
        "of another candidate. Collapse candidates that differ only by scope into the broader one. "
        "Write each description as: 'Students [verb] [what], using [method/tool].' "
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
        output_type=structured_output_type_for_model(NarrowEnvelope, spec=spec),
        system_prompt=system,
    )

    trace_id = str(uuid.uuid4())
    _register_pre_generation_trace(trace_id=trace_id, user_id=str(current_user.id))

    try:
        result = await run_llm(
            trace_id=trace_id,
            caller=_CALLER,
            generation_id=None,
            agent=agent,
            user_prompt=user,
            model=model,
            slot=slot,
            spec=spec,
            section_id=None,
            node=node,
            model_settings=get_v3_model_settings(node),
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
    finally:
        _close_pre_generation_trace(trace_id=trace_id)

    for i, c in enumerate(candidates):
        if not c.id:
            c.id = f"candidate-{i + 1}"

    return V3NarrowResponse(candidates=candidates[:5])


@v3_studio_router.post("/propose-intent", response_model=V3ProposeIntentResponse)
async def post_v3_propose_intent(
    body: V3ProposeIntentRequest,
    current_user: User = Depends(get_current_user),
) -> V3ProposeIntentResponse:
    node = "v3_propose_intent"
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(V3ProposeIntentResponse, spec=spec),
        system_prompt=PROPOSE_INTENT_SYSTEM,
    )
    user_prompt = build_propose_intent_user_prompt(**body.model_dump())
    trace_id = str(uuid.uuid4())
    _register_pre_generation_trace(trace_id=trace_id, user_id=str(current_user.id))
    try:
        result = await run_llm(
            trace_id=trace_id,
            caller=_CALLER,
            generation_id=None,
            agent=agent,
            user_prompt=user_prompt,
            model=model,
            slot=slot,
            spec=spec,
            section_id=None,
            node=node,
            model_settings=get_v3_model_settings(node),
            retry_policy=RetryPolicy(call_timeout_seconds=float(V3_TIMEOUTS["propose_intent"])),
        )
        return V3ProposeIntentResponse.model_validate(result.output)
    except Exception as exc:
        logger.exception("v3 propose intent failed topic=%s user=%s", body.topic[:80], current_user.id)
        raise HTTPException(status_code=502, detail="Could not draft the lesson intent.") from exc
    finally:
        _close_pre_generation_trace(trace_id=trace_id)


async def _ensure_chunked_generation_row(
    *,
    generation_id: str,
    user_id: str,
    subject: str,
    context: str,
    section_count: int | None = None,
    pack_id: str | None = None,
    pack_resource_id: str | None = None,
    pack_resource_label: str | None = None,
    variant: VariantSpec | None = None,
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
                    pack_id=pack_id,
                    pack_resource_id=pack_resource_id,
                    pack_resource_label=pack_resource_label,
                    variant_label=variant.label if variant is not None else None,
                    variant_spec=variant.model_dump(mode="json") if variant is not None else None,
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
            if pack_id is not None:
                model.pack_id = pack_id
            if pack_resource_id is not None:
                model.pack_resource_id = pack_resource_id
            if pack_resource_label is not None:
                model.pack_resource_label = pack_resource_label
            if variant is not None:
                model.variant_label = variant.label
                model.variant_spec = variant.model_dump(mode="json")
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


async def _resolve_owned_card_scope(
    scope_id: str,
    user_id: str,
) -> tuple[str, str]:
    """Return (card pack id, generation id) for a generation or pack scope."""
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, scope_id)
        if generation is not None and generation.user_id == user_id:
            return generation.pack_id or generation.id, generation.id

        pack = await session.get(LearningPackModel, scope_id)
        if pack is None or pack.user_id != user_id:
            raise HTTPException(status_code=404, detail="Pack not found")
        result = await session.execute(
            select(GenerationModel)
            .where(
                GenerationModel.pack_id == pack.id,
                GenerationModel.user_id == user_id,
            )
            .order_by(GenerationModel.created_at, GenerationModel.id)
            .limit(1)
        )
        generation = result.scalar_one_or_none()
        if generation is None:
            raise HTTPException(status_code=409, detail="Pack has no generation to approve")
        return pack.id, generation.id


def _card_dto(card: ConceptCardModel) -> V3ConceptCardDTO:
    misconceptions = (
        card.misconceptions if isinstance(card.misconceptions, list) else []
    )
    return V3ConceptCardDTO(
        id=card.slug,
        pack_id=card.pack_id,
        title=card.title,
        objective=card.objective,
        prereqs=list(card.prereqs) if isinstance(card.prereqs, list) else [],
        misconceptions=misconceptions,
        no_known_misconceptions=len(misconceptions) == 0,
        teacher_edited=bool(card.teacher_edited),
        source_card_id=card.source_card_id,
        source_pack_id=card.source_pack_id,
    )


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
    display_title: str | None,
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
    effective_title = (display_title or blueprint.metadata.title).strip() or blueprint.metadata.title
    existing_document = await generation_writer.get_document_json(generation_id, user_id) or {}
    existing_progress = existing_document.get("progress") if isinstance(existing_document, dict) else None
    existing_statuses = (
        existing_progress.get("sections") if isinstance(existing_progress, dict) else None
    )
    ready_ids = {
        section_id
        for section_id, status in existing_statuses.items()
        if isinstance(existing_statuses, dict) and status == "ready"
    } if isinstance(existing_statuses, dict) else set()
    preserved_ready_sections = [
        deepcopy(section)
        for section in existing_document.get("sections", [])
        if isinstance(existing_document, dict)
        and isinstance(section, dict)
        and section.get("section_id") in ready_ids
    ]
    try:
        await trace_writer.start_run(
            user_id=user_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
            title=effective_title,
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
            blueprint_title=effective_title,
            subject=blueprint.metadata.subject,
            template_id=template_id,
        )
        await generation_writer.upsert_started(
            generation_id=generation_id,
            user_id=user_id,
            subject=blueprint.metadata.subject,
            context=effective_title,
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
            display_title=effective_title,
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
        _spawn_background_task(
            _pump_sse_to_queue(
                queue,
                blueprint=blueprint,
                generation_id=generation_id,
                blueprint_id=blueprint_id,
                template_id=template_id,
                trace_writer=trace_writer,
                generation_writer=generation_writer,
                preserved_ready_sections=preserved_ready_sections,
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
    display_title: str | None = None,
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
            title=(display_title or form.topic).strip() or "Generated Lesson",
            resource_type=str(resource_spec.get("resource_type") or "lesson"),
            ship_with_holes=ship_with_holes_enabled(),
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
        planning_source={
            "kind": "teacher_approved_blueprint",
            "display_title": (display_title or form.topic).strip() or "Generated Lesson",
        },
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
            display_title=(display_title or form.topic).strip() or "Generated Lesson",
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


async def _generate_shared_pack_items(
    *,
    generation_id: str,
    form: V3InputForm,
    plan: StructuralPlan,
) -> dict[str, Any]:
    """Generate the pack's single diagnostic set from approved cards alone."""
    from v3_execution.executors.item_executor import (
        ITEM_MAX_ATTEMPTS,
        execute_items_with_diagnostics,
    )

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        pack_id = generation.pack_id or generation.id
        rows = await session.execute(
            select(ConceptCardModel)
            .where(ConceptCardModel.pack_id == pack_id)
            .order_by(ConceptCardModel.created_at, ConceptCardModel.id)
        )
        cards = list(rows.scalars())

        existing_rows = await session.execute(
            select(PackItemModel).where(PackItemModel.pack_id == pack_id)
        )
        item_rows = list(existing_rows.scalars())
        ready_card_ids = {
            card.id
            for card in cards
            if len(
                [
                    item
                    for item in item_rows
                    if item.card_id == card.id and not item.stale
                ]
            )
            == 5
        }

    notation = plan.variant_spec().voice.notation
    pending_cards = [row for row in cards if row.id not in ready_card_ids]
    results: list[ItemGenerationResult] = []
    attempts_journal: list[dict[str, Any]] = []
    failed_cards: list[dict[str, Any]] = []
    flushed_attempt_keys: set[tuple[str, str, int]] = set()

    async def _flush_attempts(
        *,
        new_attempts: list[dict[str, Any]] | None = None,
        new_failed: list[dict[str, Any]] | None = None,
    ) -> None:
        batch = list(new_attempts or [])
        pending = [
            dict(row)
            for row in attempts_journal
            if (
                str(row.get("correlation_id") or ""),
                str(row.get("card_id") or ""),
                int(row.get("attempt") or 0),
            )
            not in flushed_attempt_keys
        ]
        to_write = batch + pending
        if not to_write and not new_failed:
            return
        await append_item_attempt_records(
            generation_id,
            attempts=to_write,
            failed_cards=new_failed,
            pack_id=pack_id,
        )
        for row in to_write:
            flushed_attempt_keys.add(
                (
                    str(row.get("correlation_id") or ""),
                    str(row.get("card_id") or ""),
                    int(row.get("attempt") or 0),
                )
            )

    async def _one(row: ConceptCardModel) -> None:
        card = _approved_card_for_items(
            row,
            subject=form.subject,
            level=form.grade_level,
            notation=notation,
        )
        try:
            run = await execute_items_with_diagnostics(
                card,
                generation_id=generation_id,
                max_attempts=ITEM_MAX_ATTEMPTS,
            )
            results.append(run.result)
            attempts_journal.extend(run.attempts)
            await _flush_attempts(new_attempts=list(run.attempts))
        except Exception as exc:  # noqa: BLE001
            journal = list(getattr(exc, "item_attempts", []) or [])
            attempts_journal.extend(journal)
            failed_row = {
                "card_id": row.id,
                "correlation_id": getattr(exc, "item_correlation_id", None),
                "error": str(exc)[:500],
                "attempts": journal,
            }
            failed_cards.append(failed_row)
            await _flush_attempts(new_attempts=journal, new_failed=[failed_row])
            raise

    try:
        if pending_cards:
            await asyncio.gather(*(_one(row) for row in pending_cards))
    finally:
        await _flush_attempts()

    if results:
        await _persist_item_results(pack_id, results)

    review_cards = [
        {
            "card_id": result.card_id,
            "missing_misconceptions": list(result.missing_misconceptions),
            "unmapped_options": result.unmapped_options,
        }
        for result in results
        if result.needs_review or result.unmapped_options
    ]
    return {
        "pack_id": pack_id,
        "generated_card_count": len(results),
        "generated_item_count": sum(len(result.items) for result in results),
        "review_cards": review_cards,
        "attempts": attempts_journal,
        "failed_cards": failed_cards,
        "retry_budget": ITEM_MAX_ATTEMPTS,
    }


def _approved_card_for_items(
    row: ConceptCardModel,
    *,
    subject: str,
    level: str,
    notation: str | None,
) -> ConceptCard:
    misconceptions = [
        Misconception.model_validate(item)
        for item in (row.misconceptions or [])
        if isinstance(item, dict)
    ]
    return ConceptCard(
        id=row.id,
        title=row.title,
        objective=row.objective,
        prereqs=list(row.prereqs or []),
        misconceptions=misconceptions,
    ).with_item_context(
        subject=subject,
        level=level,
        notation=notation,
    )


def _item_row_teacher_edited(row: PackItemModel) -> bool:
    return any(
        isinstance(option, dict) and option.get("teacher_edited") is True
        for option in (row.options or [])
    )


async def _persist_item_results(
    pack_id: str,
    results: list[ItemGenerationResult],
) -> None:
    async with async_session_factory() as session:
        for result in results:
            stored = await session.execute(
                select(PackItemModel).where(
                    PackItemModel.pack_id == pack_id,
                    PackItemModel.card_id == result.card_id,
                )
            )
            existing_rows = {row.id: row for row in stored.scalars()}
            generated_ids: set[str] = set()
            for item in result.items:
                correct = next(option for option in item.options if option.correct)
                db_id = f"{pack_id}:{item.question_id}"
                generated_ids.add(db_id)
                existing = existing_rows.get(db_id)
                if existing is not None and _item_row_teacher_edited(existing):
                    existing.stale = True
                    continue
                payload = {
                    "stem": item.prompt_text,
                    "options": [
                        {
                            **option.model_dump(mode="json"),
                            "teacher_edited": False,
                        }
                        for option in item.options
                    ],
                    "correct_key": correct.key,
                    "diagnoses": {
                        option.key: option.diagnoses
                        for option in item.options
                    },
                    "stale": False,
                }
                if existing is None:
                    session.add(
                        PackItemModel(
                            id=db_id,
                            pack_id=pack_id,
                            card_id=result.card_id,
                            **payload,
                        )
                    )
                else:
                    for field, value in payload.items():
                        setattr(existing, field, value)

            for db_id, existing in existing_rows.items():
                if db_id in generated_ids:
                    continue
                if _item_row_teacher_edited(existing):
                    existing.stale = True
                else:
                    await session.delete(existing)
        await session.commit()


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
    cache_token = None
    native_failure_stage = "item_generation"
    try:
        from core.prompts import (
            bind_prompt_cache,
            reset_prompt_cache,
            resolve_all_prompts,
        )

        async with async_session_factory() as session:
            prompt_texts, prompt_hashes = await resolve_all_prompts(user_id, session)
        cache_token = bind_prompt_cache(prompt_texts)
        try:
            writer = V3GenerationWriter(async_session_factory)
            await writer.record_prompt_hashes(generation_id, prompt_hashes)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to stamp prompt hashes generation_id=%s", generation_id
            )

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

        plan = adapt_legacy_structural_plan(
            plan_raw,
            source=f"generation:{generation_id}",
        )
        variant_raw = state.get("variant_spec")
        if isinstance(variant_raw, dict):
            plan = plan.with_variant(VariantSpec.model_validate(variant_raw))
        signals, form, resource_spec = _decode_chunked_context(state)
        display_title = state.get("display_title")
        if not isinstance(display_title, str) or not display_title.strip():
            display_title = form.topic

        async def _items_job() -> dict[str, Any] | None:
            if state.get("skip_item_generation"):
                return None
            item_summary = await _generate_shared_pack_items(
                generation_id=generation_id,
                form=form,
                plan=plan,
            )
            await persist_chunked_state(
                generation_id,
                {"item_generation": item_summary},
            )
            await emit_event(
                "pack_items_ready",
                {
                    "generation_id": generation_id,
                    **item_summary,
                },
            )
            return item_summary

        # Native whole-lesson path: items → teaching plan → halt for teacher approval.
        # Do not run legacy section briefs, assembly, or component writers.
        from planning.whole_lesson.native_routing import generation_is_native_whole_lesson

        native_whole_lesson = generation_is_native_whole_lesson(state) or (
            int(getattr(plan, "document_contract_version", 1) or 1) >= 2
        )
        if native_whole_lesson:
            await _items_job()
            native_failure_stage = "planning_teaching"
            from planning.whole_lesson.service import run_and_persist_teaching_plan

            async with async_session_factory() as session:
                teaching_summary = await run_and_persist_teaching_plan(
                    session, generation_id, require_items=True
                )
            await persist_chunked_state(
                generation_id,
                {
                    "stage": "awaiting_teaching_approval",
                    "native_whole_lesson": True,
                    "teaching_plan_summary": {
                        "arc": (teaching_summary.get("teaching_plan") or {}).get("arc"),
                        "section_count": len(
                            (teaching_summary.get("teaching_plan") or {}).get("sections")
                            or []
                        ),
                    },
                },
            )
            await emit_event(
                "awaiting_teaching_approval",
                {
                    "generation_id": generation_id,
                    "arc": (teaching_summary.get("teaching_plan") or {}).get("arc"),
                },
            )
            print(
                f"\n[STAGE2 NATIVE TEACHING HALT] generation_id={generation_id}",
                flush=True,
            )
            return

        # Phase 02 Commit F: legacy stage2 back half is disabled for new lessons.
        # Historical v1 documents remain readable; new work must use the native path.
        logger.error(
            "legacy resume_stage2 blocked for new generation generation_id=%s",
            generation_id,
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "stage2_error",
                "error": "Legacy stage2 back half is disabled; use native whole-lesson path",
                "error_type": "LegacyBackHalfDisabled",
            },
        )
        await emit_event(
            "stage2_error",
            {
                "generation_id": generation_id,
                "error": "Legacy stage2 back half is disabled for new lessons",
            },
        )
        return
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
        # Prefer native atomic failure sync when this generation is native whole-lesson.
        failure_state: dict[str, Any] = {}
        try:
            failure_state = await load_chunked_state(generation_id)
        except Exception:  # noqa: BLE001
            failure_state = {}
        from planning.whole_lesson.native_routing import generation_is_native_whole_lesson
        from planning.whole_lesson.repository import persist_native_failure_for_generation

        is_native = generation_is_native_whole_lesson(failure_state) or bool(
            failure_state.get("page_document_v2")
            or (failure_state.get("context") or {}).get("native_whole_lesson")
        )
        if is_native:
            stage_name = native_failure_stage
            await persist_native_failure_for_generation(
                generation_id,
                exc=exc,
                stage=str(stage_name),
                event="pre_worker_failure",
            )
            await _chunked_emit_event(
                generation_id,
                "native_failure",
                {
                    "generation_id": generation_id,
                    "stage": str(stage_name),
                    "message": str(exc)[:400],
                },
            )
        else:
            await persist_chunked_state(
                generation_id,
                {
                    "stage": "stage2_error",
                    "execution_started": False,
                    "error": str(exc)[:400],
                    "error_type": type(exc).__name__,
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
        if cache_token is not None:
            from core.prompts import reset_prompt_cache

            reset_prompt_cache(cache_token)
        _chunked_stage2_tasks.pop(generation_id, None)
        print(
            f"\n[STAGE2 PIPELINE DONE] generation_id={generation_id}",
            flush=True,
        )


def _variant_plan_for_fanout(
    state: dict[str, Any],
    variant_label: str,
) -> dict[str, Any] | None:
    """Select the declared variant structure while retaining approved shared cards."""
    variant_plans = state.get("variant_structural_plans")
    selected_plan = (
        deepcopy(variant_plans.get(variant_label))
        if isinstance(variant_plans, dict)
        and isinstance(variant_plans.get(variant_label), dict)
        else deepcopy(state.get("structural_plan"))
    )
    canonical_plan = state.get("structural_plan")
    if isinstance(selected_plan, dict) and isinstance(canonical_plan, dict):
        selected_plan["cards"] = deepcopy(canonical_plan.get("cards", []))
        if "lesson_intent" in canonical_plan:
            selected_plan["lesson_intent"] = deepcopy(canonical_plan["lesson_intent"])
        return selected_plan
    return None


async def _prepare_variant_generations(
    *,
    coordinator_id: str,
    user_id: str,
    state: dict[str, Any],
) -> dict[str, str]:
    pack_id = state.get("pack_id")
    variants_raw = state.get("variants")
    if not isinstance(pack_id, str) or not isinstance(variants_raw, list):
        return {}
    variants = [
        VariantSpec.model_validate(raw)
        for raw in variants_raw
        if isinstance(raw, dict)
    ]
    existing_map = state.get("variant_generation_ids")
    generation_ids = (
        {
            str(label): str(generation_id)
            for label, generation_id in existing_map.items()
        }
        if isinstance(existing_map, dict)
        else {}
    )
    context = state.get("context")
    form_raw = context.get("form") if isinstance(context, dict) else None
    form = V3InputForm.model_validate(form_raw) if isinstance(form_raw, dict) else None
    if form is None:
        raise ValueError("Variant fan-out requires persisted form context")

    for index, variant in enumerate(variants):
        generation_id = generation_ids.get(variant.label) or str(uuid.uuid4())
        generation_ids[variant.label] = generation_id
        resource_id = f"variant-{index + 1}"
        selected_plan = _variant_plan_for_fanout(state, variant.label)
        selected_sections = (
            selected_plan.get("sections", []) if isinstance(selected_plan, dict) else []
        )
        await _ensure_chunked_generation_row(
            generation_id=generation_id,
            user_id=user_id,
            subject=form.subject,
            context=f"{form.topic} — {variant.label}",
            section_count=len(selected_sections),
            pack_id=pack_id,
            pack_resource_id=resource_id,
            pack_resource_label=variant.label,
            variant=variant,
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "stage2_running",
                "pack_id": pack_id,
                "coordinator_generation_id": coordinator_id,
                "variant_spec": variant.model_dump(mode="json"),
                "structural_plan": selected_plan,
                "section_briefs": {
                    str(section["id"]): None
                    for section in selected_sections
                    if isinstance(section, dict) and section.get("id")
                },
                "failed_sections": [],
                "context": deepcopy(state.get("context")),
                "display_title": f"{form.topic} — {variant.label}",
                "execution_started": False,
                "skip_item_generation": True,
            },
        )
        await _ensure_chunked_stream(
            generation_id=generation_id,
            user_id=user_id,
            blueprint_id=f"chunked-plan-{generation_id}",
        )
    return generation_ids


async def _run_pack_variant_pipeline(
    *,
    coordinator_id: str,
    user_id: str,
    generation_ids: dict[str, str],
) -> None:
    try:
        state = await load_chunked_state(coordinator_id)
        plan_raw = state.get("structural_plan")
        if not isinstance(plan_raw, dict):
            raise ValueError("Coordinator structural plan is missing")
        plan = adapt_legacy_structural_plan(
            plan_raw,
            source=f"coordinator:{coordinator_id}",
        )
        variants = [
            VariantSpec.model_validate(raw)
            for raw in state.get("variants", [])
            if isinstance(raw, dict)
        ]
        if variants:
            plan = plan.with_variant(variants[0])
        _signals, form, _resource_spec = _decode_chunked_context(state)
        item_summary = await _generate_shared_pack_items(
            generation_id=coordinator_id,
            form=form,
            plan=plan,
        )
        await persist_chunked_state(
            coordinator_id,
            {"item_generation": item_summary},
        )

        async def run_variant(generation_id: str) -> None:
            await _run_chunked_stage2_pipeline(
                generation_id=generation_id,
                user_id=user_id,
            )

        tasks = {
            generation_id: asyncio.create_task(run_variant(generation_id))
            for generation_id in generation_ids.values()
        }
        _chunked_stage2_tasks.update(tasks)
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        failures = {
            generation_id: str(result)[:400]
            for generation_id, result in zip(tasks, results, strict=True)
            if isinstance(result, Exception)
        }
        await persist_chunked_state(
            coordinator_id,
            {
                "stage": "variants_running" if len(failures) < len(tasks) else "stage2_error",
                "variant_failures": failures,
                "execution_started": bool(tasks),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "pack variant fan-out failed coordinator_id=%s",
            coordinator_id,
        )
        await persist_chunked_state(
            coordinator_id,
            {
                "stage": "stage2_error",
                "error": str(exc)[:400],
                "error_type": type(exc).__name__,
                "execution_started": False,
            },
        )
    finally:
        _chunked_stage2_tasks.pop(coordinator_id, None)


@v3_studio_router.post("/chunked/plan/start", response_model=V3ChunkedPlanStateDTO)
async def post_chunked_plan_start(
    body: V3ChunkedPlanStartRequest,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    generation_id = str(uuid.uuid4())
    pack_id = str(uuid.uuid4())
    form = body.form
    variants = [
        VariantSpec.model_validate(variant.model_dump(mode="json"))
        for variant in body.variants
    ] or [core_variant_spec()]
    labels = [variant.label.casefold() for variant in variants]
    if len(labels) != len(set(labels)):
        raise HTTPException(status_code=422, detail="Variant labels must be unique")
    resource_spec = _build_chunked_resource_spec(
        resource_type=form.resource_type,
        duration_minutes=form.duration_minutes,
    )

    resources = [
        {
            "id": f"variant-{index + 1}",
            "label": variant.label,
            "resource_type": form.resource_type,
            "enabled": True,
            "variant_spec": variant.model_dump(mode="json"),
        }
        for index, variant in enumerate(variants)
    ]
    async with async_session_factory() as session:
        session.add(
            LearningPackModel(
                id=pack_id,
                user_id=current_user.id,
                learning_job_type="xplore_variants",
                subject=form.subject.strip() or "General",
                topic=form.topic.strip() or "Generated lesson",
                pack_plan_json=json.dumps({
                    "resources": resources,
                    "shared_quiz": True,
                }),
                status="pending",
                resource_count=len(resources),
                completed_count=0,
            )
        )
        await session.commit()

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=current_user.id,
        subject=form.subject.strip() or "General",
        context=form.topic.strip() or "Chunked plan",
        pack_id=pack_id,
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
            "pack_id": pack_id,
            "variants": [
                variant.model_dump(mode="json")
                for variant in variants
            ],
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
        await V3GenerationWriter(async_session_factory).mark_awaiting_review(
            generation_id
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "awaiting_review",
                "execution_started": False,
            },
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


@v3_studio_router.get("/chunked/{generation_id}/plan", response_model=V3ChunkedPlanDTO)
async def get_chunked_plan(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanDTO:
    await _load_owned_generation(generation_id, current_user.id)
    try:
        state = await load_chunked_state(generation_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Chunked state not found") from exc
    full_state = _normalize_chunked_state(generation_id, state)
    if full_state.structural_plan is None:
        raise HTTPException(status_code=404, detail="Structural plan not found")
    return V3ChunkedPlanDTO(
        generation_id=generation_id,
        pack_id=full_state.pack_id,
        structural_plan=full_state.structural_plan,
        display_title=full_state.display_title,
        inferred_lesson_mode=full_state.inferred_lesson_mode,
        lesson_mode_confidence=full_state.lesson_mode_confidence,
        variants=full_state.variants,
        variant_generation_ids=full_state.variant_generation_ids,
    )


@v3_studio_router.get("/chunked/{generation_id}/status", response_model=V3ChunkedStatusDTO)
async def get_chunked_plan_status(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedStatusDTO:
    model = await _load_owned_generation(generation_id, current_user.id)
    try:
        state = await load_chunked_state(generation_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Chunked state not found") from exc
    return _normalize_chunked_status(
        generation_id,
        state,
        model.document_json,
        generation_status=str(model.status or "") or None,
    )


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
                try:
                    chunk = await asyncio.wait_for(
                        queue.get(),
                        timeout=HEARTBEAT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
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


@v3_studio_router.get(
    "/cards",
    response_model=list[V3CardLibraryItemDTO],
)
async def get_card_library(
    search: str = "",
    limit: int = 40,
    current_user: User = Depends(get_current_user),
) -> list[V3CardLibraryItemDTO]:
    async with async_session_factory() as session:
        pack_rows = await session.execute(
            select(LearningPackModel.id).where(
                LearningPackModel.user_id == current_user.id
            )
        )
        generation_rows = await session.execute(
            select(GenerationModel.id, GenerationModel.pack_id).where(
                GenerationModel.user_id == current_user.id
            )
        )
        owned_pack_ids = set(pack_rows.scalars())
        for generation_id, pack_id in generation_rows:
            owned_pack_ids.add(pack_id or generation_id)
        rows = await session.execute(
            select(ConceptCardModel).order_by(
                ConceptCardModel.created_at.desc(),
                ConceptCardModel.id.desc(),
            )
        )
        cards = [
            card for card in rows.scalars()
            if card.pack_id in owned_pack_ids
        ]

    needle = search.strip().casefold()
    if needle:
        cards = [
            card for card in cards
            if needle in " ".join(
                [card.slug, card.title, card.objective]
            ).casefold()
        ]
    unique: list[ConceptCardModel] = []
    seen: set[str] = set()
    for card in cards:
        if card.slug in seen:
            continue
        seen.add(card.slug)
        unique.append(card)
        if len(unique) >= max(1, min(limit, 100)):
            break
    return [
        V3CardLibraryItemDTO(
            card_id=card.id,
            pack_id=card.pack_id,
            slug=card.slug,
            title=card.title,
            objective=card.objective,
            prereqs=list(card.prereqs or []),
            misconceptions=(
                card.misconceptions
                if isinstance(card.misconceptions, list)
                else []
            ),
            created_at=_iso(card.created_at),
        )
        for card in unique
    ]


async def _sync_persisted_plan_card(
    *,
    generation_id: str,
    slug: str,
    title: str,
    objective: str,
    prereqs: list[str],
    misconceptions: list[dict[str, Any]],
) -> None:
    state = await load_chunked_state(generation_id)
    plan = state.get("structural_plan")
    if not isinstance(plan, dict):
        return
    cards = plan.get("cards")
    if not isinstance(cards, list):
        return
    updated = False
    next_cards: list[Any] = []
    for raw in cards:
        if not isinstance(raw, dict) or raw.get("id") != slug:
            next_cards.append(raw)
            continue
        next_cards.append(
            {
                **raw,
                "title": title,
                "objective": objective,
                "prereqs": prereqs,
                "misconceptions": misconceptions,
                "no_known_misconceptions": len(misconceptions) == 0,
            }
        )
        updated = True
    if updated:
        next_plan = {**plan, "cards": next_cards}
        await persist_chunked_state(
            generation_id,
            {"structural_plan": next_plan},
        )


@v3_studio_router.post(
    "/packs/{pack_id}/cards/reuse",
    response_model=V3ConceptCardDTO,
)
async def reuse_concept_card(
    pack_id: str,
    body: V3ReuseConceptCardRequest,
    current_user: User = Depends(get_current_user),
) -> V3ConceptCardDTO:
    card_pack_id, generation_id = await _resolve_owned_card_scope(
        pack_id,
        current_user.id,
    )
    async with async_session_factory() as session:
        source = await session.get(ConceptCardModel, body.source_card_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source concept card not found")
        source_scope = await session.get(LearningPackModel, source.pack_id)
        source_generation = await session.get(GenerationModel, source.pack_id)
        source_owned = (
            source_scope is not None and source_scope.user_id == current_user.id
        ) or (
            source_generation is not None
            and source_generation.user_id == current_user.id
        )
        if not source_owned:
            source_pack_generation = await session.execute(
                select(GenerationModel.id).where(
                    GenerationModel.pack_id == source.pack_id,
                    GenerationModel.user_id == current_user.id,
                ).limit(1)
            )
            source_owned = source_pack_generation.first() is not None
        if not source_owned:
            raise HTTPException(status_code=404, detail="Source concept card not found")

        target_result = await session.execute(
            select(ConceptCardModel).where(
                ConceptCardModel.pack_id == card_pack_id,
                ConceptCardModel.slug == body.target_card_id,
            )
        )
        target = target_result.scalar_one_or_none()
        if target is None:
            raise HTTPException(status_code=404, detail="Target concept card not found")
        try:
            await enforce_path_owned_card_objective(
                session,
                pack_id=card_pack_id,
                objective=source.objective,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        target.title = source.title
        target.objective = source.objective
        target.prereqs = deepcopy(source.prereqs or [])
        target.misconceptions = deepcopy(source.misconceptions or [])
        target.teacher_edited = False
        target.source_card_id = source.id
        target.source_pack_id = source.pack_id
        await session.execute(
            update(PackItemModel)
            .where(PackItemModel.card_id == target.id)
            .values(stale=True)
        )
        await session.commit()
        await session.refresh(target)
        dto = _card_dto(target)
    await _sync_persisted_plan_card(
        generation_id=generation_id,
        slug=target.slug,
        title=target.title,
        objective=target.objective,
        prereqs=list(target.prereqs or []),
        misconceptions=deepcopy(target.misconceptions or []),
    )
    return dto


@v3_studio_router.get(
    "/packs/{pack_id}/cards",
    response_model=list[V3ConceptCardDTO],
)
async def get_pack_concept_cards(
    pack_id: str,
    current_user: User = Depends(get_current_user),
) -> list[V3ConceptCardDTO]:
    card_pack_id, _ = await _resolve_owned_card_scope(pack_id, current_user.id)
    async with async_session_factory() as session:
        result = await session.execute(
            select(ConceptCardModel)
            .where(ConceptCardModel.pack_id == card_pack_id)
            .order_by(ConceptCardModel.created_at, ConceptCardModel.id)
        )
        return [_card_dto(card) for card in result.scalars()]


@v3_studio_router.patch(
    "/packs/{pack_id}/cards/{card_id}",
    response_model=V3ConceptCardDTO,
)
async def patch_pack_concept_card(
    pack_id: str,
    card_id: str,
    body: V3ConceptCardPatchRequest,
    current_user: User = Depends(get_current_user),
) -> V3ConceptCardDTO:
    card_pack_id, generation_id = await _resolve_owned_card_scope(
        pack_id,
        current_user.id,
    )
    async with async_session_factory() as session:
        result = await session.execute(
            select(ConceptCardModel).where(
                ConceptCardModel.slug == card_id,
                ConceptCardModel.pack_id == card_pack_id,
            )
        )
        card = result.scalar_one_or_none()
        if card is None:
            raise HTTPException(status_code=404, detail="Concept card not found")
        try:
            await enforce_path_owned_card_objective(
                session,
                pack_id=card_pack_id,
                objective=body.objective,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        previous_rows = (
            card.misconceptions
            if isinstance(card.misconceptions, list)
            else []
        )
        previous = {
            str(item.get("id")): item
            for item in previous_rows
            if isinstance(item, dict)
        }
        misconceptions: list[dict[str, str]] = []
        for item in body.misconceptions:
            old = previous.get(item.id)
            unchanged = (
                isinstance(old, dict)
                and old.get("description") == item.description
            )
            misconceptions.append(
                {
                    "id": item.id,
                    "description": item.description,
                    "source": (
                        str(old.get("source") or "drafted")
                        if unchanged
                        else "teacher"
                    ),
                }
            )

        card.title = body.title
        card.objective = body.objective
        card.misconceptions = misconceptions
        card.teacher_edited = True
        await session.execute(
            update(PackItemModel)
            .where(PackItemModel.card_id == card.id)
            .values(stale=True)
        )
        await session.commit()
        await session.refresh(card)
        dto = _card_dto(card)
    await _sync_persisted_plan_card(
        generation_id=generation_id,
        slug=card.slug,
        title=card.title,
        objective=card.objective,
        prereqs=list(card.prereqs or []),
        misconceptions=deepcopy(card.misconceptions or []),
    )
    return dto


async def _load_item_reviews(
    pack_id: str,
    *,
    card_id: str | None = None,
) -> list[V3CardItemReviewDTO]:
    async with async_session_factory() as session:
        card_query = select(ConceptCardModel).where(
            ConceptCardModel.pack_id == pack_id
        )
        if card_id is not None:
            card_query = card_query.where(ConceptCardModel.slug == card_id)
        card_rows = await session.execute(
            card_query.order_by(ConceptCardModel.created_at, ConceptCardModel.id)
        )
        cards = list(card_rows.scalars())
        item_query = select(PackItemModel).where(PackItemModel.pack_id == pack_id)
        if card_id is not None:
            item_query = item_query.where(
                PackItemModel.card_id.in_([card.id for card in cards])
            )
        item_rows = await session.execute(
            item_query.order_by(PackItemModel.card_id, PackItemModel.created_at, PackItemModel.id)
        )
        items_by_card: dict[str, list[PackItemModel]] = {}
        for row in item_rows.scalars():
            items_by_card.setdefault(row.card_id, []).append(row)

        reviews: list[V3CardItemReviewDTO] = []
        for card in cards:
            misconceptions = _card_dto(card).misconceptions
            known_ids = {item.id for item in misconceptions}
            coverage = {item_id: 0 for item_id in sorted(known_ids)}
            unmapped = 0
            item_dtos: list[V3PackItemDTO] = []
            card_items = items_by_card.get(card.id, [])
            for row in card_items:
                option_dtos: list[V3PackItemOptionDTO] = []
                for raw in row.options or []:
                    if not isinstance(raw, dict):
                        continue
                    option = V3PackItemOptionDTO.model_validate(raw)
                    option_dtos.append(option)
                    if option.correct:
                        continue
                    if option.diagnoses is None:
                        unmapped += 1
                    elif option.diagnoses in coverage:
                        coverage[option.diagnoses] += 1
                prefix = f"{pack_id}:"
                question_id = row.id[len(prefix):] if row.id.startswith(prefix) else row.id
                item_dtos.append(
                    V3PackItemDTO(
                        id=row.id,
                        question_id=question_id,
                        prompt_text=row.stem,
                        options=option_dtos,
                        stale=bool(row.stale),
                        teacher_edited=_item_row_teacher_edited(row),
                    )
                )

            reviews.append(
                V3CardItemReviewDTO(
                    card_id=card.slug,
                    card_title=card.title,
                    misconceptions=misconceptions,
                    items=item_dtos,
                    coverage=coverage,
                    missing_misconceptions=[
                        item_id
                        for item_id, count in coverage.items()
                        if count == 0
                    ],
                    unmapped_options=unmapped,
                    stale=any(bool(row.stale) for row in card_items),
                )
            )
        return reviews


@v3_studio_router.get(
    "/packs/{pack_id}/items",
    response_model=list[V3CardItemReviewDTO],
)
async def get_pack_items(
    pack_id: str,
    current_user: User = Depends(get_current_user),
) -> list[V3CardItemReviewDTO]:
    card_pack_id, _ = await _resolve_owned_card_scope(pack_id, current_user.id)
    return await _load_item_reviews(card_pack_id)


@v3_studio_router.patch(
    "/packs/{pack_id}/items/{item_id}",
    response_model=V3CardItemReviewDTO,
)
async def patch_pack_item(
    pack_id: str,
    item_id: str,
    body: V3PackItemPatchRequest,
    current_user: User = Depends(get_current_user),
) -> V3CardItemReviewDTO:
    card_pack_id, _ = await _resolve_owned_card_scope(pack_id, current_user.id)
    async with async_session_factory() as session:
        row = await session.get(PackItemModel, item_id)
        if row is None or row.pack_id != card_pack_id:
            raise HTTPException(status_code=404, detail="Pack item not found")
        card = await session.get(ConceptCardModel, row.card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Concept card not found")
        known_ids = {
            str(item.get("id"))
            for item in (card.misconceptions or [])
            if isinstance(item, dict)
        }
        options = [
            ItemOption(
                key=option.key,
                text=option.text,
                correct=option.correct,
                diagnoses=option.diagnoses,
            )
            for option in body.options
        ]
        for option in options:
            if option.diagnoses is not None and option.diagnoses not in known_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown misconception id '{option.diagnoses}'",
                )
        correct = next((option for option in options if option.correct), None)
        if correct is None:
            raise HTTPException(status_code=422, detail="Exactly one option must be correct")
        try:
            QuestionBrief(
                question_id=row.id,
                prompt_text=body.prompt_text,
                options=options,
                expected_answer=correct.text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.stem = body.prompt_text
        row.options = [
            {
                **option.model_dump(mode="json"),
                "teacher_edited": True,
            }
            for option in options
        ]
        row.correct_key = correct.key
        row.diagnoses = {
            option.key: option.diagnoses
            for option in options
        }
        row.stale = False
        card_id = row.card_id
        await session.commit()

    reviews = await _load_item_reviews(card_pack_id, card_id=card_id)
    return reviews[0]


@v3_studio_router.post(
    "/packs/{pack_id}/cards/{card_id}/items/regenerate",
    response_model=V3CardItemReviewDTO,
)
async def regenerate_pack_card_items(
    pack_id: str,
    card_id: str,
    current_user: User = Depends(get_current_user),
) -> V3CardItemReviewDTO:
    card_pack_id, generation_id = await _resolve_owned_card_scope(
        pack_id,
        current_user.id,
    )
    state = await load_chunked_state(generation_id)
    plan_raw = state.get("structural_plan")
    if not isinstance(plan_raw, dict):
        raise HTTPException(status_code=409, detail="Structural plan is not available")
    plan = adapt_legacy_structural_plan(
        plan_raw,
        source=f"generation:{generation_id}",
    )
    variant_raw = state.get("variant_spec")
    if isinstance(variant_raw, dict):
        plan = plan.with_variant(VariantSpec.model_validate(variant_raw))
    _signals, form, _resource_spec = _decode_chunked_context(state)
    async with async_session_factory() as session:
        result = await session.execute(
            select(ConceptCardModel).where(
                ConceptCardModel.slug == card_id,
                ConceptCardModel.pack_id == card_pack_id,
            )
        )
        card = result.scalar_one_or_none()
        if card is None:
            raise HTTPException(status_code=404, detail="Concept card not found")
        approved_card = _approved_card_for_items(
            card,
            subject=form.subject,
            level=form.grade_level,
            notation=plan.variant_spec().voice.notation,
        )
    generated = await execute_items(approved_card)
    await _persist_item_results(card_pack_id, [generated])
    reviews = await _load_item_reviews(card_pack_id, card_id=card_id)
    return reviews[0]


@v3_studio_router.post(
    "/packs/{pack_id}/cards/approve",
    response_model=V3ChunkedPlanStateDTO,
)
async def post_pack_concept_cards_approve(
    pack_id: str,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    card_pack_id, generation_id = await _resolve_owned_card_scope(
        pack_id,
        current_user.id,
    )
    async with async_session_factory() as session:
        result = await session.execute(
            select(ConceptCardModel).where(
                ConceptCardModel.pack_id == card_pack_id
            )
        )
        cards = list(result.scalars())
        if not cards:
            raise HTTPException(status_code=409, detail="Pack has no concept cards")
        for card in cards:
            try:
                await enforce_path_owned_card_objective(
                    session,
                    pack_id=card_pack_id,
                    objective=card.objective,
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await post_chunked_plan_approve(
        generation_id,
        body=None,
        current_user=current_user,
    )


async def _load_xplore_pack(
    pack_id: str,
    user_id: str,
) -> tuple[V3XplorePackDTO, LearningPackModel, GenerationModel]:
    async with async_session_factory() as session:
        pack = await session.get(LearningPackModel, pack_id)
        if (
            pack is None
            or pack.user_id != user_id
            or pack.learning_job_type != "xplore_variants"
        ):
            raise HTTPException(status_code=404, detail="Xplore pack not found")
        rows = await session.execute(
            select(GenerationModel)
            .where(GenerationModel.pack_id == pack_id)
            .order_by(GenerationModel.created_at, GenerationModel.id)
        )
        generations = list(rows.scalars())
        coordinator = next(
            (
                generation
                for generation in generations
                if generation.pack_resource_id is None
            ),
            None,
        )
        if coordinator is None:
            raise HTTPException(status_code=409, detail="Pack coordinator is missing")
        item_rows = await session.execute(
            select(PackItemModel.id).where(PackItemModel.pack_id == pack_id)
        )
        shared_item_count = len(list(item_rows.scalars()))

    coordinator_state = (
        coordinator.chunked_state_json
        if isinstance(coordinator.chunked_state_json, dict)
        else {}
    )
    variant_specs = [
        VariantSpec.model_validate(raw)
        for raw in coordinator_state.get("variants", [])
        if isinstance(raw, dict)
    ]
    ids_raw = coordinator_state.get("variant_generation_ids")
    generation_ids = ids_raw if isinstance(ids_raw, dict) else {}
    generations_by_id = {generation.id: generation for generation in generations}
    variants: list[V3PackVariantDTO] = []
    for spec in variant_specs:
        generation_id = generation_ids.get(spec.label)
        generation = (
            generations_by_id.get(str(generation_id))
            if generation_id is not None
            else None
        )
        state = (
            generation.chunked_state_json
            if generation is not None
            and isinstance(generation.chunked_state_json, dict)
            else {}
        )
        stage = str(state.get("stage") or "pending")
        failed_sections = [
            section_id
            for section_id in state.get("failed_sections", [])
            if isinstance(section_id, str)
        ]
        issues = []
        if isinstance(state.get("error"), str) and state["error"].strip():
            issues.append(state["error"].strip())
        issues.extend(
            f"Section failed: {section_id}"
            for section_id in failed_sections
        )
        if generation is None:
            status = "pending"
        elif generation.status == "deleted":
            status = "deleted"
        elif stage == "complete" or generation.status in {"completed", "partial"}:
            status = "landed"
        elif stage in {"stage2_error", "assembly_blocked"} or generation.status == "failed":
            status = "failed"
        else:
            status = "running"
        variants.append(
            V3PackVariantDTO(
                label=spec.label,
                group_description=spec.group_description,
                generation_id=generation.id if generation is not None else None,
                status=status,
                stage=stage,
                document_path=generation.document_path if generation is not None else None,
                failed_sections=failed_sections,
                issues=issues,
                can_retry=status == "failed",
            )
        )

    live_variants = [variant for variant in variants if variant.status != "deleted"]
    editor_ready = bool(live_variants) and all(
        variant.status in {"landed", "failed"}
        for variant in live_variants
    )
    landed_count = sum(variant.status == "landed" for variant in live_variants)
    if editor_ready and landed_count:
        status = "ready"
    elif editor_ready:
        status = "failed"
    else:
        status = "generating"
    dto = V3XplorePackDTO(
        pack_id=pack.id,
        coordinator_generation_id=coordinator.id,
        subject=pack.subject,
        topic=pack.topic,
        status=status,
        shared_item_count=shared_item_count,
        variants=variants,
        editor_ready=editor_ready,
    )
    return dto, pack, coordinator


@v3_studio_router.get("/packs/{pack_id}", response_model=V3XplorePackDTO)
async def get_xplore_pack(
    pack_id: str,
    current_user: User = Depends(get_current_user),
) -> V3XplorePackDTO:
    dto, _pack, _coordinator = await _load_xplore_pack(pack_id, current_user.id)
    return dto


@v3_studio_router.post(
    "/packs/{pack_id}/variants/{variant_label}/retry",
    response_model=V3XplorePackDTO,
)
async def post_xplore_variant_retry(
    pack_id: str,
    variant_label: str,
    current_user: User = Depends(get_current_user),
) -> V3XplorePackDTO:
    dto, _pack, coordinator = await _load_xplore_pack(pack_id, current_user.id)
    variant = next(
        (item for item in dto.variants if item.label == variant_label),
        None,
    )
    if variant is None or variant.generation_id is None:
        raise HTTPException(status_code=404, detail="Variant not found")
    if not variant.can_retry:
        raise HTTPException(status_code=409, detail="Only failed variants can be retried")
    running = _chunked_stage2_tasks.get(variant.generation_id)
    if running is not None and not running.done():
        raise HTTPException(status_code=409, detail="Variant retry is already running")

    state = await load_chunked_state(variant.generation_id)
    plan_raw = state.get("structural_plan")
    section_ids = [
        str(section.get("id"))
        for section in plan_raw.get("sections", [])
        if isinstance(plan_raw, dict)
        and isinstance(section, dict)
        and section.get("id")
    ] if isinstance(plan_raw, dict) else []
    await persist_chunked_state(
        variant.generation_id,
        {
            "stage": "stage2_running",
            "section_briefs": {section_id: None for section_id in section_ids},
            "failed_sections": [],
            "execution_started": False,
            "error": None,
            "error_type": None,
            "skip_item_generation": True,
        },
    )
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, variant.generation_id)
        if generation is not None:
            generation.status = "pending"
            generation.error = None
            generation.error_type = None
        await session.commit()
    task = asyncio.create_task(
        _run_chunked_stage2_pipeline(
            generation_id=variant.generation_id,
            user_id=current_user.id,
        )
    )
    _chunked_stage2_tasks[variant.generation_id] = task
    await persist_chunked_state(
        coordinator.id,
        {"stage": "variants_running"},
    )
    refreshed, _pack, _coordinator = await _load_xplore_pack(pack_id, current_user.id)
    return refreshed


@v3_studio_router.delete(
    "/packs/{pack_id}/variants/{variant_label}",
    response_model=V3XplorePackDTO,
)
async def delete_xplore_variant(
    pack_id: str,
    variant_label: str,
    current_user: User = Depends(get_current_user),
) -> V3XplorePackDTO:
    dto, pack, coordinator = await _load_xplore_pack(pack_id, current_user.id)
    variant = next(
        (item for item in dto.variants if item.label == variant_label),
        None,
    )
    if variant is None:
        raise HTTPException(status_code=404, detail="Variant not found")
    if len([item for item in dto.variants if item.status != "deleted"]) <= 1:
        raise HTTPException(status_code=409, detail="A pack must keep at least one variant")
    if variant.generation_id is not None:
        running = _chunked_stage2_tasks.pop(variant.generation_id, None)
        if running is not None and not running.done():
            running.cancel()

    coordinator_state = await load_chunked_state(coordinator.id)
    variants = [
        raw for raw in coordinator_state.get("variants", [])
        if isinstance(raw, dict) and raw.get("label") != variant_label
    ]
    generation_ids = {
        label: generation_id
        for label, generation_id in coordinator_state.get(
            "variant_generation_ids",
            {},
        ).items()
        if label != variant_label
    }
    await persist_chunked_state(
        coordinator.id,
        {
            "variants": variants,
            "variant_generation_ids": generation_ids,
        },
    )
    async with async_session_factory() as session:
        stored_pack = await session.get(LearningPackModel, pack.id)
        if stored_pack is not None:
            plan = json.loads(stored_pack.pack_plan_json)
            plan["resources"] = [
                resource
                for resource in plan.get("resources", [])
                if resource.get("label") != variant_label
            ]
            stored_pack.pack_plan_json = json.dumps(plan)
            stored_pack.resource_count = len(plan["resources"])
        if variant.generation_id is not None:
            generation = await session.get(GenerationModel, variant.generation_id)
            if generation is not None:
                generation.status = "deleted"
        await session.commit()
    refreshed, _pack, _coordinator = await _load_xplore_pack(pack_id, current_user.id)
    return refreshed


@v3_studio_router.post("/chunked/{generation_id}/approve", response_model=V3ChunkedPlanStateDTO)
async def post_chunked_plan_approve(
    generation_id: str,
    body: V3ChunkedApproveRequest | None = Body(default=None),
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    await _load_owned_generation(generation_id, current_user.id)
    state = await load_chunked_state(generation_id)
    if not isinstance(state.get("structural_plan"), dict):
        raise HTTPException(status_code=409, detail="Structural plan is not ready yet")
    stage = str(state.get("stage") or "")
    if stage not in {
        "awaiting_review",
        "plan_ready",
        "stage2_error",
        "assembly_blocked",
    }:
        if stage in {"stage2_running", "blueprint_ready", "complete"}:
            return _normalize_chunked_state(generation_id, state)
        raise HTTPException(
            status_code=409,
            detail="Generation is not awaiting explicit approval",
        )
    if stage in {"stage2_error", "assembly_blocked"}:
        claimed = await V3GenerationWriter(async_session_factory).claim_resume_attempt(generation_id)
        if not claimed:
            latest = await load_chunked_state(generation_id)
            return _normalize_chunked_state(generation_id, latest)

    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=current_user.id,
        blueprint_id=str(state.get("blueprint_id") or f"chunked-plan-{generation_id}"),
    )

    running_task = _chunked_stage2_tasks.get(generation_id)
    if running_task is not None and not running_task.done():
        latest = await load_chunked_state(generation_id)
        return _normalize_chunked_state(generation_id, latest)

    variants = [
        raw for raw in state.get("variants", [])
        if isinstance(raw, dict)
    ]
    patch: dict[str, Any] = {
        "stage": "variants_running" if variants else "stage2_running",
        "execution_started": False,
    }
    if body is not None and body.display_title and body.display_title.strip():
        patch["display_title"] = body.display_title.strip()
    if variants:
        generation_ids = await _prepare_variant_generations(
            coordinator_id=generation_id,
            user_id=current_user.id,
            state={**state, **patch},
        )
        patch["variant_generation_ids"] = generation_ids
        await persist_chunked_state(generation_id, patch)
        task = asyncio.create_task(
            _run_pack_variant_pipeline(
                coordinator_id=generation_id,
                user_id=current_user.id,
                generation_ids=generation_ids,
            )
        )
    else:
        await persist_chunked_state(generation_id, patch)
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
        await V3GenerationWriter(async_session_factory).mark_awaiting_review(
            generation_id
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "awaiting_review",
                "execution_started": False,
            },
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
    model = await _load_owned_generation(generation_id, current_user.id)
    state = await load_chunked_state(generation_id)

    from planning.whole_lesson.native_routing import generation_is_native_whole_lesson
    from planning.whole_lesson.repository import PageDocumentRepository

    if generation_is_native_whole_lesson(state, model):
        status = str(model.status or state.get("stage") or "")
        if status == "failed_recoverable":
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, generation_id)
                await repo.transition(
                    expected={"failed_recoverable"},
                    target="queued",
                    event="native_retry_requeued",
                )
            latest = await load_chunked_state(generation_id)
            latest = {
                **latest,
                "stage": "queued",
                "error": None,
                "error_type": None,
                "next_action": "wait",
            }
            await persist_chunked_state(
                generation_id,
                {
                    "stage": "queued",
                    "error": None,
                    "error_type": None,
                },
            )
            return _normalize_chunked_state(generation_id, {**latest, "stage": "queued"})
        raise HTTPException(
            status_code=409,
            detail={
                "error_type": "NativeRetryRequired",
                "message": (
                    "Legacy retry-section is disabled for native whole-lesson generations. "
                    "Requeue via failed_recoverable → queued or approve/retry native path."
                ),
                "stage": status,
                "generation_id": generation_id,
            },
        )

    plan_raw = state.get("structural_plan")
    if not isinstance(plan_raw, dict):
        raise HTTPException(status_code=409, detail="No structural plan available.")
    failed_sections = [
        section for section in state.get("failed_sections", [])
        if isinstance(section, str)
    ]
    if body.section_id not in failed_sections:
        raise HTTPException(status_code=409, detail="Section is not marked as failed.")
    if state.get("stage") == "assembly_blocked":
        claimed = await V3GenerationWriter(async_session_factory).claim_resume_attempt(generation_id)
        if not claimed:
            latest = await load_chunked_state(generation_id)
            return _normalize_chunked_state(generation_id, latest)

    running_task = _chunked_stage2_tasks.get(generation_id)
    if running_task is not None and not running_task.done():
        raise HTTPException(status_code=409, detail="Stage 2 is already running for this generation.")

    plan = adapt_legacy_structural_plan(
        plan_raw,
        source=f"generation:{generation_id}",
    )
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
                "brief": stage2_brief_preview_payload(retried) if retried is not None else None,
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
    trace_id = str(uuid.uuid4())
    _register_pre_generation_trace(trace_id=trace_id, user_id=str(current_user.id))
    try:
        revised = await adjust_production_blueprint(
            stored.blueprint,
            body.adjustment,
            trace_id=trace_id,
        )
    finally:
        _close_pre_generation_trace(trace_id=trace_id)
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
    preserved_ready_sections: list[dict[str, Any]] | None = None,
) -> None:
    def _utc_iso() -> str:
        return datetime.utcnow().isoformat() + "Z"

    def _section_ids_from_pack(pack: dict[str, Any]) -> list[str]:
        sections = pack.get("sections")
        if not isinstance(sections, list):
            return []
        ids: list[str] = []
        for section in sections:
            if isinstance(section, dict) and isinstance(section.get("section_id"), str):
                ids.append(section["section_id"])
        return ids

    def _progress_payload(
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        pack = payload.get("pack")
        existing: dict[str, Any] = {}
        section_ids: list[str] = []
        if isinstance(pack, dict):
            raw_progress = pack.get("progress")
            if isinstance(raw_progress, dict):
                existing = dict(raw_progress)
            section_ids = _section_ids_from_pack(pack)

        raw_sections = existing.get("sections")
        sections: dict[str, str] = dict(raw_sections) if isinstance(raw_sections, dict) else {}
        for section_id in section_ids:
            sections.setdefault(section_id, "pending")

        stage = str(existing.get("stage") or "writing")
        if event_type == "skeleton_ready":
            stage = "writing"
            sections = {section_id: "pending" for section_id in section_ids}
        elif event_type == "section_ready":
            stage = "writing"
            section_id = payload.get("section_id")
            if isinstance(section_id, str) and section_id:
                sections[section_id] = "ready"
        elif event_type == "coherence_review_started":
            stage = "reviewing"
        elif event_type in {"final_pack_ready", "draft_status_updated"}:
            stage = "finalizing"
            for section_id in section_ids:
                sections[section_id] = "ready"
        elif event_type == "resource_finalised":
            status = str(payload.get("status") or "")
            stage = "completed" if status in {"passed", "passed_with_warnings"} else "failed"
            for section_id in sections:
                if sections[section_id] not in {"ready", "failed"}:
                    sections[section_id] = "ready" if stage == "completed" else "failed"
        elif event_type == "generation_warning":
            stage = "failed"
            for section_id in sections:
                if sections[section_id] != "ready":
                    sections[section_id] = "failed"

        if not sections and not isinstance(pack, dict):
            return None
        return {"stage": stage, "sections": sections, "updated_at": _utc_iso()}

    def _payload_with_progress(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        progress = _progress_payload(event_type, payload)
        if progress is None:
            return payload
        next_payload = dict(payload)
        pack = next_payload.get("pack")
        if isinstance(pack, dict):
            next_pack = dict(pack)
            next_pack["progress"] = progress
            next_payload["pack"] = next_pack
        next_payload["progress"] = progress
        return next_payload

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
        lock = _snapshot_write_locks.setdefault(generation_id, asyncio.Lock())
        async with lock:
            payload = _payload_with_progress(event_type, payload)
            if event_type in {
                "component_ready",
                "component_patched",
                "question_ready",
                "visual_ready",
            }:
                await generation_writer.merge_stream_event(
                    generation_id,
                    event_type,
                    payload,
                )
                return
            if event_type in {"skeleton_ready", "section_ready"}:
                await generation_writer.write_draft(generation_id, payload)
                return
            if event_type in {"draft_pack_ready", "draft_status_updated"}:
                await generation_writer.write_draft(generation_id, payload)
                return
            if event_type == "final_pack_ready":
                await generation_writer.write_final(generation_id, payload)
                return
            if event_type == "coherence_review_started":
                progress = payload.get("progress")
                if isinstance(progress, dict):
                    await generation_writer.update_document_progress(generation_id, progress)
                else:
                    await generation_writer.update_document_progress_stage(
                        generation_id,
                        stage="reviewing",
                    )
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
                progress = payload.get("progress")
                if isinstance(progress, dict):
                    await generation_writer.update_document_progress(generation_id, progress)
                else:
                    status = str(payload.get("status") or "")
                    await generation_writer.update_document_progress_stage(
                        generation_id,
                        stage="completed" if status in {"passed", "passed_with_warnings"} else "failed",
                    )
                await generation_writer.write_resource_finalised(generation_id, payload)
                return
            if event_type == "generation_warning":
                progress = payload.get("progress")
                if isinstance(progress, dict):
                    await generation_writer.update_document_progress(generation_id, progress)
                else:
                    await generation_writer.update_document_progress_stage(
                        generation_id,
                        stage="failed",
                    )
                message = str(payload.get("message") or "Generation warning")
                await generation_writer.write_failure(generation_id, message=message)

    async def _write_pump_failure(message: str) -> None:
        if generation_writer is None:
            return
        try:
            await generation_writer.update_document_progress_stage(
                generation_id,
                stage="failed",
            )
            await generation_writer.write_failure(
                generation_id,
                message=message,
                error_type="generation_pump_failure",
                error_code="v3_generation_pump_failure",
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "v3 pump failure snapshot write failed generation_id=%s",
                generation_id,
            )

    terminal_event_seen = False
    pump_failure: str | None = None
    try:
        async for chunk in sse_event_stream(
            blueprint=blueprint,
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
            trace_id=trace_writer.trace_id if trace_writer is not None else generation_id,
            trace_writer=trace_writer,
            preserved_ready_sections=preserved_ready_sections,
        ):
            event_type, payload = _parse_sse_chunk(chunk)
            if event_type and payload is not None:
                if event_type in {"resource_finalised", "generation_warning"}:
                    terminal_event_seen = True
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
        pump_failure = "Generation stopped before it finished."
        raise
    except Exception as exc:  # noqa: BLE001
        pump_failure = f"{type(exc).__name__}: {str(exc)[:400] or repr(exc)}"
        logger.exception(
            "v3 generation pump crashed generation_id=%s",
            generation_id,
        )
    finally:
        if not terminal_event_seen and generation_writer is not None:
            # Runs as its own retained task so a cancelled pump still lands the
            # generation on a terminal snapshot and the frontend stops polling.
            _spawn_background_task(
                _write_pump_failure(
                    pump_failure or "Generation ended without a terminal event."
                )
            )
        _snapshot_write_locks.pop(generation_id, None)
        queue.put_nowait(None)


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
        effective_title = (body.display_title or blueprint.metadata.title).strip() or blueprint.metadata.title
        await trace_writer.start_run(
            user_id=current_user.id,
            blueprint_id=body.blueprint_id,
            template_id=template_id,
            title=effective_title,
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
            blueprint_title=effective_title,
            subject=blueprint.metadata.subject,
            template_id=template_id,
        )
        await generation_writer.upsert_started(
            generation_id=body.generation_id,
            user_id=current_user.id,
            subject=blueprint.metadata.subject,
            context=effective_title,
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
            display_title=effective_title,
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
    _spawn_background_task(
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
                try:
                    chunk = await asyncio.wait_for(
                        queue.get(),
                        timeout=HEARTBEAT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
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
    response: Response,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    generation_writer = V3GenerationWriter(async_session_factory)
    model = await generation_writer.get_generation_model(generation_id, current_user.id)
    if model is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    document_json = await generation_writer.get_document_json(generation_id, current_user.id)
    if document_json is None:
        document_json = {
            "kind": "v3_booklet_pack",
            "generation_id": generation_id,
            "status": "streaming_preview",
            "sections": [],
        }
    document_json = await _with_shared_pack_assessment(model, document_json)
    sections = document_json.get("sections")
    if not isinstance(sections, list) or not sections:
        process_status = str(model.status or "running")
        progress_stage = (
            "completed"
            if process_status == "completed"
            else "failed"
            if process_status in {"failed", "partial"}
            else "writing"
        )
        document_json = {
            **document_json,
            "generation_id": generation_id,
            "status": str(document_json.get("status") or "streaming_preview"),
            "sections": [],
            "progress": {"stage": progress_stage, "sections": {}},
        }
    response.headers["Cache-Control"] = "no-store"
    return document_json


async def _with_shared_pack_assessment(
    model: GenerationModel,
    document_json: dict[str, Any],
) -> dict[str, Any]:
    if not model.pack_id:
        return document_json
    async with async_session_factory() as session:
        item_result = await session.execute(
            select(PackItemModel)
            .where(PackItemModel.pack_id == model.pack_id)
            .order_by(PackItemModel.card_id, PackItemModel.id)
        )
        items = list(item_result.scalars())
        if not items:
            return document_json
        card_result = await session.execute(
            select(ConceptCardModel).where(
                ConceptCardModel.pack_id == model.pack_id
            )
        )
        cards = list(card_result.scalars())

    misconception_labels = {
        (card.id, str(misconception.get("id"))): str(
            misconception.get("description") or misconception.get("id")
        )
        for card in cards
        for misconception in (
            card.misconceptions
            if isinstance(card.misconceptions, list)
            else []
        )
        if isinstance(misconception, dict) and misconception.get("id")
    }
    item_payloads = [
        {
            "id": item.id,
            "card_id": item.card_id,
            "stem": item.stem,
            "options": item.options if isinstance(item.options, list) else [],
            "correct_key": item.correct_key,
        }
        for item in items
        if not item.stale
    ]
    quiz_sections = []
    for index, item in enumerate(item_payloads, start=1):
        options = [
            option for option in item["options"]
            if isinstance(option, dict)
        ]
        quiz_sections.append(
            {
                "section_id": f"shared-diagnostic-{index:02d}",
                "template_id": "guided-concept-path",
                "card_id": item["card_id"],
                "header": {
                    "title": (
                        "Shared diagnostic"
                        if index == 1
                        else f"Shared diagnostic · {index}"
                    ),
                    "subject": model.subject,
                    "grade_band": "secondary",
                },
                "quiz": {
                    "question": item["stem"],
                    "quiz_type": "multiple-choice",
                    "options": [
                        {
                            "text": str(option.get("text") or ""),
                            "correct": bool(option.get("correct")),
                            "explanation": (
                                "Correct."
                                if option.get("correct")
                                else "Review this idea with your teacher."
                            ),
                            "diagnoses": option.get("diagnoses"),
                        }
                        for option in options
                    ],
                    "feedback_correct": "Correct.",
                    "feedback_incorrect": "Check the concept and try again.",
                    "show_explanations": False,
                },
            }
        )
    next_document = deepcopy(document_json)
    base_sections = [
        section
        for section in next_document.get("sections", [])
        if isinstance(section, dict)
        and not str(section.get("section_id") or "").startswith(
            "shared-diagnostic-"
        )
    ]
    next_document["sections"] = [*base_sections, *quiz_sections]
    next_document["answer_key"] = build_diagnostic_answer_key_content(
        items=item_payloads,
        misconception_labels=misconception_labels,
    )
    next_document["shared_quiz_pack_id"] = model.pack_id
    return next_document


def _find_visual_block(
    document_json: dict[str, Any],
    visual_id: str,
) -> tuple[int, GeneratedVisualBlock]:
    raw_blocks = document_json.get("visual_blocks")
    if not isinstance(raw_blocks, list):
        raise HTTPException(status_code=404, detail="Visual not found")
    for idx, raw in enumerate(raw_blocks):
        if not isinstance(raw, dict):
            continue
        if raw.get("visual_id") == visual_id:
            return idx, GeneratedVisualBlock.model_validate(raw)
    raise HTTPException(status_code=404, detail="Visual not found")


def _work_order_for_visual(
    *,
    artifact: dict[str, Any],
    target: GeneratedVisualBlock,
    generation_id: str,
) -> VisualGeneratorWorkOrder:
    blueprint = ProductionBlueprint.model_validate(artifact["blueprint"])
    blueprint_id = str(artifact.get("blueprint_id") or f"blueprint-{generation_id}")
    template_id = str(artifact.get("template_id") or "guided-concept-path")
    bundle = compile_execution_bundle(
        blueprint,
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        template_id=template_id,
    )
    for order in bundle.visual_orders:
        if order.work_order_id == target.source_work_order_id:
            return order
        if order.visual.id == target.visual_id:
            return order
        if target.parent_visual_id and order.visual.id == target.parent_visual_id:
            return order
    raise HTTPException(status_code=404, detail="Visual work order not found")


def _work_order_for_component(
    *, artifact: dict[str, Any], component_ref: str, generation_id: str
) -> tuple[SectionWriterWorkOrder, str]:
    blueprint = ProductionBlueprint.model_validate(artifact["blueprint"])
    bundle = compile_execution_bundle(
        blueprint,
        generation_id=generation_id,
        blueprint_id=str(artifact.get("blueprint_id") or f"blueprint-{generation_id}"),
        template_id=str(artifact.get("template_id") or "guided-concept-path"),
    )
    matches: list[tuple[SectionWriterWorkOrder, str]] = []
    for order in bundle.section_orders:
        for component in order.section.components:
            refs = {
                component.component_id,
                f"{order.section.id}:{component.component_id}",
                f"{component.component_id}@{order.section.id}",
            }
            if component_ref in refs:
                matches.append((order, component.component_id))
    if len(matches) != 1:
        raise HTTPException(status_code=404, detail="Component work order not found")
    return matches[0]


def _single_component_order(
    order: SectionWriterWorkOrder,
    component_id: str,
    teacher_instruction: str,
    *,
    generation_id: str,
) -> SectionWriterWorkOrder:
    cloned = order.model_copy(deep=True)
    selected = next(component for component in cloned.section.components if component.component_id == component_id)
    selected.corrections = [
        *selected.corrections,
        Correction(
            text=teacher_instruction.strip(),
            created_at=datetime.utcnow().isoformat() + "Z",
            applied_in_generation=generation_id,
        ),
    ]
    cloned.section.components = [selected]
    return cloned


def _card_section_orders(
    *,
    artifact: dict[str, Any],
    card_id: str,
    generation_id: str,
    correction_hint: str,
) -> list[SectionWriterWorkOrder]:
    blueprint = ProductionBlueprint.model_validate(artifact["blueprint"])
    section_ids = {
        section.section_id
        for section in blueprint.sections
        if section.card_id == card_id
    }
    if not section_ids:
        raise HTTPException(status_code=404, detail="Card repair target not found")
    bundle = compile_execution_bundle(
        blueprint,
        generation_id=generation_id,
        blueprint_id=str(artifact.get("blueprint_id") or f"blueprint-{generation_id}"),
        template_id=str(artifact.get("template_id") or "guided-concept-path"),
    )
    orders: list[SectionWriterWorkOrder] = []
    correction = Correction(
        text=correction_hint.strip(),
        created_at=datetime.utcnow().isoformat() + "Z",
        applied_in_generation=generation_id,
    )
    for order in bundle.section_orders:
        if order.section.id not in section_ids:
            continue
        cloned = order.model_copy(deep=True)
        for component in cloned.section.components:
            component.corrections = [*component.corrections, correction.model_copy()]
        orders.append(cloned)
    if not orders:
        raise HTTPException(status_code=404, detail="Card work orders not found")
    return orders


def _patch_section_component(document_json: dict[str, Any], block: GeneratedComponentBlock) -> None:
    sections = document_json.get("sections")
    if not isinstance(sections, list):
        raise HTTPException(status_code=404, detail="Component section not found")
    for section in sections:
        if isinstance(section, dict) and section.get("section_id") == block.section_id:
            section[block.section_field] = block.data
            return
    raise HTTPException(status_code=404, detail="Component section not found")


def _apply_visual_repair_context(
    order: VisualGeneratorWorkOrder,
    target: GeneratedVisualBlock,
    teacher_hint: str | None,
) -> VisualGeneratorWorkOrder:
    hint = (teacher_hint or "").strip()
    qc_reasons = [reason.strip() for reason in target.qc_reasons if reason.strip()]
    if not hint and not qc_reasons:
        return order
    cloned = order.model_copy(deep=True)
    additions: list[str] = []
    if qc_reasons:
        additions.append(
            "Quality review reasons:\n" + "\n".join(f"- {reason}" for reason in qc_reasons)
        )
    if hint:
        additions.append(f"Correction: {hint}")
    cloned.visual.purpose = f"{cloned.visual.purpose}\n\n" + "\n\n".join(additions)
    return cloned


def _replace_visual_blocks(
    document_json: dict[str, Any],
    *,
    target: GeneratedVisualBlock,
    new_blocks: list[GeneratedVisualBlock],
) -> None:
    raw_blocks = document_json.get("visual_blocks")
    if not isinstance(raw_blocks, list):
        document_json["visual_blocks"] = [b.model_dump(mode="json", exclude_none=True) for b in new_blocks]
        return

    source_work_order_id = target.source_work_order_id
    replaced = False
    updated: list[Any] = []
    for raw in raw_blocks:
        if not isinstance(raw, dict):
            updated.append(raw)
            continue
        if raw.get("source_work_order_id") == source_work_order_id:
            if not replaced:
                updated.extend(b.model_dump(mode="json", exclude_none=True) for b in new_blocks)
                replaced = True
            continue
        updated.append(raw)
    if not replaced:
        updated.extend(b.model_dump(mode="json", exclude_none=True) for b in new_blocks)
    document_json["visual_blocks"] = updated


def _patch_section_visuals(
    document_json: dict[str, Any],
    *,
    target: GeneratedVisualBlock,
    new_blocks: list[GeneratedVisualBlock],
) -> None:
    sections = document_json.get("sections")
    if not isinstance(sections, list):
        return
    affected_ids = {target.attaches_to, *(block.attaches_to for block in new_blocks)}
    for section in sections:
        if not isinstance(section, dict) or section.get("section_id") not in affected_ids:
            continue
        ready_blocks = [block for block in new_blocks if block.attaches_to == section.get("section_id") and block.image_url]
        section.pop("diagram", None)
        section.pop("diagram_series", None)
        if not ready_blocks:
            continue
        series = sorted(
            [block for block in ready_blocks if block.mode == "diagram_series"],
            key=lambda block: block.frame_index or 0,
        )
        if series:
            section["diagram_series"] = {
                "title": section.get("title") or "Diagram",
                "diagrams": [
                    {
                        "step_label": f"Frame {(block.frame_index or 0) + 1}",
                        "caption": block.caption or block.alt_text or f"Frame {block.frame_index}",
                        "image_url": block.image_url,
                    }
                    for block in series
                ],
            }
            continue
        block = ready_blocks[0]
        section["diagram"] = {
            "image_url": block.image_url,
            "caption": block.caption or section.get("title") or "",
            "alt_text": block.alt_text or section.get("title") or "",
        }


async def _persist_regenerated_visual(
    *,
    generation_id: str,
    user_id: str,
    document_json: dict[str, Any],
) -> None:
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        if model is None or model.user_id != user_id:
            raise HTTPException(status_code=404, detail="Generation not found")
        bump_document_version(document_json)
        model.document_json = document_json
        await session.commit()


def _lock_for_visual_regenerate(generation_id: str) -> asyncio.Lock:
    lock = _visual_regenerate_locks.get(generation_id)
    if lock is None:
        lock = asyncio.Lock()
        _visual_regenerate_locks[generation_id] = lock
    return lock


@v3_studio_router.post("/generations/{generation_id}/components/{component_ref}/patch")
async def patch_v3_component(
    generation_id: str,
    component_ref: str,
    body: V3ComponentPatchRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    async with async_session_factory() as ownership_session:
        owned_model = await ownership_session.get(GenerationModel, generation_id)
        if owned_model is not None and owned_model.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Generation is owned by another user")
    generation_writer = V3GenerationWriter(async_session_factory)
    document_json = await generation_writer.get_document_json(generation_id, current_user.id)
    if document_json is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    artifact = await generation_writer.read_planning_artifact(generation_id, current_user.id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Planning artifact not found")

    order, component_id = _work_order_for_component(
        artifact=artifact, component_ref=component_ref, generation_id=generation_id
    )
    order = _single_component_order(
        order,
        component_id,
        body.teacher_instruction,
        generation_id=generation_id,
    )

    async def emit_noop(_event_type: str, _payload: dict[str, Any]) -> None:
        return None

    blocks = await execute_section(
        order,
        emit_noop,
        trace_id=generation_id,
        generation_id=generation_id,
        max_retries=0,
    )
    if len(blocks) != 1:
        raise HTTPException(status_code=500, detail="Component patch produced no component")
    block = blocks[0]
    _patch_section_component(document_json, block)
    await _persist_regenerated_visual(
        generation_id=generation_id,
        user_id=current_user.id,
        document_json=document_json,
    )
    return block.model_dump(mode="json", exclude_none=True)


@v3_studio_router.post("/generations/{generation_id}/cards/{card_id}/repair")
async def repair_v3_card(
    generation_id: str,
    card_id: str,
    body: V3CardRepairRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    generation_writer = V3GenerationWriter(async_session_factory)
    document_json = await generation_writer.get_document_json(generation_id, current_user.id)
    if document_json is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    artifact = await generation_writer.read_planning_artifact(
        generation_id,
        current_user.id,
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="Planning artifact not found")

    issue_hints = [
        str(issue.get("qc_correction_hint") or issue.get("message") or "").strip()
        for issue in document_json.get("booklet_issues", [])
        if isinstance(issue, dict)
        and issue.get("repair_target_id") == card_id
    ]
    supplied_hint = body.correction_hint.strip() if body and body.correction_hint else ""
    correction_hint = supplied_hint or "\n".join(hint for hint in issue_hints if hint)
    if not correction_hint:
        raise HTTPException(
            status_code=409,
            detail="Card repair requires a failed QC correction hint",
        )
    orders = _card_section_orders(
        artifact=artifact,
        card_id=card_id,
        generation_id=generation_id,
        correction_hint=correction_hint,
    )

    async def emit_noop(_event_type: str, _payload: dict[str, Any]) -> None:
        return None

    blocks: list[GeneratedComponentBlock] = []
    for order in orders:
        blocks.extend(
            await execute_section(
                order,
                emit_noop,
                trace_id=generation_id,
                generation_id=generation_id,
                max_retries=0,
            )
        )
    for block in blocks:
        _patch_section_component(document_json, block)
    prior_issues = [
        issue
        for issue in document_json.get("booklet_issues", [])
        if (
            isinstance(issue, dict)
            and issue.get("repair_target_id") == card_id
        )
    ]
    retained_issues = [
        issue
        for issue in document_json.get("booklet_issues", [])
        if not (
            isinstance(issue, dict)
            and issue.get("repair_target_id") == card_id
        )
    ]
    blueprint = ProductionBlueprint.model_validate(artifact["blueprint"])
    rubric = next(
        (card for card in blueprint.card_rubrics if card.card_id == card_id),
        None,
    )
    verdict = "unavailable"
    if rubric is not None:
        generated_sections = [
            section
            for section in document_json.get("sections", [])
            if isinstance(section, dict) and section.get("card_id") == card_id
        ]
        try:
            qc = await review_card_content(
                card=rubric,
                variant_label=blueprint.voice.variant_label,
                notation=blueprint.voice.notation,
                avoid=(
                    list(blueprint.repair_focus.what_not_to_teach)
                    if blueprint.repair_focus is not None
                    else []
                ),
                generated_sections=generated_sections,
                generation_id=generation_id,
            )
        except Exception:  # noqa: BLE001
            retained_issues.extend(prior_issues)
        else:
            verdict = qc.verdict
            retained_issues.extend(
                {
                    "issue_id": str(uuid.uuid4()),
                    "severity": "major",
                    "category": (
                        "card_objective_unmet"
                        if check.check == "objective"
                        else "card_scope_breach"
                        if check.check == "scope"
                        else "card_notation_breach"
                        if check.check == "notation"
                        else "card_misconception_unconfronted"
                    ),
                    "message": (
                        f"Card '{card_id}' failed {check.check}: {check.reason}"
                    ),
                    "section_id": f"{blueprint.voice.variant_label}:{card_id}",
                    "repair_target_id": card_id,
                    "qc_correction_hint": check.correction_hint or check.reason,
                }
                for check in qc.checks
                if check.result == "FAIL"
            )
    else:
        retained_issues.extend(prior_issues)
    document_json["booklet_issues"] = retained_issues
    await _persist_regenerated_visual(
        generation_id=generation_id,
        user_id=current_user.id,
        document_json=document_json,
    )
    return {
        "card_id": card_id,
        "repaired_sections": sorted({block.section_id for block in blocks}),
        "component_count": len(blocks),
        "verdict": verdict,
    }


@v3_studio_router.post("/generations/{generation_id}/visuals/{visual_id}/regenerate")
async def regenerate_v3_visual(
    generation_id: str,
    visual_id: str,
    body: V3VisualRegenerateRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    lock = _lock_for_visual_regenerate(generation_id)
    if lock.locked():
        raise HTTPException(status_code=409, detail="Visual regeneration already running.")

    async with lock:
        generation_writer = V3GenerationWriter(async_session_factory)
        document_json = await generation_writer.get_document_json(generation_id, current_user.id)
        if document_json is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        artifact = await generation_writer.read_planning_artifact(generation_id, current_user.id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Planning artifact not found")

        _, target = _find_visual_block(document_json, visual_id)
        order = _work_order_for_visual(
            artifact=artifact,
            target=target,
            generation_id=generation_id,
        )
        order = _apply_visual_repair_context(
            order,
            target,
            body.teacher_hint if body is not None else None,
        )

        async def emit_noop(_event_type: str, _payload: dict[str, Any]) -> None:
            return None

        new_blocks = await execute_visual(
            order,
            emit_noop,
            trace_id=generation_id,
            generation_id=generation_id,
            bypass_cache_read=True,
        )
        if not new_blocks:
            raise HTTPException(status_code=500, detail="Visual regeneration produced no block")

        _replace_visual_blocks(document_json, target=target, new_blocks=new_blocks)
        _patch_section_visuals(document_json, target=target, new_blocks=new_blocks)
        await _persist_regenerated_visual(
            generation_id=generation_id,
            user_id=current_user.id,
            document_json=document_json,
        )

        response_block = next(
            (block for block in new_blocks if block.visual_id == visual_id),
            new_blocks[0],
        )
        return response_block.model_dump(mode="json", exclude_none=True)


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
    document_json = await _with_shared_pack_assessment(model, document_json)
    # Strict print policy for native v2: pending/failed required figures block final export.
    allow_placeholders = bool(getattr(body, "allow_placeholders", False))
    lectio_doc = document_json.get("lectio_document")
    if isinstance(lectio_doc, dict) and int(document_json.get("document_version") or 0) == 2:
        pending_ids: list[str] = []
        for section in lectio_doc.get("sections") or []:
            for block in section.get("blocks") or []:
                if block.get("object") != "figure":
                    continue
                asset = (block.get("content") or {}).get("asset") or {}
                status = str(asset.get("status") or "")
                if status in {"pending", "failed"}:
                    pending_ids.append(str(block.get("id")))
        if pending_ids and not allow_placeholders:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "FIGURES_NOT_READY",
                    "message": "Required figures are pending or failed",
                    "block_ids": pending_ids,
                },
            )
    sections = document_json.get("sections")
    if not isinstance(sections, list) or not sections:
        # Native v2 may store only lectio_document; synthesize section list for legacy PDF path.
        if isinstance(lectio_doc, dict) and isinstance(lectio_doc.get("sections"), list):
            sections = lectio_doc["sections"]
            document_json = {**document_json, "sections": sections}
        else:
            raise HTTPException(status_code=404, detail="Document not found")
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
            title=_generation_title(model),
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

# -- Whole-lesson teaching approach gate (native page documents) --------------


class LessonApproachApproveRequest(BaseModel):
    expected_revision: int = 1
    teacher_note: str | None = None


class LessonApproachRejectRequest(BaseModel):
    expected_revision: int = 1
    teacher_note: str | None = None


class PageBlockPatchRequest(BaseModel):
    expected_document_revision: int
    content_patch: dict[str, Any]


class FigureVisualCallbackRequest(BaseModel):
    request_id: str
    block_id: str | None = None
    asset: dict[str, Any]


@v3_studio_router.get("/generations/{generation_id}/lesson-approach")
async def get_lesson_approach(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _load_owned_generation(generation_id, current_user.id)
    from planning.whole_lesson.repository import PageDocumentRepository

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        state = await repo.load_page_generation_state()
    if not state.get("teaching_plan"):
        raise HTTPException(status_code=404, detail="Teaching plan not ready")
    return {
        "generation_id": generation_id,
        "teaching_plan": state.get("teaching_plan"),
        "teaching_validation": state.get("teaching_validation"),
        "teaching_qc": state.get("teaching_qc"),
        "teaching_review": state.get("teaching_review"),
        "lesson_packet": state.get("lesson_packet"),
        "catalogue": state.get("catalogue"),
    }


@v3_studio_router.post("/generations/{generation_id}/lesson-approach/approve")
async def post_lesson_approach_approve(
    generation_id: str,
    body: LessonApproachApproveRequest,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    await _load_owned_generation(generation_id, current_user.id)
    from planning.whole_lesson.service import approve_teaching_and_queue

    async with async_session_factory() as session:
        try:
            result = await approve_teaching_and_queue(
                session,
                generation_id,
                expected_revision=body.expected_revision,
                reviewed_by=current_user.id,
                teacher_note=body.teacher_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("lesson approach approve failed generation_id=%s", generation_id)
            raise HTTPException(status_code=500, detail=str(exc)[:400]) from exc
    return JSONResponse(
        status_code=202,
        content={
            "generation_id": generation_id,
            "status": result.get("status") or "queued",
            "document_version": 2,
        },
    )


@v3_studio_router.post("/generations/{generation_id}/lesson-approach/reject")
async def post_lesson_approach_reject(
    generation_id: str,
    body: LessonApproachRejectRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _load_owned_generation(generation_id, current_user.id)
    from planning.whole_lesson.repository import PageDocumentRepository

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        try:
            await repo.save_teaching_review(
                status="rejected",
                expected_revision=body.expected_revision,
                reviewed_by=current_user.id,
                teacher_note=body.teacher_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"generation_id": generation_id, "status": "rejected_by_teacher"}


@v3_studio_router.patch("/generations/{generation_id}/page-blocks/{block_id}")
async def patch_page_block(
    generation_id: str,
    block_id: str,
    body: PageBlockPatchRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _load_owned_generation(generation_id, current_user.id)
    from generation.page_objects.document_assembly import reload_document
    from planning.whole_lesson.events import make_event
    from planning.whole_lesson.repository import PageDocumentRepository
    from contracts.lectio_page import validate_document

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        repo = PageDocumentRepository(session, generation_id)
        state = await repo.load_page_generation_state()
        current_rev = int(state.get("document_revision") or 0)
        if body.expected_document_revision != current_rev:
            raise HTTPException(status_code=409, detail="stale document revision")
        envelope = generation.document_json or {}
        document = reload_document(envelope)
        found = False
        for section in document.get("sections") or []:
            for block in section.get("blocks") or []:
                if block.get("id") == block_id:
                    content = dict(block.get("content") or {})
                    content.update(body.content_patch)
                    block["content"] = content
                    found = True
                    break
            if found:
                break
        if not found:
            raise HTTPException(status_code=404, detail=f"block {block_id!r} not found")
        errors = validate_document(document)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors[:5]))
        from generation.page_objects.document_assembly import persist_document_json

        generation.document_json = persist_document_json(envelope, document)
        revision = await repo.bump_document_revision()
        await repo.append_event(
            make_event(
                "block_patched",
                generation_id=generation_id,
                block_id=block_id,
                status="ready",
            )
        )
        await session.commit()
    return {"generation_id": generation_id, "block_id": block_id, "document_revision": revision}


@v3_studio_router.post("/generations/{generation_id}/visuals/callback")
async def post_figure_visual_callback(
    generation_id: str,
    body: FigureVisualCallbackRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Idempotent figure asset completion keyed by request_id."""
    await _load_owned_generation(generation_id, current_user.id)
    from planning.whole_lesson.repository import (
        PageDocumentRepository,
        VisualCompletionConflict,
        VisualCompletionInvariantError,
        VisualCompletionStateError,
        VisualRequestNotFound,
    )

    request_id = str(body.request_id or "").strip()
    if not request_id:
        raise HTTPException(status_code=400, detail="request_id is required")
    asset = dict(body.asset or {})
    asset["request_id"] = request_id

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        try:
            result = await repo.apply_visual_completion(
                request_id=request_id,
                asset=asset,
                supplied_block_id=body.block_id,
            )
        except VisualRequestNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (
            VisualCompletionConflict,
            VisualCompletionStateError,
            VisualCompletionInvariantError,
        ) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            from generation.page_objects.visual_completion import VisualCompletionError

            if isinstance(exc, VisualCompletionError):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise

    return {
        "generation_id": result.generation_id,
        "block_id": result.block_id,
        "request_id": result.request_id,
        "status": result.status,
        "document_revision": result.document_revision,
        "idempotent": result.idempotent,
    }


@v3_studio_router.post("/generations/{generation_id}/visuals/retry")
async def post_visuals_retry(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Visuals-only redispath for native generations stuck in awaiting_visuals.

    Never requeues writers, form planning, teaching, or item generation.
    """
    model = await _load_owned_generation(generation_id, current_user.id)
    from planning.whole_lesson.native_routing import generation_is_native_whole_lesson
    from planning.whole_lesson.repository import PageDocumentRepository
    from planning.whole_lesson.visual_dispatch import dispatch_and_patch_from_repo

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        repo = PageDocumentRepository(session, generation_id)
        state = await repo.load_page_generation_state()
        chunked = dict(generation.chunked_state_json or {})
        if not generation_is_native_whole_lesson(chunked, generation):
            raise HTTPException(
                status_code=409,
                detail="visuals/retry is only available for native whole-lesson generations",
            )
        status = str(generation.status or "")
        if status != "awaiting_visuals":
            raise HTTPException(
                status_code=409,
                detail=f"visuals/retry requires awaiting_visuals, got {status!r}",
            )
        try:
            dispatch = await dispatch_and_patch_from_repo(
                session=session,
                generation_id=generation_id,
            )
        except Exception as exc:  # noqa: BLE001
            await repo.persist_visual_dispatch_failure(exc=exc)
            raise HTTPException(
                status_code=502,
                detail=f"visual redispath failed: {str(exc)[:400]}",
            ) from exc
        generation = await session.get(GenerationModel, generation_id)
        terminal = str(generation.status or status) if generation else status
        page = await repo.load_page_generation_state()
        last_error = (page.get("execution") or {}).get("last_error")
    return {
        "generation_id": generation_id,
        "status": terminal,
        "visual_dispatch": dispatch,
        "next_action": (
            "retry_visuals"
            if terminal == "awaiting_visuals"
            and (dispatch.get("failed") or last_error)
            else ("done" if terminal == "ready" else "wait_visuals")
        ),
        "error_detail": last_error if isinstance(last_error, dict) else None,
    }
