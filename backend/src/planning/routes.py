from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from core.rate_limit import limiter

import core.events as core_events
from core.llm import build_model, run_llm
from pipeline.contracts import get_contract, list_template_ids, validate_preset_for_template
from pipeline.types.requests import (
    GenerationMode,
    SectionPlan,
    SectionVisualPolicy,
    count_visual_placements,
    needs_diagram_from_placements,
)
from generation.dtos import GenerationAcceptedResponse
from generation.ports.document_repository import DocumentRepository
from generation.ports.generation_report_repository import (
    GenerationReportRepository,
)
from generation.ports.generation_repository import GenerationRepository
from generation.dependencies import (
    get_document_repository,
    get_generation_engine,
    get_generation_repository,
    get_report_repository,
)
from generation.service import enqueue_generation
from planning.llm_config import get_planning_spec, get_planning_slot
from planning.dtos import BriefRequest, GenerationSpec
from planning import PlanningService, PlanningTemplateContract, StudioBriefRequest
from planning.models import PlanningGenerationSpec, PlanningSectionPlan
from planning.service import (
    BriefPlannerService,
    TemplateSummary,
    _fallback_spec,
)
from core.entities.student_profile import StudentProfile
from core.entities.user import User
from core.dependencies import get_student_profile_repository
from core.ports.student_profile_repository import StudentProfileRepository
from core.auth.middleware import get_current_user
from core.events import TraceClosedEvent, TraceRegisteredEvent

router = APIRouter(prefix="/api/v1", tags=["brief"])
logger = logging.getLogger(__name__)
_PLANNING_CALLER = "brief_interpreter"


def diag(tag: str, **fields) -> None:
    sys.stderr.write(f"DIAG::{tag}::{json.dumps(fields, default=str)}\n")
    sys.stderr.flush()


def _legacy_live_safe_templates() -> list[TemplateSummary]:
    templates: list[TemplateSummary] = []
    for template_id in list_template_ids():
        if not validate_preset_for_template(template_id, "blue-classroom"):
            continue
        contract = get_contract(template_id)
        templates.append(
            TemplateSummary(
                id=contract.id,
                name=contract.name,
                intent=contract.intent,
                learner_fit=list(contract.learner_fit),
            )
        )
    return templates


def _planning_live_safe_templates() -> list[PlanningTemplateContract]:
    templates: list[PlanningTemplateContract] = []
    for template_id in list_template_ids():
        if not validate_preset_for_template(template_id, "blue-classroom"):
            continue
        contract = get_contract(template_id)
        templates.append(PlanningTemplateContract.model_validate(contract.model_dump(mode="json")))
    return templates


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _load_profile(
    user: User,
    profile_repo: StudentProfileRepository,
) -> StudentProfile | None:
    return await profile_repo.find_by_user_id(user.id)


def _pipeline_section_from_planning(
    section: PlanningSectionPlan,
    *,
    always_present: list[str],
    generation_mode: GenerationMode,
) -> SectionPlan:
    selected = list(dict.fromkeys([*always_present, *section.selected_components]))
    needs_diagram = needs_diagram_from_placements(section)
    needs_worked_example = any(
        component == "worked-example-card" for component in selected
    )
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
        source="planning_routes",
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
        bridges_from=None,
        bridges_to=None,
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


@router.post("/brief", response_model=GenerationSpec)
async def create_brief(
    brief: BriefRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    profile_repo: StudentProfileRepository = Depends(get_student_profile_repository),
) -> GenerationSpec:
    logger.warning(
        "Deprecated POST /api/v1/brief used by user_id=%s; prefer /api/v1/brief/stream + /api/v1/brief/commit",
        current_user.id,
    )
    response.headers["Deprecation"] = "true"
    response.headers["Warning"] = (
        '299 - "Deprecated endpoint; use /api/v1/brief/stream and /api/v1/brief/commit."'
    )

    profile = await _load_profile(current_user, profile_repo)
    templates = _legacy_live_safe_templates()
    if not templates:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No live-safe templates are available for blue-classroom.",
        )

    planning_spec = get_planning_spec(_PLANNING_CALLER)
    planning_slot = get_planning_slot(_PLANNING_CALLER)
    trace_id = uuid.uuid4().hex

    async def run_legacy_brief_llm(**kwargs):
        generation_id = kwargs.pop("generation_id", "")
        caller = kwargs.pop("node", _PLANNING_CALLER)
        return await run_llm(
            trace_id=generation_id,
            caller=caller,
            slot=planning_slot,
            spec=planning_spec,
            **kwargs,
        )

    service = BriefPlannerService()
    try:
        core_events.event_bus.publish(
            trace_id,
            TraceRegisteredEvent(
                trace_id=trace_id,
                user_id=current_user.id,
                source="planning",
            ),
        )
        model = build_model(planning_spec)
        return await service.plan(
            brief,
            profile=profile,
            templates=templates,
            model=model,
            run_llm_fn=run_legacy_brief_llm,
            generation_id=trace_id,
        )
    except Exception:
        logger.exception("Legacy brief planning failed; returning fallback spec")
        return _fallback_spec(brief)
    finally:
        core_events.event_bus.publish(
            trace_id,
            TraceClosedEvent(trace_id=trace_id, source="planning"),
        )


