"""Owner-scoped HTTP for Preparation Runs (Option D, 3A).

``POST /api/v1/preparations/{generation_id}/plan`` admits the plan-generation
Run when the teacher approves the lesson structure; ``.../plan:regenerate``
admits the next bounded attempt for a failed or rejected plan.  Failed cards
are retried through the generic runtime routes
(``/api/v1/generation/work-items/{id}/retry``, ``/generation/runs/{id}/retry``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.preparation_runs import (
    PreparationAdmission,
    PreparationRunError,
    admit_preparation_run,
)
from core.database.models import GenerationModel
from core.entities.user import User
from curriculum.backbone.persistence import load_backbone_record
from curriculum.planning.persistence import load_chunked_state
from infra.auth.middleware import get_current_user
from infra.database.session import get_async_session

router = APIRouter(prefix="/api/v1/preparations", tags=["preparations"])


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_title: str | None = Field(default=None, max_length=120)


def _payload(generation_id: str, admission: PreparationAdmission) -> dict[str, Any]:
    run = admission.run
    return {
        "generation_id": generation_id,
        "run_id": run.id,
        "status": run.status,
        "attempt": admission.attempt,
        "created": admission.created,
        "recovery_action": run.recovery_action,
    }


def _http_error(exc: PreparationRunError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}
    )


async def _admit(
    session: AsyncSession,
    *,
    generation_id: str,
    user: User,
    regenerate: bool,
    display_title: str | None = None,
) -> dict[str, Any]:
    try:
        admission = await admit_preparation_run(
            session,
            generation_id=generation_id,
            owner_user_id=user.id,
            regenerate=regenerate,
            display_title=display_title,
        )
        await session.commit()
    except PreparationRunError as exc:
        await session.rollback()
        raise _http_error(exc) from exc
    return _payload(generation_id, admission)


@router.post("/{generation_id}/plan", status_code=202)
async def post_preparation_plan(
    generation_id: str,
    body: PlanRequest | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Admit (or return) the preparation Run for an approved lesson structure."""
    return await _admit(
        session,
        generation_id=generation_id,
        user=current_user,
        regenerate=False,
        display_title=body.display_title if body is not None else None,
    )


@router.post("/{generation_id}/plan:regenerate", status_code=202)
async def post_preparation_plan_regenerate(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Admit the next bounded attempt (max 3) for a failed-terminal or rejected plan."""
    return await _admit(
        session, generation_id=generation_id, user=current_user, regenerate=True
    )


@router.get("/{generation_id}/structure")
async def get_preparation_structure(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Structural plan preview shown while the teacher reviews the lesson structure."""
    generation = await session.get(GenerationModel, generation_id)
    if generation is None or generation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    try:
        state = await load_chunked_state(generation_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Chunked state not found") from exc
    plan = state.get("structural_plan")
    if not isinstance(plan, dict):
        raise HTTPException(status_code=404, detail="Structural plan not found")
    return {"generation_id": generation_id, "structural_plan": plan}


@router.get("/{generation_id}/backbone")
async def get_preparation_backbone(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """The lesson backbone (read-only for teachers); 404 until it is ready."""
    generation = await session.get(GenerationModel, generation_id)
    if generation is None or generation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    record = await load_backbone_record(session, generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Backbone not ready")
    backbone, digest, _input_hash = record
    return {"backbone": backbone.model_dump(mode="json"), "hash": digest}


__all__ = ["router"]
