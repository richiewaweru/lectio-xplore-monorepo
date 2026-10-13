"""Public return-code routes: resume a learner by code, join a class as an existing learner."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database.session import get_async_session
from infra.rate_limit import limiter
from learn.runtime.class_service import accept_class_invite
from learn.runtime_models import LearnClassModel, LearnerIdentityModel
from learn.runtime_service import create_learner_session, resolve_learner_session

router = APIRouter(prefix="/api/v1/learn", tags=["learn-resume"])

_LEGACY_HEX = re.compile(r"^[0-9a-f]{8}$")


class ResumeBody(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class JoinExistingBody(BaseModel):
    invite_code: str = Field(min_length=1, max_length=64)


def normalise_learner_code(raw: str) -> str:
    """Trim, uppercase, spaces -> hyphens. Legacy 8-hex codes stay lowercase."""
    code = re.sub(r"\s+", "-", raw.strip())
    if _LEGACY_HEX.match(code.lower()):
        return code.lower()
    return code.upper()


@router.post("/learners/resume")
@limiter.limit("10/minute")
@limiter.limit("200/day")
async def api_resume_learner(
    request: Request,
    body: ResumeBody,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Public: exchange a learner code for a fresh session (other sessions stay valid)."""
    _ = request
    code = normalise_learner_code(body.code)
    learner = await session.scalar(
        select(LearnerIdentityModel).where(LearnerIdentityModel.invite_code == code)
    )
    if learner is None:
        raise HTTPException(status_code=404, detail="That code was not found")
    sess = await create_learner_session(session, learner_id=learner.id)
    await session.commit()
    return {
        "learner_id": learner.id,
        "display_name": learner.display_name,
        "token": sess.token,
        "session_id": sess.id,
    }


@router.post("/classes/join-existing")
async def api_join_class_existing(
    body: JoinExistingBody,
    x_learner_session: str | None = Header(default=None),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Public same-device join: a learner session proves identity; no new learner is created."""
    learner_session = await resolve_learner_session(session, x_learner_session)
    if learner_session is None:
        raise HTTPException(status_code=401, detail="Learner session required")
    invite = body.invite_code.strip()
    class_row = await session.scalar(
        select(LearnClassModel).where(LearnClassModel.invite_code == invite)
    )
    if class_row is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    membership = await accept_class_invite(
        session, invite_code=invite, learner_id=learner_session.learner_id
    )
    await session.commit()
    return {
        "learner_id": learner_session.learner_id,
        "class_id": membership.class_id,
        "class_name": class_row.name,
    }
