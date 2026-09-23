from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any

from core.auth.jwt_handler import JWTHandler
from core.auth.middleware import get_current_user
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from starlette.background import BackgroundTask

from application.unit_lesson import enforce_path_owned_card_objective
from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LearningPackModel,
    PackItemModel,
)
from core.database.session import async_session_factory
from core.dependencies import get_jwt_handler, get_settings
from core.entities.user import User
from core.events import TraceClosedEvent, TraceRegisteredEvent, event_bus
from infra.telemetry.service import telemetry_monitor
from print.http.v3_studio.dtos import (
    BlueprintPreviewDTO,
    V3CardItemReviewDTO,
    V3CardLibraryItemDTO,
    V3ChunkedApproveRequest,
    V3ChunkedPlanDTO,
    V3ChunkedPlanStartRequest,
    V3ChunkedPlanStateDTO,
    V3ChunkedRegenerateRequest,
    V3ChunkedRetrySectionRequest,
    V3ChunkedStatusDTO,
    V3ConceptCardDTO,
    V3ConceptCardPatchRequest,
    V3GenerationDetailDTO,
    V3GenerationHistoryItemDTO,
    V3InputForm,
    V3PackItemDTO,
    V3PackItemOptionDTO,
    V3PackItemPatchRequest,
    V3PackVariantDTO,
    V3PdfExportRequest,
    V3ReuseConceptCardRequest,
    V3XplorePackDTO,
)
from print.http.v3_studio.generation_writer import V3GenerationWriter
from print.http.v3_studio.preview_mapper import blueprint_to_preview_dto
from print.http.v3_studio.session_store import v3_studio_store
from print.rendering.pdf.cleanup import cleanup_files
from print.rendering.pdf.components.answers_v3 import (
    build_diagnostic_answer_key_content,
)
from print.rendering.pdf.rendering.playwright import PDFRenderError
from print.rendering.pdf.service import (
    NativeDocumentContractError,
    PDFExportRequest,
    export_v3_studio_pdf,
)
from resource_specs.loader import get_spec, list_spec_ids
from resource_specs.renderer import render_spec_for_prompt
from v3_blueprint.models import ProductionBlueprint
from curriculum.items.generator import execute_items
from curriculum.planning.models import (
    ItemOption,
    QuestionBrief,
    SectionBrief,
    StructuralPlan,
    VariantSpec,
    adapt_legacy_structural_plan,
)
from curriculum.planning.persistence import load_chunked_state, persist_chunked_state
from application.unit_lesson.native_pipeline import (
    _approved_card_for_items,
    _chunked_emit_event,
    _chunked_stage2_tasks,
    _contract_version_for_generation,
    _decode_chunked_context,
    _generate_shared_pack_items,
    _load_owned_generation,
    _normalize_chunked_state,
    _normalize_chunked_status,
    _persist_item_results,
    _require_current_native_generation,
    _run_chunked_stage2_pipeline,
)

logger = logging.getLogger(__name__)

_CALLER = "v3_studio"
HEARTBEAT_SECONDS = 15
v3_studio_router = APIRouter(prefix="/v3", tags=["v3-studio"])
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
    except Exception:  # noqa: BLE001
        return {
            "resource_type": resource_type,
            "depth": depth,
            "spec": {},
            "rendered": (
                f"Resource type: {resource_type}\n"
                "(Resource spec unavailable for this type - use judgment based on resource intent.)"
            ),
        }








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
    planning_spec_json: str | None = None,
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
                    planning_spec_json=planning_spec_json,
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
            if planning_spec_json is not None:
                model.planning_spec_json = planning_spec_json
        await session.commit()










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
    native_variant = bool(
        state.get("native_whole_lesson")
        or (
            state.get("context", {}).get("native_whole_lesson")
            if isinstance(state.get("context"), dict)
            else False
        )
    )

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
            planning_spec_json=(
                json.dumps(selected_plan, sort_keys=True)
                if native_variant and isinstance(selected_plan, dict)
                else None
            ),
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
                "native_whole_lesson": native_variant,
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
            raise TypeError("Coordinator structural plan is missing")
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
    except Exception as exc:
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
    # This endpoint creates the historical contract-v1 workflow.  New lessons
    # must originate from the approved unit/path flow, which persists immutable
    # provenance and a native document contract before approval.  Keep the route
    # explicit so direct callers cannot create orphaned legacy rows or state.
    raise HTTPException(
        status_code=410,
        detail="Direct chunked plan start is retired; prepare a lesson from an approved path",
    )


