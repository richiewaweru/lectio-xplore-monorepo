"""Units-owned review and execution endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.auth.middleware import get_current_user
from core.capabilities import require_xplore_v2
from core.database.models import (
    EditableLessonModel,
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)
from infra.dependencies import get_async_session
from core.entities.user import User
from learn.generation.units_dispatch import dispatch_units_generation, units_dispatch_task
from learn.authoring.builder.service import (
    ComponentLectioBuilderDocumentError,
    ComponentLectioBuilderNotReadyError,
    get_or_create_component_lectio_builder_lesson,
)
from curriculum.models import PathVersionMutationRequest
from v3_blueprint.planning.persistence import load_chunked_state

router = APIRouter(
    prefix="/api/v1/units",
    tags=["units-generation"],
    dependencies=[Depends(require_xplore_v2)],
)


class UnitsGenerationStatus(BaseModel):
    generation_id: str
    pipeline: str
    stage: str
    document_present: bool
    failed_blocks: list[str]
    retryable: bool
    builder_id: str | None = None
    display_title: str | None = None
    review_cards: list["UnitsReviewCard"] = Field(default_factory=list)


class UnitsReviewCard(BaseModel):
    id: str
    title: str
    objective: str
    prereqs: list[str]
    misconception_descriptions: list[str]


async def _generation_context(
    session: AsyncSession,
    *,
    unit_id: str,
    lesson_id: str,
    user_id: str,
) -> tuple[UnitModel, PathVersionModel, PathLessonModel, GenerationModel, dict[str, Any]]:
    unit = await session.scalar(
        select(UnitModel).where(UnitModel.id == unit_id, UnitModel.owner_id == user_id)
    )
    lesson = await session.scalar(select(PathLessonModel).where(PathLessonModel.id == lesson_id))
    if unit is None or lesson is None:
        raise HTTPException(status_code=404, detail="Unit generation not found")
    version = await session.get(PathVersionModel, lesson.path_version_id)
    if version is None or version.unit_id != unit.id:
        raise HTTPException(status_code=404, detail="Unit generation not found")
    if not lesson.pack_id:
        raise HTTPException(status_code=404, detail="Unit generation not found")
    provenance = await session.get(LessonProvenanceModel, lesson.pack_id)
    if (
        provenance is None
        or provenance.path_version_id != version.id
        or provenance.path_lesson_id != lesson.id
        or provenance.invalidated_at is not None
    ):
        raise HTTPException(status_code=404, detail="Unit generation not found")
    generation = await session.get(GenerationModel, provenance.pack_id)
    if generation is None or generation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Unit generation not found")
    return unit, version, lesson, generation, await load_chunked_state(generation.id, session)


async def _builder_id(
    session: AsyncSession | None, generation: GenerationModel, user_id: str
) -> str | None:
    if session is None:
        return None
    return await session.scalar(
        select(EditableLessonModel.id).where(
            EditableLessonModel.user_id == user_id,
            EditableLessonModel.source_generation_id == generation.id,
            EditableLessonModel.source_type == "component_lectio",
        )
    )


async def _status(
    session: AsyncSession | None, generation: GenerationModel, state: dict[str, Any], user_id: str
) -> UnitsGenerationStatus:
    scalar_status = str(generation.status or "").casefold()
    has_document = isinstance(generation.document_json, dict)
    if scalar_status == "completed" and has_document:
        # The scalar terminal state and document are committed atomically. A
        # stale review snapshot must not reopen the approval card on reload.
        stage = "complete"
    elif scalar_status == "completed" and not has_document:
        stage = "assembly_blocked"
    else:
        stage = str(state.get("stage") or generation.status or "unknown")
    failed = state.get("failed_blocks") or state.get("failed_sections") or []
    raw_plan = state.get("structural_plan")
    raw_cards = raw_plan.get("cards", []) if isinstance(raw_plan, dict) else []
    review_cards: list[UnitsReviewCard] = []
    for raw_card in raw_cards:
        if not isinstance(raw_card, dict):
            continue
        misconceptions = raw_card.get("misconceptions", [])
        descriptions = [
            str(item.get("description", "")).strip()
            for item in misconceptions
            if isinstance(item, dict) and str(item.get("description", "")).strip()
        ]
        review_cards.append(
            UnitsReviewCard(
                id=str(raw_card.get("id", "")),
                title=str(raw_card.get("title", "")),
                objective=str(raw_card.get("objective", "")),
                prereqs=[
                    str(item) for item in raw_card.get("prereqs", []) if isinstance(item, str)
                ],
                misconception_descriptions=descriptions,
            )
        )
    return UnitsGenerationStatus(
        generation_id=generation.id,
        pipeline=str((state.get("control") or {}).get("pipeline") or "retired"),
        stage=stage,
        document_present=isinstance(generation.document_json, dict),
        failed_blocks=[str(item) for item in failed if isinstance(item, str)],
        retryable=stage in {"failed", "assembly_blocked", "stage2_error", "component_lectio_error"},
        builder_id=await _builder_id(session, generation, user_id),
        display_title=str(state.get("display_title")) if state.get("display_title") else None,
        review_cards=review_cards,
    )


@router.get("/{unit_id}/path/lessons/{lesson_id}/generation", response_model=UnitsGenerationStatus)
async def get_units_generation_status(
    unit_id: str,
    lesson_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    _unit, _version, _lesson, generation, state = await _generation_context(
        session, unit_id=unit_id, lesson_id=lesson_id, user_id=current_user.id
    )
    return await _status(session, generation, state, current_user.id)


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/generation:review", response_model=UnitsGenerationStatus
)
async def review_units_generation(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    _unit, version, lesson, generation, state = await _generation_context(
        session, unit_id=unit_id, lesson_id=lesson_id, user_id=current_user.id
    )
    if version.id != body.path_version_id or version.revision != body.path_revision:
        raise HTTPException(
            status_code=409, detail="The unit path changed; reload before continuing"
        )
    if not lesson.pack_id or lesson.pack_id != generation.id:
        raise HTTPException(status_code=409, detail="Lesson generation linkage is stale")
    return await _status(session, generation, state, current_user.id)


async def _dispatch(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    current_user: User,
    session: AsyncSession,
    *,
    retry: bool = False,
) -> UnitsGenerationStatus:
    _unit, version, lesson, generation, state = await _generation_context(
        session, unit_id=unit_id, lesson_id=lesson_id, user_id=current_user.id
    )
    if version.id != body.path_version_id or version.revision != body.path_revision:
        raise HTTPException(
            status_code=409, detail="The unit path changed; reload before continuing"
        )
    if lesson.pack_id != generation.id:
        raise HTTPException(status_code=409, detail="Lesson generation linkage is stale")
    stage = str(state.get("stage") or generation.status or "unknown")
    if not retry:
        if stage == "complete":
            return await _status(session, generation, state, current_user.id)
        if (
            stage == "component_lectio_running"
            and (task := units_dispatch_task(generation.id)) is not None
            and not task.done()
        ):
            return await _status(session, generation, state, current_user.id)
        if stage not in {"awaiting_review", "prepared", "plan_ready"}:
            raise HTTPException(status_code=409, detail="Generation is not awaiting approval")
    if retry and stage not in {
        "assembly_blocked",
        "stage2_error",
        "component_lectio_error",
        "failed",
    }:
        raise HTTPException(status_code=409, detail="Generation is not retryable")
    try:
        await dispatch_units_generation(
            generation_id=generation.id, user_id=current_user.id, state=state
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    state = {**state, "stage": "component_lectio_running", "execution_started": True}
    generation.status = "running"
    return await _status(session, generation, state, current_user.id)


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/generation:approve", response_model=UnitsGenerationStatus
)
async def approve_units_generation(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    return await _dispatch(unit_id, lesson_id, body, current_user, session)


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/generation:retry", response_model=UnitsGenerationStatus
)
async def retry_units_generation(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    return await _dispatch(unit_id, lesson_id, body, current_user, session, retry=True)


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/generation:open-builder",
    response_model=UnitsGenerationStatus,
)
async def open_units_builder(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    _unit, version, lesson, generation, state = await _generation_context(
        session, unit_id=unit_id, lesson_id=lesson_id, user_id=current_user.id
    )
    if version.id != body.path_version_id or version.revision != body.path_revision:
        raise HTTPException(
            status_code=409, detail="The unit path changed; reload before continuing"
        )
    if lesson.pack_id != generation.id:
        raise HTTPException(status_code=409, detail="Lesson generation linkage is stale")
    if str((state.get("control") or {}).get("pipeline") or "retired") != "component_lectio":
        raise HTTPException(status_code=409, detail="Generation is not marked as Component Lectio")
    try:
        await get_or_create_component_lectio_builder_lesson(
            session, generation=generation, user_id=current_user.id
        )
        await session.commit()
    except ComponentLectioBuilderNotReadyError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ComponentLectioBuilderDocumentError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await _status(session, generation, state, current_user.id)


__all__ = ["router"]
