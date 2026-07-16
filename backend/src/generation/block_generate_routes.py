from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.middleware import get_current_user
from core.database.models import EditableLessonModel
from core.database.session import get_async_session
from core.entities.user import User
from generation.block_generate import (
    BlockGenerateRequest,
    BlockGenerateResponse,
    run_block_generation,
)
from v3_blueprint.planning.persistence import load_chunked_state

import json
import logging

block_generate_router = APIRouter()
logger = logging.getLogger(__name__)
_MAX_GENERATION_CONTEXT_CHARS = 3000


def _compact_generation_context(state: dict, section_id: str | None) -> str | None:
    plan = state.get("structural_plan")
    if not isinstance(plan, dict):
        return None
    intent = plan.get("lesson_intent")
    sections = plan.get("sections")
    section = None
    if section_id and isinstance(sections, list):
        section = next(
            (item for item in sections if isinstance(item, dict) and item.get("id") == section_id),
            None,
        )
    briefs = state.get("section_briefs")
    brief = briefs.get(section_id) if section_id and isinstance(briefs, dict) else None
    payload = {
        "lesson_intent": intent if isinstance(intent, dict) else None,
        "section": {
            key: section.get(key)
            for key in ("id", "title", "role")
            if isinstance(section, dict) and section.get(key) is not None
        } or None,
        "section_brief": brief if isinstance(brief, dict) else None,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:_MAX_GENERATION_CONTEXT_CHARS]


@block_generate_router.post("/blocks/generate", response_model=BlockGenerateResponse)
async def generate_block(
    body: BlockGenerateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BlockGenerateResponse:
    if body.lesson_id:
        lesson_lookup = await session.execute(
            select(EditableLessonModel).where(
                EditableLessonModel.id == body.lesson_id,
                EditableLessonModel.user_id == current_user.id,
            )
        )
        lesson = lesson_lookup.scalar_one_or_none()
        if lesson is None:
            raise HTTPException(status_code=404, detail="Lesson not found")
        if lesson.source_generation_id:
            try:
                state = await load_chunked_state(lesson.source_generation_id, session=session)
                context = _compact_generation_context(state, body.section_id)
                if context:
                    body = body.model_copy(update={"generation_context": context})
                    logger.debug(
                        "builder assist plan context injected generation_id=%s chars=%d",
                        lesson.source_generation_id,
                        len(context),
                    )
            except Exception:  # noqa: BLE001
                logger.debug(
                    "builder assist plan context unavailable generation_id=%s",
                    lesson.source_generation_id,
                    exc_info=True,
                )
    content = await run_block_generation(body, user_id=current_user.id)
    return BlockGenerateResponse(content=content)
