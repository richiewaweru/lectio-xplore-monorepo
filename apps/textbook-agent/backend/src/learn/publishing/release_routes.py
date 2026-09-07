"""Explicit immutable LearnRelease publishing (Phase 05)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.auth.middleware import get_current_user
from core.database.models import (
    EditableLessonModel,
    GenerationModel,
    LearnReleaseModel,
    LessonProvenanceModel,
    PathLessonModel,
)
from infra.database.session import get_async_session
from core.entities.user import User

router = APIRouter(prefix="/api/v1/learn", tags=["learn-releases"])

_MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
_ACTIVE_SOURCES = {"manual", "component_lectio", "template"}


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def document_hash(document: dict[str, Any]) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    if not isinstance(payload.get("version"), int):
        raise HTTPException(status_code=422, detail="LessonDocument.version must be an integer")
    lesson_id = payload.get("id")
    if not isinstance(lesson_id, str) or not lesson_id.strip():
        raise HTTPException(status_code=422, detail="LessonDocument.id must be a non-empty string")
    if not isinstance(payload.get("sections"), list):
        raise HTTPException(status_code=422, detail="LessonDocument.sections must be a list")
    if not isinstance(payload.get("blocks"), dict):
        raise HTTPException(status_code=422, detail="LessonDocument.blocks must be an object")
    media = payload.get("media")
    if media is None or not isinstance(media, dict):
        raise HTTPException(status_code=422, detail="LessonDocument.media must be an object")


async def _owned_lesson_or_404(
    session: AsyncSession, *, lesson_id: str, user_id: str
) -> EditableLessonModel:
    result = await session.execute(
        select(EditableLessonModel).where(
            EditableLessonModel.id == lesson_id,
            EditableLessonModel.user_id == user_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None or model.source_type not in _ACTIVE_SOURCES:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return model


async def resolve_release_provenance(
    session: AsyncSession,
    *,
    lesson: EditableLessonModel,
    explicit_path_lesson_id: str | None,
) -> tuple[str | None, int | None, str | None]:
    """Resolve path_lesson_id / revision / objective_hash for a publish.

    Unit-path sourced lessons (path_lesson resolved) require revision + objective_hash.
    Manual Builder lessons may leave all three null.
    """
    path_lesson_id = explicit_path_lesson_id

    if path_lesson_id is None and lesson.source_generation_id:
        generation = await session.get(GenerationModel, lesson.source_generation_id)
        if generation is not None and generation.pack_id:
            provenance = await session.get(LessonProvenanceModel, generation.pack_id)
            if provenance is not None and provenance.path_lesson_id:
                path_lesson_id = provenance.path_lesson_id

    if path_lesson_id is None:
        # Manual drafts: provenance fields remain null.
        return None, None, None

    path_lesson = await session.get(PathLessonModel, path_lesson_id)
    if path_lesson is None:
        raise HTTPException(
            status_code=422,
            detail=f"path_lesson_id {path_lesson_id} not found",
        )

    revision = int(path_lesson.revision)
    objective = path_lesson.objective_hash
    if not objective:
        raise HTTPException(
            status_code=422,
            detail="Unit-path publish requires objective_hash on PathLesson",
        )
    return path_lesson_id, revision, objective


class LearnReleaseResponse(BaseModel):
    id: str
    editable_lesson_id: str
    release_number: int
    title: str
    document_hash: str
    source_generation_id: str | None = None
    path_lesson_id: str | None = None
    path_lesson_revision: int | None = None
    objective_hash: str | None = None
    status: str
    published_at: datetime
    document: dict[str, Any]


class LearnReleaseListItem(BaseModel):
    id: str
    editable_lesson_id: str
    release_number: int
    title: str
    document_hash: str
    path_lesson_id: str | None = None
    path_lesson_revision: int | None = None
    objective_hash: str | None = None
    status: str
    published_at: datetime


class PublishLearnReleaseRequest(BaseModel):
    path_lesson_id: str | None = None
    title: str | None = Field(default=None, max_length=200)


def _to_response(model: LearnReleaseModel) -> LearnReleaseResponse:
    return LearnReleaseResponse(
        id=model.id,
        editable_lesson_id=model.editable_lesson_id,
        release_number=model.release_number,
        title=model.title,
        document_hash=model.document_hash,
        source_generation_id=model.source_generation_id,
        path_lesson_id=model.path_lesson_id,
        path_lesson_revision=model.path_lesson_revision,
        objective_hash=model.objective_hash,
        status=model.status,
        published_at=model.published_at,
        document=model.document_json if isinstance(model.document_json, dict) else {},
    )


@router.post(
    "/lessons/{lesson_id}/releases",
    response_model=LearnReleaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_learn_release(
    lesson_id: str,
    body: PublishLearnReleaseRequest | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> LearnReleaseResponse:
    body = body or PublishLearnReleaseRequest()
    lesson = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
    document = _clone_json_tree(lesson.document_json if isinstance(lesson.document_json, dict) else {})
    _validate_lesson_document_shape(document)

    path_lesson_id, path_lesson_revision, objective_hash = await resolve_release_provenance(
        session, lesson=lesson, explicit_path_lesson_id=body.path_lesson_id
    )

    next_number = await session.scalar(
        select(func.coalesce(func.max(LearnReleaseModel.release_number), 0)).where(
            LearnReleaseModel.editable_lesson_id == lesson.id
        )
    )
    release_number = int(next_number or 0) + 1
    snapshot = _clone_json_tree(document)
    digest = document_hash(snapshot)
    now = _utc_naive_now()
    release = LearnReleaseModel(
        id=str(uuid.uuid4()),
        editable_lesson_id=lesson.id,
        owner_user_id=current_user.id,
        release_number=release_number,
        title=(body.title or lesson.title or "Untitled lesson").strip() or "Untitled lesson",
        document_json=snapshot,
        document_hash=digest,
        source_generation_id=lesson.source_generation_id,
        path_lesson_id=path_lesson_id,
        path_lesson_revision=path_lesson_revision,
        objective_hash=objective_hash,
        status="published",
        published_at=now,
        created_at=now,
    )
    session.add(release)
    await session.commit()
    await session.refresh(release)
    return _to_response(release)


@router.get("/lessons/{lesson_id}/releases", response_model=list[LearnReleaseListItem])
async def list_learn_releases(
    lesson_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[LearnReleaseListItem]:
    await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
    result = await session.execute(
        select(LearnReleaseModel)
        .where(
            LearnReleaseModel.editable_lesson_id == lesson_id,
            LearnReleaseModel.owner_user_id == current_user.id,
        )
        .order_by(LearnReleaseModel.release_number.asc())
    )
    rows = result.scalars().all()
    return [
        LearnReleaseListItem(
            id=row.id,
            editable_lesson_id=row.editable_lesson_id,
            release_number=row.release_number,
            title=row.title,
            document_hash=row.document_hash,
            path_lesson_id=row.path_lesson_id,
            path_lesson_revision=row.path_lesson_revision,
            objective_hash=row.objective_hash,
            status=row.status,
            published_at=row.published_at,
        )
        for row in rows
    ]


@router.get("/releases/{release_id}", response_model=LearnReleaseResponse)
async def get_learn_release(
    release_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> LearnReleaseResponse:
    result = await session.execute(
        select(LearnReleaseModel).where(
            LearnReleaseModel.id == release_id,
            LearnReleaseModel.owner_user_id == current_user.id,
        )
    )
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(status_code=404, detail="LearnRelease not found")
    return _to_response(release)
