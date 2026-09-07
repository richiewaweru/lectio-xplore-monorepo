"""Application orchestration: Builder lesson → Print PDF export/preflight."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from builder import routes as builder_routes
from contracts.document import PipelineDocument, PipelineSectionManifestItem
from core.auth.jwt_handler import JWTHandler
from core.auth.middleware import get_current_user
from core.dependencies import get_jwt_handler, get_settings
from core.database.session import get_async_session
from core.entities.user import User
from core.rate_limit import limiter
from print.rendering.pdf.cleanup import cleanup_files
from print.rendering.pdf.config import PDFExportConfig
from print.rendering.pdf.context import PDFGenerationContext
from print.rendering.pdf.rendering.playwright import render_generation_print_preflight
from print.rendering.pdf.service import PDFExportRequest, export_generation_pdf

router = APIRouter(prefix="/api/v1/builder", tags=["builder-print"])


class BuilderLessonPDFExportRequest(BaseModel):
    audience: Literal["student", "teacher"] = "teacher"


class BuilderLessonPrintPreflightRequest(BaseModel):
    audience: Literal["student", "teacher"] = "teacher"


class BuilderPrintPreflightImages(BaseModel):
    loaded: int = 0
    failed: int = 0
    timed_out: int = 0


class BuilderPrintPreflightResponse(BaseModel):
    page_count_estimate: int
    oversized_blocks: list[dict[str, Any]] = Field(default_factory=list)
    images: BuilderPrintPreflightImages
    print_contract_coverage: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def _safe_position(raw_position: Any, fallback: int) -> int:
    if isinstance(raw_position, int):
        return raw_position
    return fallback


def _first_section_template_id(document: dict[str, Any]) -> str:
    sections = document.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            template_id = section.get("template_id")
            if isinstance(template_id, str) and template_id.strip():
                return template_id.strip()
    return "guided-concept-path"


def _section_manifest_from_document(document: dict[str, Any]) -> list[PipelineSectionManifestItem]:
    manifest: list[PipelineSectionManifestItem] = []
    sections = document.get("sections")
    if not isinstance(sections, list):
        return manifest
    sortable_sections: list[tuple[int, dict[str, Any]]] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        sortable_sections.append((_safe_position(section.get("position"), index), section))
    sortable_sections.sort(key=lambda item: item[0])
    for index, (_, section) in enumerate(sortable_sections, start=1):
        section_id = section.get("id")
        title = section.get("title")
        position = _safe_position(section.get("position"), index)
        manifest.append(
            PipelineSectionManifestItem(
                section_id=section_id
                if isinstance(section_id, str) and section_id
                else f"section-{index}",
                title=title if isinstance(title, str) and title else f"Section {index}",
                position=position,
            )
        )
    return manifest


def _build_builder_pipeline_document(lesson_id: str, document: dict[str, Any]) -> PipelineDocument:
    subject = document.get("subject")
    description = document.get("description")
    preset_id = document.get("preset_id")
    return PipelineDocument(
        generation_id=lesson_id,
        subject=subject if isinstance(subject, str) and subject.strip() else "Lesson",
        context=description if isinstance(description, str) else "",
        mode="v3",
        template_id=_first_section_template_id(document),
        preset_id=preset_id
        if isinstance(preset_id, str) and preset_id.strip()
        else "blue-classroom",
        status="completed",
        section_manifest=_section_manifest_from_document(document),
        sections=[],
        quality_passed=True,
    )


def _builder_generation_from_document(
    lesson_id: str,
    user_id: str,
    document: dict[str, Any],
) -> PDFGenerationContext:
    subject = document.get("subject")
    description = document.get("description")
    template_id = _first_section_template_id(document)
    preset_id = document.get("preset_id")
    subject_text = subject if isinstance(subject, str) and subject.strip() else "Lesson"
    return PDFGenerationContext(
        id=lesson_id,
        user_id=user_id,
        subject=subject_text,
        context=description if isinstance(description, str) else "",
        mode="v3",
        status="completed",
        requested_template_id=template_id,
        resolved_template_id=template_id,
        requested_preset_id=preset_id
        if isinstance(preset_id, str) and preset_id.strip()
        else "blue-classroom",
        resolved_preset_id=preset_id
        if isinstance(preset_id, str) and preset_id.strip()
        else "blue-classroom",
        quality_passed=True,
    )


def _builder_pdf_request_for_user(current_user: User) -> PDFExportRequest:
    teacher_name = (current_user.name or current_user.email or "Teacher").strip()
    return PDFExportRequest(
        school_name="Lesson Builder",
        teacher_name=teacher_name or "Teacher",
        include_toc=True,
        include_answers=False,
    )


def _int_from_report(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _builder_print_preflight_response(snapshot: dict[str, Any]) -> BuilderPrintPreflightResponse:
    report = snapshot.get("print_layout_report")
    if not isinstance(report, dict):
        report = {}
    oversized = report.get("oversized_blocks")
    oversized_blocks = oversized if isinstance(oversized, list) else []
    coverage = report.get("print_contract_coverage")
    if not isinstance(coverage, dict):
        coverage = {}
    failed_images = _int_from_report(report.get("images_failed"))
    timed_out_images = _int_from_report(report.get("images_timed_out"))
    warnings: list[str] = []
    for block in oversized_blocks:
        if not isinstance(block, dict):
            continue
        label = block.get("block") or block.get("type") or "A block"
        warnings.append(f"Block {label} is taller than one A4 page.")
    if failed_images:
        warnings.append(f"{failed_images} images failed to load.")
    if timed_out_images:
        warnings.append(f"{timed_out_images} images timed out while loading.")
    return BuilderPrintPreflightResponse(
        page_count_estimate=max(1, _int_from_report(report.get("page_count_estimate")) or 1),
        oversized_blocks=[b for b in oversized_blocks if isinstance(b, dict)],
        images=BuilderPrintPreflightImages(
            loaded=_int_from_report(report.get("images_loaded")),
            failed=failed_images,
            timed_out=timed_out_images,
        ),
        print_contract_coverage=coverage,
        warnings=warnings,
    )


@router.post("/lessons/{lesson_id}/export/pdf")
async def export_builder_lesson_pdf(
    lesson_id: str,
    body: BuilderLessonPDFExportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> FileResponse:
    model = await builder_routes._owned_lesson_or_404(
        session, lesson_id=lesson_id, user_id=current_user.id
    )
    if not isinstance(model.document_json, dict):
        raise HTTPException(status_code=422, detail="Stored lesson document is invalid")

    document = builder_routes._clone_json_tree(model.document_json)
    if body.audience == "student":
        document = builder_routes._strip_answers_for_student_doc(document)

    generation = _builder_generation_from_document(lesson_id, current_user.id, document)
    pipeline_document = _build_builder_pipeline_document(lesson_id, document)
    auth_token = jwt_handler.create_access_token(current_user.id, current_user.email)
    export_request = _builder_pdf_request_for_user(current_user)
    result = await export_generation_pdf(
        generation=generation,
        document=pipeline_document,
        auth_token=auth_token,
        request=export_request,
        settings=get_settings(),
        request_id=getattr(request.state, "request_id", None),
        render_path=f"/builder/print/{lesson_id}?audience={body.audience}",
    )
    builder_routes._log_builder_event(
        "pdf_exported",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
        audience=body.audience,
        page_count=result.page_count,
        file_size_bytes=result.file_size_bytes,
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


@router.post("/lessons/{lesson_id}/print-preflight", response_model=BuilderPrintPreflightResponse)
@limiter.limit("6/minute")
async def print_preflight_builder_lesson(
    request: Request,
    lesson_id: str,
    body: BuilderLessonPrintPreflightRequest | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> BuilderPrintPreflightResponse:
    model = await builder_routes._owned_lesson_or_404(
        session, lesson_id=lesson_id, user_id=current_user.id
    )
    if not isinstance(model.document_json, dict):
        raise HTTPException(status_code=422, detail="Stored lesson document is invalid")

    audience = body.audience if body is not None else "teacher"
    settings = get_settings()
    config = PDFExportConfig(settings)
    if not config.enabled:
        raise HTTPException(status_code=503, detail="Print preflight is disabled")

    auth_token = jwt_handler.create_access_token(current_user.id, current_user.email)
    snapshot = await render_generation_print_preflight(
        generation_id=lesson_id,
        auth_token=auth_token,
        config=config,
        render_path=f"/builder/print/{lesson_id}?audience={audience}",
    )
    response = _builder_print_preflight_response(snapshot)
    builder_routes._log_builder_event(
        "print_preflight_checked",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
        audience=audience,
        page_count_estimate=response.page_count_estimate,
        warning_count=len(response.warnings),
    )
    return response
