"""Shared Learn realization from an approved Teaching Plan on a preparation generation."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel, LessonProvenanceModel, PathLessonModel
from curriculum.teaching_plan.consumers import (
    TeachingRevisionNotApprovedError,
    TeachingRevisionUnavailableError,
    accept_approved_teaching_revision,
)
from learn.generation.native_execution import produce_learn_from_approved_teaching
from learn.generation.native_production import teaching_plan_content_hash
from v3_blueprint.planning.persistence import load_chunked_state


async def realize_learn_from_preparation(
    session: AsyncSession,
    *,
    preparation_generation_id: str,
    user_id: str,
    path_lesson_id: str | None = None,
) -> dict[str, Any]:
    """Produce LearnDocument v2 from approved teaching on a preparation generation."""
    generation = await session.get(GenerationModel, preparation_generation_id)
    if generation is None or generation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Preparation generation not found")

    lesson_id = path_lesson_id
    if not lesson_id:
        provenance = await session.get(LessonProvenanceModel, preparation_generation_id)
        if provenance is not None and provenance.path_lesson_id:
            lesson_id = provenance.path_lesson_id
        else:
            # Fallback: find path lesson whose pack_id is this preparation.
            lesson = await session.scalar(
                select(PathLessonModel).where(
                    PathLessonModel.pack_id == preparation_generation_id
                )
            )
            if lesson is not None:
                lesson_id = lesson.id
    if not lesson_id:
        raise HTTPException(
            status_code=409,
            detail="Cannot resolve path lesson for this preparation",
        )

    try:
        state = await load_chunked_state(preparation_generation_id, session)
    except ValueError:
        state = dict(generation.chunked_state_json or {})

    try:
        teaching_plan = accept_approved_teaching_revision(state, consumer="learn")
    except TeachingRevisionNotApprovedError as exc:
        raise HTTPException(
            status_code=409,
            detail="Approve the Teaching Plan before generating Learn",
        ) from exc
    except TeachingRevisionUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    plan_hash = teaching_plan_content_hash(teaching_plan)
    result = await produce_learn_from_approved_teaching(
        session,
        teaching_plan=teaching_plan,
        user_id=user_id,
        path_lesson_id=lesson_id,
        preparation_generation_id=preparation_generation_id,
        pack_id=None,
        title=str(teaching_plan.arc or "Learn lesson"),
        subject=str(generation.subject or "science"),
    )
    editable_id = str(result.get("editable_lesson_id") or "")
    output_id = str(result.get("output_id") or "")
    return {
        "status": "ready",
        "path": "learn",
        "output_id": output_id,
        "editable_lesson_id": editable_id,
        "realization_id": result.get("realization_id"),
        "teaching_plan_hash": plan_hash,
        "teaching_plan_revision": result.get("teaching_plan_revision"),
        "open_href": f"/builder/{editable_id}" if editable_id else None,
    }


__all__ = ["realize_learn_from_preparation"]
