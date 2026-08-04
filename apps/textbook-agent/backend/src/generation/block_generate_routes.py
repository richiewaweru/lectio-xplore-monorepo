from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal

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

block_generate_router = APIRouter()
logger = logging.getLogger(__name__)
_MAX_GENERATION_CONTEXT_CHARS = 3000
_MAX_CONTEXT_STRING_CHARS = 600
_MAX_CONTEXT_LIST_ITEMS = 8
_MAX_CONTEXT_DICT_ITEMS = 24
_MAX_CONTEXT_KEY_CHARS = 100


_ContextStatus = Literal[
    "plan_absent",
    "context_empty",
    "section_not_matched",
    "brief_found",
    "section_matched_without_brief",
]


@dataclass(frozen=True)
class _GenerationContextResolution:
    context: str | None
    status: _ContextStatus


def _truncate_context_string(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 0:
        return ""
    if limit == 1:
        return "…"
    return f"{value[: limit - 1].rstrip()}…"


def _bounded_context_value(value: object, string_limit: int) -> object:
    if isinstance(value, str):
        return _truncate_context_string(value, string_limit)
    if isinstance(value, list):
        return [
            _bounded_context_value(item, string_limit)
            for item in value[:_MAX_CONTEXT_LIST_ITEMS]
        ]
    if isinstance(value, dict):
        bounded: dict[str, object] = {}
        for raw_key, item in list(value.items())[:_MAX_CONTEXT_DICT_ITEMS]:
            key = _truncate_context_string(str(raw_key), _MAX_CONTEXT_KEY_CHARS)
            bounded[key] = _bounded_context_value(item, string_limit)
        return bounded
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _truncate_context_string(str(value), string_limit)


def _serialize_bounded_context(payload: dict[str, object]) -> str:
    def serialize(string_limit: int) -> str:
        bounded = _bounded_context_value(payload, string_limit)
        if string_limit < _MAX_CONTEXT_STRING_CHARS and isinstance(bounded, dict):
            bounded["truncated"] = True
        return json.dumps(bounded, ensure_ascii=False, separators=(",", ":"))

    full = serialize(_MAX_CONTEXT_STRING_CHARS)
    if len(full) <= _MAX_GENERATION_CONTEXT_CHARS:
        return full

    low = 0
    high = _MAX_CONTEXT_STRING_CHARS - 1
    best: str | None = None
    while low <= high:
        midpoint = (low + high) // 2
        candidate = serialize(midpoint)
        if len(candidate) <= _MAX_GENERATION_CONTEXT_CHARS:
            best = candidate
            low = midpoint + 1
        else:
            high = midpoint - 1
    if best is not None:
        return best

    fallback = {
        "lesson_intent": None,
        "section": None,
        "section_brief": None,
        "truncated": True,
    }
    return json.dumps(fallback, ensure_ascii=False, separators=(",", ":"))


def _compact_generation_context(
    state: dict, section_id: str | None
) -> _GenerationContextResolution:
    plan = state.get("structural_plan")
    if not isinstance(plan, dict):
        return _GenerationContextResolution(None, "plan_absent")
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
        "lesson_intent": intent if isinstance(intent, dict) and intent else None,
        "section": {
            key: section.get(key)
            for key in ("id", "title", "role")
            if isinstance(section, dict) and section.get(key) is not None
        } or None,
        "section_brief": brief if isinstance(brief, dict) and brief else None,
    }
    if not any(payload.values()):
        return _GenerationContextResolution(None, "context_empty")
    if section_id and section is None:
        status: _ContextStatus = "section_not_matched"
    elif payload["section_brief"] is not None:
        status = "brief_found"
    else:
        status = "section_matched_without_brief"
    return _GenerationContextResolution(_serialize_bounded_context(payload), status)


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
                resolution = _compact_generation_context(state, body.section_id)
                logger.debug(
                    "builder assist plan context resolved generation_id=%s status=%s chars=%d",
                    lesson.source_generation_id,
                    resolution.status,
                    len(resolution.context or ""),
                )
                if resolution.context:
                    body = body.model_copy(
                        update={"generation_context": resolution.context}
                    )
            except Exception:  # noqa: BLE001
                logger.debug(
                    "builder assist plan context unavailable generation_id=%s",
                    lesson.source_generation_id,
                    exc_info=True,
                )
    content = await run_block_generation(body, user_id=current_user.id)
    return BlockGenerateResponse(content=content)