@v3_studio_router.get("/chunked/{generation_id}/plan", response_model=V3ChunkedPlanDTO)
async def get_chunked_plan(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanDTO:
    await _load_owned_generation(generation_id, current_user.id)
    try:
        state = await load_chunked_state(generation_id)
    except Exception as exc:
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
    except Exception as exc:
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
                except TimeoutError:
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
            if needle in f"{card.slug} {card.title} {card.objective}".casefold()
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
                question_id = row.id.removeprefix(prefix)
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
    # Validate immutable current/path provenance and contract v2 before any
    # resume claim, stream registration, task scheduling, or state patch.
    _model, state, _provenance = await _require_current_native_generation(
        generation_id,
        current_user.id,
    )
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
    # Stage 2 is an in-process task. Mark the durable generation row as running
    # before scheduling it so a server restart can reconcile the interrupted
    # task instead of leaving the row at the pre-approval awaiting_review
    # checkpoint while the chunked state says stage2_running.
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is not None:
            generation.status = "running"
            generation.error = None
            generation.error_type = None
            generation.error_code = None
            await session.commit()
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
    # Both current native generations and historical v1 records are read-only
    # through this retired stage-1 handler.  Native recovery uses retry-native;
    # old records remain available to view but cannot restart execution.
    raise HTTPException(
        status_code=409,
        detail="Plan regeneration is retired; generation records are read-only",
    )

@v3_studio_router.post("/chunked/{generation_id}/retry-section", response_model=V3ChunkedPlanStateDTO)
async def post_chunked_retry_section(
    generation_id: str,
    body: V3ChunkedRetrySectionRequest,
    current_user: User = Depends(get_current_user),
) -> V3ChunkedPlanStateDTO:
    model = await _load_owned_generation(generation_id, current_user.id)
    state = await load_chunked_state(generation_id)

    from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson

    if generation_is_native_whole_lesson(state, model):
        from print.generation.whole_lesson.native_retry import (
            NativeRetryConflict,
            accept_native_retry,
        )

        status = str(model.status or state.get("stage") or "")
        try:
            result = await accept_native_retry(
                generation_id, user_id=current_user.id
            )
        except NativeRetryConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error_type": exc.code,
                    "message": str(exc),
                    "stage": exc.status or status,
                    "retry_target": exc.target.value if exc.target else None,
                    "generation_id": generation_id,
                    **(exc.detail or {}),
                },
            ) from exc
        latest = await load_chunked_state(generation_id)
        return _normalize_chunked_state(
            generation_id,
            {
                **latest,
                "stage": result.get("status") or latest.get("stage"),
                "next_action": result.get("next_action") or "wait",
            },
        )

    # Historical v1 retry-section is likewise read-only.  Keep the native branch
    # above because it maps to the checkpointed native retry contract.
    raise HTTPException(
        status_code=409,
        detail="Legacy section retry is retired; generation records are read-only",
    )







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
    from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson
    from print.generation.whole_lesson.native_status import visual_quality_summary

    chunked = dict(model.chunked_state_json or {})
    contract_version = _contract_version_for_generation(model, chunked)
    native_whole_lesson = generation_is_native_whole_lesson(chunked, model) or contract_version >= 2
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
        native_whole_lesson=native_whole_lesson,
        document_contract_version=contract_version,
        visual_quality=visual_quality_summary(chunked),
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
                except TimeoutError:
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
    from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson
    from print.generation.whole_lesson.native_status import visual_quality_summary
    chunked_state = dict(model.chunked_state_json or {})
    if generation_is_native_whole_lesson(chunked_state, model):
        document_json = {
            **document_json,
            "visual_quality": visual_quality_summary(chunked_state),
        }
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
    from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson

    native_whole_lesson = generation_is_native_whole_lesson(
        dict(model.chunked_state_json or {}), model
    )
    document_json = await generation_writer.get_document_json(generation_id, current_user.id)
    if document_json is None:
        if native_whole_lesson:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "NATIVE_DOCUMENT_CONTRACT",
                    "message": "Native generation is missing LectioDocumentV2.",
                },
            )
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
    if not native_whole_lesson and (not isinstance(sections, list) or not sections):
        # Native v2 may store only lectio_document; synthesize section list for legacy PDF path.
        if isinstance(lectio_doc, dict) and isinstance(lectio_doc.get("sections"), list):
            sections = lectio_doc["sections"]
            document_json = {**document_json, "sections": sections}
        else:
            raise HTTPException(status_code=404, detail="Document not found")
    if not native_whole_lesson and (not isinstance(sections, list) or not sections):
        raise HTTPException(status_code=404, detail="Document not found")
    template_id = (
        model.resolved_template_id
        or model.requested_template_id
        or "guided-concept-path"
    )

    auth_token = jwt_handler.create_access_token(current_user.id, current_user.email)
    edition = body.edition or ("teacher" if body.include_answers else "student")
    if edition not in {"teacher", "student"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_EDITION", "message": "edition must be teacher or student"},
        )
    pdf_request = PDFExportRequest(
        school_name=body.school_name,
        teacher_name=body.teacher_name,
        date=body.date,
        include_toc=body.include_toc,
        include_answers=edition == "teacher",
        edition=edition,
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
            native_whole_lesson=native_whole_lesson,
        )
    except NativeDocumentContractError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NATIVE_DOCUMENT_CONTRACT",
                "message": str(exc),
            },
        ) from exc
    except Exception as exc:
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
        except Exception:
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
    except Exception:
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






__all__ = ["v3_studio_router"]

# -- Whole-lesson teaching approach gate (native page documents) --------------
































