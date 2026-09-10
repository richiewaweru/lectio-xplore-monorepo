"""Server persistence for teacher-owned Builder lessons (Phase 2)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.auth.jwt_handler import JWTHandler
from infra.auth.middleware import get_current_user
from infra.dependencies import get_gcs_image_store, get_jwt_handler, get_settings
from core.database.models import EditableLessonModel, GenerationModel
from infra.database.session import get_async_session
from core.entities.user import User
from infra.rate_limit import limiter
from infra.storage.gcs_image_store import GCSImageStore
from learn.authoring.builder.service import (
    ACTIVE_BUILDER_SOURCE_TYPES,
    ComponentLectioBuilderError,
    get_or_create_native_learn_builder_lesson,
    validate_builder_document,
)
from learn.generation.pipeline_dispatch import COMPONENT_LECTIO_RETIRED
from contracts.lectio import get_component_registry_entry
from learn.generation.interaction_writer import validate_interaction_contract

router = APIRouter(prefix="/api/v1/builder", tags=["builder"])
logger = logging.getLogger(__name__)

_VALID_SOURCES = {
    "manual",
    "v3_generation",
    "template",
    "document",
    "learn_document",
    "native_learn",
}
_ACTIVE_SOURCES = set(ACTIVE_BUILDER_SOURCE_TYPES)
_RETIRED_SOURCES = {"v3_generation", "v3_studio", "legacy", "legacy_unit", "component_lectio"}
_LEGACY_PIPELINE_RETIRED = {
    "code": "legacy_pipeline_retired",
    "message": "The Legacy Studio pipeline has been retired. Use the Units workflow.",
}
_COMPONENT_LECTIO_RETIRED = {
    "code": "component_lectio_retired",
    "message": COMPONENT_LECTIO_RETIRED,
}
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
    if version == 2:
        errors = validate_builder_document(payload)
        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))
        return

    # Deprecated LessonDocument v1 (component/sections/blocks) until Phase M.
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

        contract = raw_block.get("learn_interaction") or raw_block.get("interaction")
        if isinstance(contract, dict):
            errors = validate_interaction_contract(contract)
            if errors:
                raise HTTPException(
                    status_code=422,
                    detail=f"Block '{block_id}' interaction invalid: {'; '.join(errors)}",
                )

    for section in sections:
        if not isinstance(section, dict):
            raise HTTPException(status_code=422, detail="Each section must be an object")
        block_ids = section.get("block_ids")
        if not isinstance(block_ids, list):
            raise HTTPException(status_code=422, detail="Section block_ids must be a list")
        for block_id in block_ids:
            if not isinstance(block_id, str) or not block_id.strip():
                raise HTTPException(
                    status_code=422, detail="Section block_ids must be non-empty strings"
                )
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
    source_type: Literal[
        "manual",
        "v3_generation",
        "component_lectio",
        "template",
        "document",
        "learn_document",
        "native_learn",
    ] = "manual"
    document: dict[str, Any] = Field(..., description="LessonDocument / LearnDocument JSON payload")


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


def _resolved_title(
    explicit: str | None, document: dict[str, Any], default: str = "Untitled lesson"
) -> str:
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
    if model.source_type in _RETIRED_SOURCES or str(model.source_type).startswith("legacy"):
        raise HTTPException(status_code=410, detail=_LEGACY_PIPELINE_RETIRED)
    if model.source_type not in _ACTIVE_SOURCES:
        # Unknown source types are not enumerated through the active Builder
        # surface, even if a stale row happens to be owned by this user.
        raise HTTPException(status_code=404, detail="Lesson not found")
    return model


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


@router.post(
    "/lessons", response_model=BuilderLessonDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_builder_lesson(
    body: BuilderLessonCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BuilderLessonDetailResponse:
    if body.source_type not in _VALID_SOURCES:
        if body.source_type in _RETIRED_SOURCES:
            raise HTTPException(
                status_code=410,
                detail=_COMPONENT_LECTIO_RETIRED
                if body.source_type == "component_lectio"
                else _LEGACY_PIPELINE_RETIRED,
            )
        raise HTTPException(status_code=422, detail=f"Unsupported source_type: {body.source_type}")
    if body.source_type == "v3_generation":
        raise HTTPException(status_code=410, detail=_LEGACY_PIPELINE_RETIRED)
    if body.source_type == "component_lectio":
        raise HTTPException(status_code=410, detail=_COMPONENT_LECTIO_RETIRED)
    if body.source_type in {"v3_generation"} and not body.source_generation_id:
        raise HTTPException(
            status_code=422,
            detail=f"source_generation_id is required for {body.source_type}",
        )

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


@router.post(
    "/lessons/from-component-lectio/{generation_id}",
    response_model=BuilderLessonDetailResponse,
)
async def open_component_lectio_builder_lesson(
    generation_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BuilderLessonDetailResponse:
    _ = (generation_id, request, current_user, session)
    raise HTTPException(status_code=410, detail=_COMPONENT_LECTIO_RETIRED)


@router.post(
    "/lessons/from-native-learn/{generation_id}",
    response_model=BuilderLessonDetailResponse,
)
async def open_native_learn_builder_lesson(
    generation_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BuilderLessonDetailResponse:
    generation_result = await session.execute(
        select(GenerationModel).where(
            GenerationModel.id == generation_id,
            GenerationModel.user_id == current_user.id,
        )
    )
    generation = generation_result.scalar_one_or_none()
    if generation is None:
        raise HTTPException(status_code=404, detail="Source generation not found")

    try:
        lesson = await get_or_create_native_learn_builder_lesson(
            session,
            generation=generation,
            user_id=current_user.id,
        )
        await session.commit()
    except ComponentLectioBuilderError as exc:
        await session.rollback()
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _log_builder_event(
        "native_learn_lesson_opened",
        user_id=current_user.id,
        lesson_id=lesson.id,
        request=request,
        source_type=lesson.source_type,
        source_generation_id=generation_id,
    )
    return _to_detail(lesson)


@router.get("/lessons", response_model=list[BuilderLessonListItem])
async def list_builder_lessons(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[BuilderLessonListItem]:
    result = await session.execute(
        select(EditableLessonModel)
        .where(
            EditableLessonModel.user_id == current_user.id,
            EditableLessonModel.source_type.in_(_ACTIVE_SOURCES),
        )
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
    created_at_value = (
        model.document_json.get("created_at") if isinstance(model.document_json, dict) else None
    )
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