@router.post("/brief/stream")
@limiter.limit("20/minute")
async def stream_brief(
    request: Request,
    brief: StudioBriefRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    templates = _planning_live_safe_templates()
    if not templates:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No live-safe templates are available for blue-classroom.",
        )

    planning_spec = get_planning_spec(_PLANNING_CALLER)
    planning_slot = get_planning_slot(_PLANNING_CALLER)
    service = PlanningService()
    trace_id = uuid.uuid4().hex

    async def stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def emit(payload: dict) -> None:
            await queue.put(payload)

        async def run_planning_llm(**kwargs):
            return await run_llm(
                slot=planning_slot,
                spec=planning_spec,
                **kwargs,
            )

        async def run() -> None:
            try:
                core_events.event_bus.publish(
                    trace_id,
                    TraceRegisteredEvent(
                        trace_id=trace_id,
                        user_id=current_user.id,
                        source="planning",
                    ),
                )
                model = build_model(planning_spec)
                spec = await service.plan(
                    brief,
                    contracts=templates,
                    model=model,
                    run_llm_fn=run_planning_llm,
                    generation_id=trace_id,
                    emit=emit,
                )
                await queue.put(
                    {
                        "event": "plan_complete",
                        "data": {"spec": spec.model_dump(mode="json")},
                    }
                )
            except Exception:
                fallback = service.fallback(brief, contracts=templates)
                await queue.put(
                    {
                        "event": "plan_error",
                        "data": {
                            "spec": fallback.model_dump(mode="json"),
                            "warning": fallback.warning,
                        },
                    }
                )
            finally:
                core_events.event_bus.publish(
                    trace_id,
                    TraceClosedEvent(trace_id=trace_id, source="planning"),
                )
                await queue.put(None)

        task = asyncio.create_task(run())
        try:
            while True:
                payload = await queue.get()
                if payload is None:
                    break
                yield _sse_event(payload["event"], payload["data"])
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/contracts", response_model=list[PlanningTemplateContract])
async def list_contracts(
    current_user: User = Depends(get_current_user),
) -> list[PlanningTemplateContract]:
    _ = current_user
    return _planning_live_safe_templates()


@router.post("/brief/commit", response_model=GenerationAcceptedResponse)
async def commit_brief(
    spec: PlanningGenerationSpec,
    current_user: User = Depends(get_current_user),
    profile_repo: StudentProfileRepository = Depends(get_student_profile_repository),
    engine=Depends(get_generation_engine),
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    report_repo: GenerationReportRepository = Depends(get_report_repository),
) -> GenerationAcceptedResponse:
    if not validate_preset_for_template(spec.template_id, spec.preset_id):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid template/preset combination: {spec.template_id}/{spec.preset_id}",
        )

    profile = await _load_profile(current_user, profile_repo)
    committed = spec.model_copy(update={"status": "committed"})
    return await enqueue_generation(
        current_user=current_user,
        profile=profile,
        engine=engine,
        gen_repo=gen_repo,
        document_repo=document_repo,
        report_repo=report_repo,
        subject=committed.source_brief.intent,
        context=_context_from_planning_spec(
            committed,
            subject=committed.source_brief.intent,
        ),
        mode=committed.mode,
        template_id=committed.template_id,
        preset_id=committed.preset_id,
        section_count=len(committed.sections),
        section_plans=_pipeline_sections_from_planning_spec(committed),
        planning_spec_json=committed.model_dump_json(),
    )
