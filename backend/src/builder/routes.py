"""Server persistence for teacher-owned Builder lessons (Phase 2)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from core.auth.jwt_handler import JWTHandler
from core.auth.middleware import get_current_user
from core.dependencies import get_gcs_image_store, get_jwt_handler, get_settings
from core.database.models import EditableLessonModel, GenerationModel
from core.database.session import get_async_session
from core.entities.user import User
from core.rate_limit import limiter
from core.storage.gcs_image_store import GCSImageStore
from generation.pdf_export.context import PDFGenerationContext
from generation.pdf_export.cleanup import cleanup_files
from generation.pdf_export.config import PDFExportConfig
from generation.pdf_export.rendering.playwright import render_generation_print_preflight
from generation.pdf_export.service import PDFExportRequest, export_generation_pdf
from contracts.document import PipelineDocument, PipelineSectionManifestItem
from contracts.lectio import get_component_registry_entry

router = APIRouter(prefix="/api/v1/builder", tags=["builder"])
logger = logging.getLogger(__name__)

_VALID_SOURCES = {"manual", "v3_generation", "template"}
_MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
_MAX_MEDIA_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_MEDIA_UPLOAD_MIME_TYPES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clone_json_tree(value: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Document must be valid JSON") from exc


def _validate_lesson_document_shape(document: dict[str, Any]) -> None:
    payload = _clone_json_tree(document)
    payload_bytes = len(json.dumps(payload).encode("utf-8"))
    if payload_bytes > _MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Document payload exceeds {_MAX_DOCUMENT_BYTES} bytes",
        )

    version = payload.get("version")
    if not isinstance(version, int):
        raise HTTPException(status_code=422, detail="LessonDocument.version must be an integer")

    lesson_id = payload.get("id")
    if not isinstance(lesson_id, str) or not lesson_id.strip():
        raise HTTPException(status_code=422, detail="LessonDocument.id must be a non-empty string")

    sections = payload.get("sections")
    if not isinstance(sections, list):
        raise HTTPException(status_code=422, detail="LessonDocument.sections must be a list")

    blocks = payload.get("blocks")
    if not isinstance(blocks, dict):
        raise HTTPException(status_code=422, detail="LessonDocument.blocks must be an object")

    media = payload.get("media")
    if media is None or not isinstance(media, dict):
        raise HTTPException(status_code=422, detail="LessonDocument.media must be an object")

    known_block_ids = set(blocks.keys())
    for block_id, raw_block in blocks.items():
        if not isinstance(block_id, str) or not block_id.strip():
            raise HTTPException(status_code=422, detail="Block ids must be non-empty strings")
        if not isinstance(raw_block, dict):
            raise HTTPException(status_code=422, detail=f"Block '{block_id}' must be an object")

        component_id = raw_block.get("component_id")
        if not isinstance(component_id, str) or not component_id.strip():
            raise HTTPException(
                status_code=422,
                detail=f"Block '{block_id}' is missing a valid component_id",
            )
        if get_component_registry_entry(component_id) is None:
            raise HTTPException(status_code=400, detail=f"Unknown component_id: {component_id}")

        if "content" not in raw_block:
            raise HTTPException(status_code=422, detail=f"Block '{block_id}' is missing content")

    for section in sections:
        if not isinstance(section, dict):
            raise HTTPException(status_code=422, detail="Each section must be an object")
        block_ids = section.get("block_ids")
        if not isinstance(block_ids, list):
            raise HTTPException(status_code=422, detail="Section block_ids must be a list")
        for block_id in block_ids:
            if not isinstance(block_id, str) or not block_id.strip():
                raise HTTPException(status_code=422, detail="Section block_ids must be non-empty strings")
            if block_id not in known_block_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"Section references missing block id: {block_id}",
                )


def _normalize_document_for_storage(
    document: dict[str, Any],
    *,
    lesson_id: str,
    title: str,
    now_iso: str,
    created_at_value: str | None = None,
) -> dict[str, Any]:
    normalized = _clone_json_tree(document)
    normalized["id"] = lesson_id
    normalized["title"] = title
    if created_at_value:
        normalized["created_at"] = created_at_value
    else:
        normalized.setdefault("created_at", now_iso)
    normalized["updated_at"] = now_iso
    return normalized


class BuilderLessonCreateRequest(BaseModel):
    title: str | None = None
    class_label: str | None = None
    source_generation_id: str | None = None
    source_type: Literal["manual", "v3_generation", "template"] = "manual"
    document: dict[str, Any] = Field(..., description="LessonDocument JSON payload")


class BuilderLessonUpdateRequest(BaseModel):
    title: str | None = None
    class_label: str | None = None
    document: dict[str, Any] = Field(..., description="LessonDocument JSON payload")


class BuilderLessonListItem(BaseModel):
    id: str
    source_generation_id: str | None
    source_type: str
    title: str
    class_label: str | None
    created_at: datetime
    updated_at: datetime


class BuilderLessonDetailResponse(BuilderLessonListItem):
    document: dict[str, Any]


class BuilderMediaUploadResponse(BaseModel):
    id: str
    type: Literal["image"] = "image"
    url: str
    mime_type: str
    filename: str | None = None
    source: Literal["upload"] = "upload"


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


def _to_list_item(model: EditableLessonModel) -> BuilderLessonListItem:
    return BuilderLessonListItem(
        id=model.id,
        source_generation_id=model.source_generation_id,
        source_type=model.source_type,
        title=model.title,
        class_label=model.class_label,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_detail(model: EditableLessonModel) -> BuilderLessonDetailResponse:
    return BuilderLessonDetailResponse(
        **_to_list_item(model).model_dump(),
        document=model.document_json,
    )


def _resolved_title(explicit: str | None, document: dict[str, Any], default: str = "Untitled lesson") -> str:
    title = (explicit or "").strip()
    if title:
        return title
    candidate = document.get("title")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return default


def _normalized_class_label(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def _owned_lesson_or_404(
    session: AsyncSession,
    *,
    lesson_id: str,
    user_id: str,
) -> EditableLessonModel:
    result = await session.execute(
        select(EditableLessonModel).where(
            EditableLessonModel.id == lesson_id,
            EditableLessonModel.user_id == user_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return model


def _first_section_template_id(document: dict[str, Any]) -> str:
    sections = document.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            template_id = section.get("template_id")
            if isinstance(template_id, str) and template_id.strip():
                return template_id.strip()
    return "open-canvas"


def _safe_position(raw_position: Any, fallback: int) -> int:
    if isinstance(raw_position, int):
        return raw_position
    return fallback


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
                section_id=section_id if isinstance(section_id, str) and section_id else f"section-{index}",
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
        preset_id=preset_id if isinstance(preset_id, str) and preset_id.strip() else "blue-classroom",
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
        requested_preset_id=preset_id if isinstance(preset_id, str) and preset_id.strip() else "blue-classroom",
        resolved_preset_id=preset_id if isinstance(preset_id, str) and preset_id.strip() else "blue-classroom",
        quality_passed=True,
    )


def _strip_answers_for_student_doc(document: dict[str, Any]) -> dict[str, Any]:
    stripped = _clone_json_tree(document)
    blocks = stripped.get("blocks")
    if not isinstance(blocks, dict):
        return stripped

    for raw_block in blocks.values():
        if not isinstance(raw_block, dict):
            continue
        component_id = raw_block.get("component_id")
        content = raw_block.get("content")
        if not isinstance(component_id, str) or not isinstance(content, dict):
            continue

        if component_id == "quiz-check":
            options = content.get("options")
            if isinstance(options, list):
                for option in options:
                    if not isinstance(option, dict):
                        continue
                    option["correct"] = False
                    if "explanation" in option:
                        option["explanation"] = ""
            if "feedback_correct" in content:
                content["feedback_correct"] = ""
            if "feedback_incorrect" in content:
                content["feedback_incorrect"] = ""
        elif component_id == "short-answer":
            content.pop("mark_scheme", None)
        elif component_id == "practice-stack":
            problems = content.get("problems")
            if isinstance(problems, list):
                for problem in problems:
                    if isinstance(problem, dict):
                        problem.pop("solution", None)
        elif component_id == "fill-in-blank":
            segments = content.get("segments")
            if isinstance(segments, list):
                for segment in segments:
                    if isinstance(segment, dict):
                        segment.pop("answer", None)

    return stripped


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


def _log_builder_event(
    action: str,
    *,
    user_id: str,
    lesson_id: str | None = None,
    request: Request | None = None,
    **details: Any,
) -> None:
    payload: dict[str, Any] = {
        "action": action,
        "user_id": user_id,
        "lesson_id": lesson_id,
        "request_id": getattr(getattr(request, "state", None), "request_id", None),
    }
    payload.update(details)
    logger.info("builder_event", extra=payload)


@router.post("/lessons", response_model=BuilderLessonDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_builder_lesson(
    body: BuilderLessonCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BuilderLessonDetailResponse:
    if body.source_type not in _VALID_SOURCES:
        raise HTTPException(status_code=422, detail=f"Unsupported source_type: {body.source_type}")
    if body.source_type == "v3_generation" and not body.source_generation_id:
        raise HTTPException(status_code=422, detail="source_generation_id is required for v3_generation")

    if body.source_generation_id:
        generation_result = await session.execute(
            select(GenerationModel.id).where(
                GenerationModel.id == body.source_generation_id,
                GenerationModel.user_id == current_user.id,
            )
        )
        if generation_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Source generation not found")

    _validate_lesson_document_shape(body.document)

    now = _utc_naive_now()
    now_iso = now.isoformat()
    lesson_id = str(uuid.uuid4())
    title = _resolved_title(body.title, body.document)
    document_json = _normalize_document_for_storage(
        body.document,
        lesson_id=lesson_id,
        title=title,
        now_iso=now_iso,
    )

    model = EditableLessonModel(
        id=lesson_id,
        user_id=current_user.id,
        source_generation_id=body.source_generation_id,
        source_type=body.source_type,
        title=title,
        class_label=_normalized_class_label(body.class_label),
        document_json=document_json,
        created_at=now,
        updated_at=now,
    )
    session.add(model)
    await session.commit()
    _log_builder_event(
        "lesson_created",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
        source_type=body.source_type,
        source_generation_id=body.source_generation_id,
    )
    return _to_detail(model)


@router.get("/lessons", response_model=list[BuilderLessonListItem])
async def list_builder_lessons(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[BuilderLessonListItem]:
    result = await session.execute(
        select(EditableLessonModel)
        .where(EditableLessonModel.user_id == current_user.id)
        .order_by(EditableLessonModel.updated_at.desc())
    )
    items = [_to_list_item(model) for model in result.scalars().all()]
    _log_builder_event(
        "lessons_listed",
        user_id=current_user.id,
        request=request,
        lesson_count=len(items),
    )
    return items


@router.get("/lessons/{lesson_id}", response_model=BuilderLessonDetailResponse)
async def get_builder_lesson(
    lesson_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BuilderLessonDetailResponse:
    model = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
    _log_builder_event(
        "lesson_loaded",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
    )
    return _to_detail(model)


@router.put("/lessons/{lesson_id}", response_model=BuilderLessonDetailResponse)
@limiter.limit("120/minute")
async def update_builder_lesson(
    request: Request,
    lesson_id: str,
    body: BuilderLessonUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BuilderLessonDetailResponse:
    model = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
    _validate_lesson_document_shape(body.document)

    now = _utc_naive_now()
    now_iso = now.isoformat()
    title = _resolved_title(body.title, body.document, default=model.title)
    created_at_value = model.document_json.get("created_at") if isinstance(model.document_json, dict) else None
    document_json = _normalize_document_for_storage(
        body.document,
        lesson_id=lesson_id,
        title=title,
        now_iso=now_iso,
        created_at_value=created_at_value if isinstance(created_at_value, str) else None,
    )

    model.title = title
    if "class_label" in body.model_fields_set:
        model.class_label = _normalized_class_label(body.class_label)
    model.document_json = document_json
    model.updated_at = now
    await session.commit()
    _log_builder_event(
        "lesson_saved",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
        payload_bytes=len(json.dumps(document_json).encode("utf-8")),
    )
    return _to_detail(model)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_builder_lesson(
    lesson_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    model = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
    await session.delete(model)
    await session.commit()
    _log_builder_event(
        "lesson_deleted",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/lessons/{lesson_id}/media/upload", response_model=BuilderMediaUploadResponse)
async def upload_builder_lesson_media(
    lesson_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    gcs_store: GCSImageStore = Depends(get_gcs_image_store),
) -> BuilderMediaUploadResponse:
    await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)

    mime_type = (file.content_type or "").strip().lower()
    extension = _ALLOWED_MEDIA_UPLOAD_MIME_TYPES.get(mime_type)
    if not extension:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported media type. Use PNG, JPEG, WebP, or GIF.",
        )

    payload = await file.read()
    if len(payload) > _MAX_MEDIA_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Max size is {_MAX_MEDIA_UPLOAD_BYTES} bytes.",
        )

    if not gcs_store.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media upload is unavailable.",
        )

    media_id = uuid.uuid4().hex
    key = f"editable-lessons/{lesson_id}/media/{media_id}.{extension}"
    uploaded_url = await gcs_store.upload_with_key(
        key=key,
        image_bytes=payload,
        content_type=mime_type,
    )
    if not uploaded_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to upload media.",
        )

    _log_builder_event(
        "media_uploaded",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
        media_id=media_id,
        mime_type=mime_type,
        byte_size=len(payload),
    )

    return BuilderMediaUploadResponse(
        id=media_id,
        url=uploaded_url,
        mime_type=mime_type,
        filename=file.filename,
    )


@router.get("/lessons/{lesson_id}/print-document")
async def get_builder_lesson_print_document(
    lesson_id: str,
    request: Request,
    audience: Literal["student", "teacher"] = "teacher",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    model = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
    if not isinstance(model.document_json, dict):
        raise HTTPException(status_code=422, detail="Stored lesson document is invalid")

    document = _clone_json_tree(model.document_json)
    _log_builder_event(
        "print_document_loaded",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
        audience=audience,
    )
    if audience == "student":
        return _strip_answers_for_student_doc(document)
    return document


@router.post("/lessons/{lesson_id}/export/pdf")
async def export_builder_lesson_pdf(
    lesson_id: str,
    body: BuilderLessonPDFExportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> FileResponse:
    model = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
    if not isinstance(model.document_json, dict):
        raise HTTPException(status_code=422, detail="Stored lesson document is invalid")

    document = _clone_json_tree(model.document_json)
    if body.audience == "student":
        document = _strip_answers_for_student_doc(document)

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
    _log_builder_event(
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
    model = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
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
    _log_builder_event(
        "print_preflight_checked",
        user_id=current_user.id,
        lesson_id=lesson_id,
        request=request,
        audience=audience,
        page_count_estimate=response.page_count_estimate,
        warning_count=len(response.warnings),
    )
    return response



