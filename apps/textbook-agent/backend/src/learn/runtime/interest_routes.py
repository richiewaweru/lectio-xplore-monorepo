"""Interest capture: public note from demo visitors, teacher-only list."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.user import User
from infra.auth.middleware import get_current_user
from infra.database.models import InterestMessageModel, LearnerIdentityModel
from infra.database.session import get_async_session
from infra.rate_limit import limiter
from learn.runtime.runtime_service import resolve_learner_session

router = APIRouter(prefix="/api/v1/learn", tags=["learn-interest"])

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^[0-9+()\-.\s]{6,30}$")


class InterestBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    source: Literal["home", "topic"] = "home"
    website: str | None = Field(default=None, max_length=500)  # honeypot

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v

    @field_validator("email", "phone", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("email")
    @classmethod
    def _email_shape(cls, v: str | None) -> str | None:
        if v is not None and not _EMAIL.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("phone")
    @classmethod
    def _phone_shape(cls, v: str | None) -> str | None:
        if v is not None and (not _PHONE.match(v) or sum(c.isdigit() for c in v) < 6):
            raise ValueError("Enter a valid phone number")
        return v

    @model_validator(mode="after")
    def _needs_contact(self) -> InterestBody:
        if not self.email and not self.phone:
            raise ValueError("Add an email or a phone number")
        return self


class InterestOut(BaseModel):
    id: str
    display_name: str | None
    email: str | None
    phone: str | None
    message: str
    source: str
    created_at: datetime


@router.post("/interest")
@limiter.limit("5/minute")
@limiter.limit("30/day")
async def api_submit_interest(
    request: Request,
    body: InterestBody,
    x_learner_session: str | None = Header(default=None),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, bool]:
    """Public: store a note. A learner session is optional and only adds attribution."""
    _ = request
    if body.website:  # honeypot: pretend success, store nothing
        return {"ok": True}
    learner_id: str | None = None
    display_name: str | None = None
    learner_session = await resolve_learner_session(session, x_learner_session)
    if learner_session is not None:
        learner = await session.get(LearnerIdentityModel, learner_session.learner_id)
        if learner is not None:
            learner_id = learner.id
            display_name = learner.display_name
    session.add(
        InterestMessageModel(
            learner_id=learner_id,
            display_name=display_name,
            email=body.email,
            phone=body.phone,
            message=body.message,
            source=body.source,
        )
    )
    await session.commit()
    return {"ok": True}


@router.get("/interest", response_model=list[InterestOut])
async def api_list_interest(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[InterestOut]:
    """Teacher: newest notes first."""
    _ = current_user
    rows = await session.scalars(
        select(InterestMessageModel)
        .order_by(InterestMessageModel.created_at.desc(), InterestMessageModel.id)
        .limit(limit)
        .offset(offset)
    )
    return [
        InterestOut(
            id=r.id,
            display_name=r.display_name,
            email=r.email,
            phone=r.phone,
            message=r.message,
            source=r.source,
            created_at=r.created_at,
        )
        for r in rows
    ]
