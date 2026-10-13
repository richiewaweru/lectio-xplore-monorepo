"""Read-only topic path for a learner (doc 38 3.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.user import User
from infra.auth.middleware import get_optional_user
from infra.database.session import get_async_session
from learn.runtime.runtime_models import LearnerIdentityModel
from learn.runtime.topic_service import build_topics_payload
from learn.runtime_service import require_learner_session_for

router = APIRouter(prefix="/api/v1/learn", tags=["learn-runtime"])


@router.get("/learners/{learner_id}/topics")
async def api_learner_topics(
    learner_id: str,
    current_user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_async_session),
    x_learner_session: str | None = Header(default=None, alias="X-Learner-Session"),
) -> dict[str, Any]:
    learner = await session.get(LearnerIdentityModel, learner_id)
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    # Same auth as the ``home`` endpoint: learner session, or a teacher login.
    if x_learner_session:
        await require_learner_session_for(
            session, token=x_learner_session, learner_id=learner_id
        )
    elif current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await build_topics_payload(session, learner)
