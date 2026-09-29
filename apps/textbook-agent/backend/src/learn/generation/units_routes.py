"""Units-owned realization admission endpoints.

P13C: the review/approve/retry/open-builder endpoints that used to live here
(and their exclusive helpers) targeted the retired Component Lectio dispatch
seam and had zero callers -- superseded by curriculum/routes.py's
prepare/status flow plus the realizations:generate-* admission below. Deleted;
see tests/architecture/test_p13c_retired_routes_guard.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.capabilities import require_xplore_v2
from core.database.models import PathLessonModel, PathVersionModel, UnitModel
from core.entities.user import User
from curriculum.models import PathLessonMutationRequest
from infra.auth.middleware import get_current_user
from infra.dependencies import get_async_session

router = APIRouter(
    prefix="/api/v1/units",
    tags=["units-generation"],
    dependencies=[Depends(require_xplore_v2)],
)


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/realizations:generate-learn",
)
async def generate_learn_realization(
    unit_id: str,
    lesson_id: str,
    body: PathLessonMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
) -> dict[str, Any]:
    """Admit a durable LearnDocument v2 run from an approved Teaching Plan.

    Requires shared preparation with an approved teaching revision. Does not
    convert Print artifacts and does not queue the Print worker.
    """
    from application.unit_lesson.realize_learn_handoff import realize_learn_from_preparation

    unit = await session.scalar(
        select(UnitModel).where(UnitModel.id == unit_id, UnitModel.owner_id == current_user.id)
    )
    lesson = await session.scalar(select(PathLessonModel).where(PathLessonModel.id == lesson_id))
    if unit is None or lesson is None:
        raise HTTPException(status_code=404, detail="Unit lesson not found")
    version = await session.get(PathVersionModel, lesson.path_version_id)
    if version is None or version.unit_id != unit.id:
        raise HTTPException(status_code=404, detail="Unit lesson not found")

    if (
        version.id != body.path_version_id
        or version.revision != body.path_revision
        or lesson.revision != body.lesson_revision
    ):
        raise HTTPException(
            status_code=409, detail="The unit path changed; reload before continuing"
        )
    prep_id = lesson.pack_id
    if not prep_id:
        raise HTTPException(status_code=409, detail="Prepare the lesson before generating Learn")

    try:
        result = await realize_learn_from_preparation(
            session,
            preparation_generation_id=prep_id,
            user_id=current_user.id,
            path_lesson_id=lesson.id,
            admission_request_key=idempotency_key,
        )
        await session.commit()
        if response is not None and result.get("status") in {"queued", "running"}:
            response.status_code = status.HTTP_202_ACCEPTED
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(exc)[:400]) from exc

    return result


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/realizations:generate-print",
)
async def generate_print_realization(
    unit_id: str,
    lesson_id: str,
    body: PathLessonMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Admit + queue Print from an approved Teaching Plan (no Studio re-approval)."""
    from application.unit_lesson.realize_print_handoff import realize_print_from_preparation

    unit = await session.scalar(
        select(UnitModel).where(UnitModel.id == unit_id, UnitModel.owner_id == current_user.id)
    )
    lesson = await session.scalar(select(PathLessonModel).where(PathLessonModel.id == lesson_id))
    if unit is None or lesson is None:
        raise HTTPException(status_code=404, detail="Unit lesson not found")
    version = await session.get(PathVersionModel, lesson.path_version_id)
    if version is None or version.unit_id != unit.id:
        raise HTTPException(status_code=404, detail="Unit lesson not found")

    if (
        version.id != body.path_version_id
        or version.revision != body.path_revision
        or lesson.revision != body.lesson_revision
    ):
        raise HTTPException(
            status_code=409, detail="The unit path changed; reload before continuing"
        )
    prep_id = lesson.pack_id
    if not prep_id:
        raise HTTPException(status_code=409, detail="Prepare the lesson before generating Print")

    try:
        result = await realize_print_from_preparation(
            session,
            preparation_generation_id=prep_id,
            user_id=current_user.id,
            path_lesson_id=lesson.id,
            admission_request_key=idempotency_key,
        )
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(exc)[:400]) from exc

    return result


__all__ = ["router"]
