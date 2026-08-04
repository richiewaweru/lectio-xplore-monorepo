"""Lesson Builder: public share links for read-only lesson views."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.middleware import get_current_user
from core.config import settings
from core.database.models import LessonShareModel
from core.database.session import get_async_session
from core.entities.user import User

router = APIRouter(prefix="/api/v1/shares", tags=["shares"])

_DEFAULT_EXPIRES_SECONDS = 30 * 24 * 60 * 60


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CreateShareBody(BaseModel):
    document: dict = Field(..., description="LessonDocument JSON")
    expires_in: int | None = Field(None, ge=60, le=365 * 24 * 60 * 60)
    allow_download: bool = False


class CreateShareResponse(BaseModel):
    share_id: str
    url: str
    expires_at: datetime


class ShareGetResponse(BaseModel):
    document: dict
    allow_download: bool


@router.post("", response_model=CreateShareResponse)
async def create_share(
    body: CreateShareBody,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CreateShareResponse:
    share_id = secrets.token_urlsafe(12)
    seconds = body.expires_in if body.expires_in is not None else _DEFAULT_EXPIRES_SECONDS
    expires_at = _utc_naive_now() + timedelta(seconds=seconds)
    row = LessonShareModel(
        id=share_id,
        document_json=body.document,
        expires_at=expires_at,
        allow_download=body.allow_download,
        created_at=_utc_naive_now(),
    )
    session.add(row)
    await session.commit()
    base = settings.lesson_builder_public_url.rstrip("/")
    url = f"{base}/shared/{share_id}"
    return CreateShareResponse(share_id=share_id, url=url, expires_at=expires_at)


@router.get("/{share_id}", response_model=ShareGetResponse)
async def get_share(
    share_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> ShareGetResponse:
    result = await session.execute(select(LessonShareModel).where(LessonShareModel.id == share_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if row.expires_at < _utc_naive_now():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share expired")
    return ShareGetResponse(document=row.document_json, allow_download=row.allow_download)
