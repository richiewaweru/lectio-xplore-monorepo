"""Units-owned review and execution endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
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
from application.unit_lesson.realizations import get_realization, resolve_by_path, to_identity
from learn.generation.units_dispatch import dispatch_units_generation, units_dispatch_task
from learn.authoring.builder.service import (
    ComponentLectioBuilderError,
    get_or_create_native_learn_builder_lesson,
)
from learn.generation.pipeline_dispatch import COMPONENT_LECTIO_RETIRED
from curriculum.models import PathLessonMutationRequest, PathVersionMutationRequest
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
    realization_id: str | None = None
    path: Literal["print", "learn"] | None = None
    open_href: str | None = None


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
    path: Literal["print", "learn"] | None = None,
    realization_id: str | None = None,
) -> tuple[UnitModel, PathVersionModel, PathLessonModel, GenerationModel, dict[str, Any], Any]:
    unit = await session.scalar(
        select(UnitModel).where(UnitModel.id == unit_id, UnitModel.owner_id == user_id)
    )
    lesson = await session.scalar(select(PathLessonModel).where(PathLessonModel.id == lesson_id))
    if unit is None or lesson is None:
        raise HTTPException(status_code=404, detail="Unit generation not found")
    version = await session.get(PathVersionModel, lesson.path_version_id)
    if version is None or version.unit_id != unit.id:
        raise HTTPException(status_code=404, detail="Unit generation not found")

    realization = None
    generation_id: str | None = None
    if realization_id:
        realization = await get_realization(session, realization_id)
        if realization is None or realization.path_lesson_id != lesson.id:
            raise HTTPException(status_code=404, detail="Realization not found")
        if realization.status == "read_only":
            raise HTTPException(
                status_code=409,
                detail=realization.error_summary
                or "Realization is read-only; regenerate with an explicit path",
            )
        generation_id = realization.output_id
    elif path:
        realization = await resolve_by_path(session, path_lesson_id=lesson.id, path=path)
        if realization is None:
            raise HTTPException(status_code=404, detail=f"No {path} realization for lesson")
        if realization.status == "read_only":
            raise HTTPException(
                status_code=409,
                detail=realization.error_summary
                or "Realization is read-only; regenerate with an explicit path",
            )
        generation_id = realization.output_id

    if generation_id:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            # Realization may be queued before its native artifact exists; fall
            # back to the shared preparation generation for status reads.
            fallback_id = (
                (realization.preparation_generation_id if realization is not None else None)
                or lesson.pack_id
            )
            if fallback_id and fallback_id != generation_id:
                generation = await session.get(GenerationModel, fallback_id)
        if generation is None or generation.user_id != user_id:
            raise HTTPException(status_code=404, detail="Unit generation not found")
        try:
            state = await load_chunked_state(generation.id, session)
        except ValueError:
            state = {}
        return unit, version, lesson, generation, state, realization

    if realization is not None:
        # Queued realization without output yet — use shared preparation.
        fallback_id = realization.preparation_generation_id or lesson.pack_id
        if not fallback_id:
            raise HTTPException(status_code=404, detail="Unit generation not found")
        generation = await session.get(GenerationModel, fallback_id)
        if generation is None or generation.user_id != user_id:
            raise HTTPException(status_code=404, detail="Unit generation not found")
        try:
            state = await load_chunked_state(generation.id, session)
        except ValueError:
            state = {}
        return unit, version, lesson, generation, state, realization

    # Legacy fallback: single pack_id preparation link.
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
    return unit, version, lesson, generation, await load_chunked_state(generation.id, session), None


async def _builder_id(
    session: AsyncSession | None, generation: GenerationModel, user_id: str
) -> str | None:
    if session is None:
        return None
    return await session.scalar(
        select(EditableLessonModel.id).where(
            EditableLessonModel.user_id == user_id,
            EditableLessonModel.source_generation_id == generation.id,
            EditableLessonModel.source_type.in_(
                ("learn_document", "native_learn", "document", "manual", "template")
            ),
        )
    )


async def _status(
    session: AsyncSession | None,
    generation: GenerationModel,
    state: dict[str, Any],
    user_id: str,
    *,
    realization: Any = None,
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
    identity = to_identity(realization) if realization is not None else None
    reported_id = (
        identity.output_id
        if identity is not None and identity.output_id
        else generation.id
    )
    return UnitsGenerationStatus(
        generation_id=reported_id,
        pipeline=str((state.get("control") or {}).get("pipeline") or "retired"),
        stage=stage,
        document_present=isinstance(generation.document_json, dict),
        failed_blocks=[str(item) for item in failed if isinstance(item, str)],
        retryable=stage in {"failed", "assembly_blocked", "stage2_error", "native_learn_error"},
        builder_id=await _builder_id(session, generation, user_id),
        display_title=str(state.get("display_title")) if state.get("display_title") else None,
        review_cards=review_cards,
        realization_id=identity.realization_id if identity else None,
        path=identity.path if identity else None,
        open_href=identity.open_href if identity else None,
    )


@router.get("/{unit_id}/path/lessons/{lesson_id}/generation", response_model=UnitsGenerationStatus)
async def get_units_generation_status(
    unit_id: str,
    lesson_id: str,
    path: Literal["print", "learn"] | None = Query(default=None),
    realization_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    _unit, _version, _lesson, generation, state, realization = await _generation_context(
        session,
        unit_id=unit_id,
        lesson_id=lesson_id,
        user_id=current_user.id,
        path=path,
        realization_id=realization_id,
    )
    return await _status(session, generation, state, current_user.id, realization=realization)


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/generation:review", response_model=UnitsGenerationStatus
)
async def review_units_generation(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    path: Literal["print", "learn"] | None = Query(default=None),
    realization_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    _unit, version, lesson, generation, state, realization = await _generation_context(
        session,
        unit_id=unit_id,
        lesson_id=lesson_id,
        user_id=current_user.id,
        path=path,
        realization_id=realization_id,
    )
    if version.id != body.path_version_id or version.revision != body.path_revision:
        raise HTTPException(
            status_code=409, detail="The unit path changed; reload before continuing"
        )
    if realization is None and (not lesson.pack_id or lesson.pack_id != generation.id):
        raise HTTPException(status_code=409, detail="Lesson generation linkage is stale")
    return await _status(session, generation, state, current_user.id, realization=realization)


async def _dispatch(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    current_user: User,
    session: AsyncSession,
    *,
    retry: bool = False,
    path: Literal["print", "learn"] | None = None,
    realization_id: str | None = None,
) -> UnitsGenerationStatus:
    _unit, version, lesson, generation, state, realization = await _generation_context(
        session,
        unit_id=unit_id,
        lesson_id=lesson_id,
        user_id=current_user.id,
        path=path,
        realization_id=realization_id,
    )
    if version.id != body.path_version_id or version.revision != body.path_revision:
        raise HTTPException(
            status_code=409, detail="The unit path changed; reload before continuing"
        )
    if realization is None and lesson.pack_id != generation.id:
        raise HTTPException(status_code=409, detail="Lesson generation linkage is stale")
    stage = str(state.get("stage") or generation.status or "unknown")
    if not retry:
        if stage == "complete":
            return await _status(
                session, generation, state, current_user.id, realization=realization
            )
        if (
            stage == "native_learn_running"
            and (task := units_dispatch_task(generation.id)) is not None
            and not task.done()
        ):
            return await _status(
                session, generation, state, current_user.id, realization=realization
            )
        if stage not in {"awaiting_review", "prepared", "plan_ready"}:
            raise HTTPException(status_code=409, detail="Generation is not awaiting approval")
    if retry and stage not in {
        "assembly_blocked",
        "stage2_error",
        "native_learn_error",
        "failed",
    }:
        raise HTTPException(status_code=409, detail="Generation is not retryable")
    try:
        await dispatch_units_generation(
            generation_id=generation.id, user_id=current_user.id, state=state
        )
    except ValueError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    state = {**state, "stage": "native_learn_running", "execution_started": True}
    generation.status = "running"
    return await _status(session, generation, state, current_user.id, realization=realization)


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/generation:approve", response_model=UnitsGenerationStatus
)
async def approve_units_generation(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    path: Literal["print", "learn"] | None = Query(default=None),
    realization_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    return await _dispatch(
        unit_id,
        lesson_id,
        body,
        current_user,
        session,
        path=path,
        realization_id=realization_id,
    )


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/generation:retry", response_model=UnitsGenerationStatus
)
async def retry_units_generation(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    path: Literal["print", "learn"] | None = Query(default=None),
    realization_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    return await _dispatch(
        unit_id,
        lesson_id,
        body,
        current_user,
        session,
        retry=True,
        path=path,
        realization_id=realization_id,
    )


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/generation:open-builder",
    response_model=UnitsGenerationStatus,
)
async def open_units_builder(
    unit_id: str,
    lesson_id: str,
    body: PathVersionMutationRequest,
    path: Literal["print", "learn"] | None = Query(default="learn"),
    realization_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnitsGenerationStatus:
    _unit, version, lesson, generation, state, realization = await _generation_context(
        session,
        unit_id=unit_id,
        lesson_id=lesson_id,
        user_id=current_user.id,
        path=path,
        realization_id=realization_id,
    )
    if version.id != body.path_version_id or version.revision != body.path_revision:
        raise HTTPException(
            status_code=409, detail="The unit path changed; reload before continuing"
        )
    if realization is None and lesson.pack_id != generation.id:
        raise HTTPException(status_code=409, detail="Lesson generation linkage is stale")
    if realization is not None and realization.path != "learn":
        raise HTTPException(status_code=409, detail="Builder open requires a Learn realization")
    if str((state.get("control") or {}).get("pipeline") or "retired") not in {
        "native_learn",
        "learn_document",
    }:
        raise HTTPException(status_code=410, detail=COMPONENT_LECTIO_RETIRED)
    try:
        await get_or_create_native_learn_builder_lesson(
            session, generation=generation, user_id=current_user.id
        )
        await session.commit()
    except ComponentLectioBuilderError as exc:
        await session.rollback()
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await _status(session, generation, state, current_user.id, realization=realization)


@router.post(
    "/{unit_id}/path/lessons/{lesson_id}/realizations:generate-learn",
)
async def generate_learn_realization(
    unit_id: str,
    lesson_id: str,
    body: PathLessonMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Admit + execute LearnDocument v2 from an approved Teaching Plan.

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
