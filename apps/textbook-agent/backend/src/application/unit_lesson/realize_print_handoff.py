"""Shared Print realization from an approved Teaching Plan on a preparation generation."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import admit_realization
from core.database.models import GenerationModel, LessonProvenanceModel, PathLessonModel
from curriculum.teaching_plan.consumers import (
    TeachingRevisionNotApprovedError,
    TeachingRevisionUnavailableError,
    accept_approved_teaching_revision,
)
from print.generation.native_production import teaching_plan_content_hash
from print.generation.whole_lesson.repository import PageDocumentRepository
from v3_blueprint.planning.persistence import load_chunked_state


async def realize_print_from_preparation(
    session: AsyncSession,
    *,
    preparation_generation_id: str,
    user_id: str,
    path_lesson_id: str | None = None,
) -> dict[str, Any]:
    """Queue native Print from approved teaching. Does not re-approve the plan."""
    generation = await session.get(GenerationModel, preparation_generation_id)
    if generation is None or generation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Preparation generation not found")

    lesson_id = path_lesson_id
    if not lesson_id:
        provenance = await session.get(LessonProvenanceModel, preparation_generation_id)
        if provenance is not None and provenance.path_lesson_id:
            lesson_id = provenance.path_lesson_id
        else:
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
        teaching_plan = accept_approved_teaching_revision(state, consumer="print")
    except TeachingRevisionNotApprovedError as exc:
        raise HTTPException(
            status_code=409,
            detail="Approve the Teaching Plan before generating Print",
        ) from exc
    except TeachingRevisionUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    plan_hash = teaching_plan_content_hash(teaching_plan)
    review = dict(state.get("teaching_review") or {})
    expected_revision = int(
        review.get("approved_revision") or teaching_plan.revision or 1
    )
    repo = PageDocumentRepository(session, preparation_generation_id)
    try:
        await repo.save_teaching_review(
            status="approved",
            expected_revision=expected_revision,
            queue=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    row, _created = await admit_realization(
        session,
        path_lesson_id=lesson_id,
        path="print",
        teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        teaching_plan_revision=int(teaching_plan.revision or 1),
        teaching_plan_hash=plan_hash,
        preparation_generation_id=preparation_generation_id,
        pack_id=preparation_generation_id,
        output_id=preparation_generation_id,
    )
    status = str(generation.status or row.status or "queued")
    return {
        "status": status,
        "path": "print",
        "output_id": preparation_generation_id,
        "realization_id": row.id,
        "teaching_plan_hash": plan_hash,
        "teaching_plan_revision": int(teaching_plan.revision or 1),
        "open_href": f"/studio/print/{preparation_generation_id}",
    }


__all__ = ["realize_print_from_preparation"]
