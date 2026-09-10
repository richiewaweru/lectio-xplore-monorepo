"""Explicit immutable LearnRelease publishing (Phase 05 / P06)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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
from learn.publishing.publish_validation import (
    PublishValidationError,
    validate_publishable_lesson_document,
)

router = APIRouter(prefix="/api/v1/learn", tags=["learn-releases"])

_MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
_ACTIVE_SOURCES = {"manual", "template", "native_learn", "learn_document", "document"}
_MAX_RELEASE_ALLOC_ATTEMPTS = 8


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
    """Legacy shape check kept for callers; publish uses full validation."""
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


def _validate_for_publish(document: dict[str, Any]) -> None:
    payload = _clone_json_tree(document)
    payload_bytes = len(json.dumps(payload).encode("utf-8"))
    if payload_bytes > _MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Document payload exceeds {_MAX_DOCUMENT_BYTES} bytes",
        )
    try:
        validate_publishable_lesson_document(payload)
    except PublishValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "PUBLISH_VALIDATION", "errors": exc.errors}) from exc


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

    Unit-path sourced lessons use the generation's *pinned* LessonProvenance
    revision/objective_hash. Never stamp today's live PathLesson.revision onto
    an older draft (P06-L06 / 04_RUNTIME_AND_RELEASE).

    Manual Builder lessons may leave all three null. Explicit path_lesson_id
    without generation provenance (manual attach) may use the live PathLesson
    identity only when no pinned provenance exists.
    """
    pinned_path_lesson_id: str | None = None
    pinned_revision: int | None = None
    pinned_objective: str | None = None

    if lesson.source_generation_id:
        generation = await session.get(GenerationModel, lesson.source_generation_id)
        if generation is not None and generation.pack_id:
            provenance = await session.get(LessonProvenanceModel, generation.pack_id)
            if provenance is not None:
                if provenance.path_lesson_id:
                    pinned_path_lesson_id = provenance.path_lesson_id
                if provenance.path_lesson_revision is not None:
                    pinned_revision = int(provenance.path_lesson_revision)
                if provenance.objective_hash:
                    pinned_objective = provenance.objective_hash

    path_lesson_id = explicit_path_lesson_id or pinned_path_lesson_id

    if path_lesson_id is None:
        # Manual drafts: provenance fields remain null.
        return None, None, None

    # Prefer pinned provenance when the draft was generated from a unit path.
    if pinned_path_lesson_id and path_lesson_id == pinned_path_lesson_id:
        if pinned_revision is None or not pinned_objective:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "PINNED_PROVENANCE_REQUIRED",
                    "message": (
                        "Unit-path publish requires pinned path_lesson_revision and "
                        "objective_hash on LessonProvenance; refusing to stamp live PathLesson"
                    ),
                },
            )
        # Ownership check: path lesson must still exist, but revision is pinned.
        path_lesson = await session.get(PathLessonModel, path_lesson_id)
        if path_lesson is None:
            raise HTTPException(
                status_code=422,
                detail=f"path_lesson_id {path_lesson_id} not found",
            )
        return path_lesson_id, pinned_revision, pinned_objective

    if pinned_path_lesson_id and explicit_path_lesson_id and explicit_path_lesson_id != pinned_path_lesson_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PROVENANCE_PATH_MISMATCH",
                "message": (
                    f"explicit path_lesson_id {explicit_path_lesson_id!r} does not match "
                    f"pinned generation provenance {pinned_path_lesson_id!r}"
                ),
            },
        )

    # Manual attach: no generation pin — use live PathLesson identity.
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
    idempotent_replay: bool = False


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
    idempotency_key: str | None = Field(default=None, max_length=128)


def _to_response(model: LearnReleaseModel, *, idempotent_replay: bool = False) -> LearnReleaseResponse:
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
        idempotent_replay=idempotent_replay,
    )


async def _latest_release_for_hash(
    session: AsyncSession, *, lesson_id: str, digest: str
) -> LearnReleaseModel | None:
    result = await session.execute(
        select(LearnReleaseModel)
        .where(
            LearnReleaseModel.editable_lesson_id == lesson_id,
            LearnReleaseModel.document_hash == digest,
        )
        .order_by(LearnReleaseModel.release_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _allocate_next_release_number(session: AsyncSession, *, lesson_id: str) -> int:
    """Allocate the next release number under a row lock on the editable lesson."""
    # Lock the parent lesson so concurrent publishers serialize number allocation.
    locked = await session.execute(
        select(EditableLessonModel)
        .where(EditableLessonModel.id == lesson_id)
        .with_for_update()
    )
    if locked.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    next_number = await session.scalar(
        select(func.coalesce(func.max(LearnReleaseModel.release_number), 0)).where(
            LearnReleaseModel.editable_lesson_id == lesson_id
        )
    )
    return int(next_number or 0) + 1


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
    idempotency_key_header: str | None = Header(default=None, alias="Idempotency-Key"),
) -> LearnReleaseResponse:
    body = body or PublishLearnReleaseRequest()
    lesson = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
    document = _clone_json_tree(lesson.document_json if isinstance(lesson.document_json, dict) else {})
    _validate_for_publish(document)

    path_lesson_id, path_lesson_revision, objective_hash = await resolve_release_provenance(
        session, lesson=lesson, explicit_path_lesson_id=body.path_lesson_id
    )

    snapshot = _clone_json_tree(document)
    digest = document_hash(snapshot)

    # Idempotent double-click: identical draft hash returns the existing release.
    existing = await _latest_release_for_hash(session, lesson_id=lesson.id, digest=digest)
    if existing is not None:
        return _to_response(existing, idempotent_replay=True)

    # Optional idempotency key: store in title metadata is insufficient; treat as
    # soft hint by re-checking hash after lock (above covers same-document clicks).
    _ = body.idempotency_key or idempotency_key_header

    last_error: Exception | None = None
    for _attempt in range(_MAX_RELEASE_ALLOC_ATTEMPTS):
        try:
            release_number = await _allocate_next_release_number(session, lesson_id=lesson.id)
            # Re-check idempotency under lock in case a twin commit landed.
            existing = await _latest_release_for_hash(session, lesson_id=lesson.id, digest=digest)
            if existing is not None:
                response = _to_response(existing, idempotent_replay=True)
                await session.rollback()
                return response

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
        except IntegrityError as exc:
            last_error = exc
            await session.rollback()
            # Re-load lesson after rollback for the next attempt.
            lesson = await _owned_lesson_or_404(session, lesson_id=lesson_id, user_id=current_user.id)
            existing = await _latest_release_for_hash(session, lesson_id=lesson.id, digest=digest)
            if existing is not None:
                return _to_response(existing, idempotent_replay=True)
            continue

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Could not allocate a unique release number: {last_error}",
    )


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
