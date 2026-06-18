from __future__ import annotations

import asyncio

import core.events as core_events
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from core.auth.jwt_handler import JWTHandler
from core.auth.middleware import get_current_user
from core.dependencies import (
    get_jwt_handler,
    get_settings,
    get_student_profile_repository,
    get_user_repository,
)
from core.entities.user import User
from core.ports.student_profile_repository import StudentProfileRepository
from core.ports.user_repository import UserRepository
from core.rate_limit import limiter
from generation import service as generation_service
from generation.block_generate_routes import block_generate_router
from generation.dependencies import (
    get_document_repository,
    get_generation_engine,
    get_generation_repository,
)
from generation.dtos import GenerationAcceptedResponse, GenerationRequest
from generation.pdf_export.cleanup import cleanup_files
from generation.pdf_export.service import PDFExportRequest, export_generation_pdf
from generation.ports.document_repository import DocumentRepository
from generation.ports.generation_repository import GenerationRepository
from generation.v3_studio.router import v3_studio_router
from pipeline.adapter import run_pipeline_streaming
from pipeline.api import PipelineCommand as _PipelineCommand
from telemetry.dependencies import get_report_repository
from telemetry.ports.generation_report_repository import GenerationReportRepository

PipelineCommand = _PipelineCommand

router = APIRouter(prefix="/api/v1", tags=["generation"])
router.include_router(v3_studio_router)
router.include_router(block_generate_router)

# Re-export the service-layer symbols that the route tests exercise directly.
event_bus = core_events.event_bus
_SSE_KEEPALIVE_TIMEOUT_SECONDS = generation_service._SSE_KEEPALIVE_TIMEOUT_SECONDS
_persist_failed_generation_state = generation_service._persist_failed_generation_state
_generation_job_timeout = generation_service._generation_job_timeout
_ASYNCIO_COMPAT = asyncio


class _PatchedPipelineEngine:
    async def run_streaming(self, command, on_event=None):
        return await run_pipeline_streaming(command, on_event=on_event)


async def _run_generation_job(
    generation,
    command,
    gen_repo,
    document_repo,
    report_repo,
    initial_document,
):
    original_persist_failed_generation_state = (
        generation_service._persist_failed_generation_state
    )
    original_generation_job_timeout = generation_service._generation_job_timeout
    try:
        generation_service._persist_failed_generation_state = (
            _persist_failed_generation_state
        )
        generation_service._generation_job_timeout = _generation_job_timeout
        return await generation_service._run_generation_job(
            generation,
            command,
            _PatchedPipelineEngine(),
            gen_repo,
            document_repo,
            report_repo,
            initial_document,
        )
    finally:
        generation_service._persist_failed_generation_state = (
            original_persist_failed_generation_state
        )
        generation_service._generation_job_timeout = original_generation_job_timeout


@router.post("/generations", status_code=202, response_model=GenerationAcceptedResponse)
@limiter.limit("10/minute")
async def create_generation(
    request: Request,
    req: GenerationRequest,
    current_user: User = Depends(get_current_user),
    profile_repo: StudentProfileRepository = Depends(get_student_profile_repository),
    engine=Depends(get_generation_engine),
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
    ) = generation_service._effective_generation_payload(req)

    profile = await profile_repo.find_by_user_id(current_user.id)
    return await generation_service.enqueue_generation(
        current_user=current_user,
        profile=profile,
        engine=engine,
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
    return [generation_service._history_item(generation) for generation in generations]


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
    return generation_service._detail_item(generation, report=report)


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


@router.post("/generations/{generation_id}/export/pdf")
async def export_generation_pdf_route(
    generation_id: str,
    body: PDFExportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
):
    generation = await gen_repo.find_by_id(generation_id)
    if generation is None or generation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    if generation.status != "completed":
        raise HTTPException(
            status_code=409,
            detail="PDF export is only available for completed generations",
        )

    document_ref = generation.document_path or generation.id
    try:
        document = await document_repo.load_document(document_ref)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    auth_token = jwt_handler.create_access_token(current_user.id, current_user.email)
    result = await export_generation_pdf(
        generation=generation,
        document=document,
        auth_token=auth_token,
        request=body,
        settings=get_settings(),
        request_id=getattr(request.state, "request_id", None),
    )
    return FileResponse(
        path=result.pdf_path,
        media_type="application/pdf",
        filename=result.filename,
        headers={
            "X-Page-Count": str(result.page_count),
            "X-File-Size": str(result.file_size_bytes),
            "X-Generation-Time-Ms": str(result.generation_time_ms),
        },
        background=BackgroundTask(cleanup_files, result.cleanup_paths),
    )


@router.get("/generations/{generation_id}/events")
async def get_generation_events(
    generation_id: str,
    request: Request,
    gen_repo: GenerationRepository = Depends(get_generation_repository),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    user_repo: UserRepository = Depends(get_user_repository),
):
    current_user = await generation_service._stream_user_from_token(
        request,
        jwt_handler,
        user_repo,
    )
    generation = await gen_repo.find_by_id(generation_id)
    if generation is None or generation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")

    return StreamingResponse(
        generation_service._stream_generation_events(
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


router.include_router(block_generate_router)
