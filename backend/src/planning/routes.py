from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.middleware import get_current_user
from core.database.models import (
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    UnitModel,
)
from core.dependencies import get_async_session
from core.entities.user import User
from planning.agents import run_adjacent_merge_critics, run_path_planner
from planning.bridge import PathPreparationBlocked, prepare_path_lesson
from planning.models import (
    MergePathLessonsRequest,
    PathLessonPatch,
    PathPlannerRequest,
    PrepareLessonRequest,
    PreparedLessonStatusResponse,
    RegenerateLessonRequest,
    ReorderPathLessonsRequest,
    SplitPathLessonRequest,
    UnitCreate,
    UnitUpdate,
)
from planning.service import (
    ConceptResolutionError,
    PathNotFoundError,
    approve_path,
    create_unit,
    get_owned_unit,
    get_path_lesson,
    get_path_version,
    invalidate_path_approval,
    merge_lessons,
    patch_lesson,
    persist_path_plan,
    reorder_lessons,
    skip_lesson,
    split_lesson,
    update_unit,
)
from planning.validation import PathApprovalBlocked, PathValidationError
from v3_blueprint.planning.persistence import load_chunked_state


router = APIRouter(prefix="/api/v1/units", tags=["units", "paths"])


def _unit_payload(unit: UnitModel) -> dict[str, object]:
    return {
        "id": unit.id,
        "title": unit.title,
        "topic": unit.topic,
        "subject": unit.subject,
        "grade_level": unit.grade_level,
        "curriculum_context": unit.curriculum_context,
        "destination_objective": unit.destination_objective,
        "starting_knowledge": unit.starting_knowledge,
        "status": unit.status,
        "active_path_version_id": unit.active_path_version_id,
    }


async def _path_payload(session: AsyncSession, version) -> dict[str, object]:
    lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    links = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel).where(
                PathLessonPrerequisiteModel.path_lesson_id.in_([lesson.id for lesson in lessons])
            )
        )
    ) if lessons else []
    prerequisites: dict[str, list[str]] = {lesson.id: [] for lesson in lessons}
    for link in links:
        prerequisites[link.path_lesson_id].append(link.prerequisite_lesson_id)
    return {
        "id": version.id,
        "unit_id": version.unit_id,
        "version": version.version,
        "status": version.status,
        "generated_by": version.generated_by,
        "merge_critic_results": version.merge_critic_results,
        "prerequisite_risks": version.prerequisite_risks,
        "forward_verified": version.forward_verified,
        "reaches_destination": version.reaches_destination,
        "approved_at": version.approved_at,
        "lessons": [
            {
                "id": lesson.id,
                "concept_id": lesson.concept_id,
                "concept_slug": lesson.concept_slug,
                "title": lesson.title,
                "objective": lesson.objective,
                "objective_hash": lesson.objective_hash,
                "prerequisites": prerequisites[lesson.id],
                "external_prerequisites": lesson.external_prerequisites,
                "must_establish": lesson.must_establish,
                "exclusions": lesson.exclusions,
                "primary_knowledge_type": lesson.primary_knowledge_type,
                "secondary_demand": lesson.secondary_demand,
                "knowledge_type_source": lesson.knowledge_type_source,
                "merge_warning": lesson.merge_warning,
                "position": lesson.position,
                "source": lesson.source,
                "teacher_edited": lesson.teacher_edited,
                "skipped": lesson.skipped,
                "revision": lesson.revision,
                "pack_id": lesson.pack_id,
            }
            for lesson in lessons
        ],
    }


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, PathNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (PathApprovalBlocked, PathPreparationBlocked)):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, (PathValidationError, ConceptResolutionError, ValueError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.post("", status_code=status.HTTP_201_CREATED)
async def post_unit(
    request: UnitCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    unit = await create_unit(session, owner_id=current_user.id, request=request)
    await session.commit()
    return _unit_payload(unit)


@router.get("")
async def list_units(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, object]]:
    units = await session.scalars(
        select(UnitModel).where(UnitModel.owner_id == current_user.id).order_by(UnitModel.created_at)
    )
    return [_unit_payload(unit) for unit in units]


@router.get("/{unit_id}")
async def get_unit(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
    except Exception as exc:
        _raise_http(exc)
    return _unit_payload(unit)


@router.patch("/{unit_id}")
async def patch_unit(
    unit_id: str,
    request: UnitUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        await update_unit(session, unit, request)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)
    return _unit_payload(unit)


def _planner_request_for_unit(unit: UnitModel, request: PathPlannerRequest) -> PathPlannerRequest:
    if (
        request.topic != unit.topic
        or request.subject != unit.subject
        or request.grade_level != unit.grade_level
        or request.destination_objective != unit.destination_objective
        or request.starting_knowledge != unit.starting_knowledge
    ):
        raise ValueError("Planner-owned unit fields must exactly match the persisted unit")
    return request


async def _plan_or_replan(
    *,
    unit_id: str,
    request: PathPlannerRequest,
    current_user: User,
    session: AsyncSession,
    replan: bool,
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        planner_request = _planner_request_for_unit(unit, request)
        prior = await get_path_version(session, unit_id=unit.id) if replan else None
        plan = await run_path_planner(planner_request, trace_id=f"unit:{unit.id}")
        merge_results = await run_adjacent_merge_critics(
            plan,
            trace_id=f"unit:{unit.id}",
        )
        version = await persist_path_plan(
            session,
            unit=unit,
            plan=plan,
            generated_by="path_replanner" if replan else "path_planner",
            prior_version=prior,
            merge_critic_results=merge_results,
        )
        await session.commit()
        return await _path_payload(session, version)
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path:plan", status_code=status.HTTP_201_CREATED)
async def post_path_plan(
    unit_id: str,
    request: PathPlannerRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    return await _plan_or_replan(
        unit_id=unit_id,
        request=request,
        current_user=current_user,
        session=session,
        replan=False,
    )


@router.post("/{unit_id}/path:replan", status_code=status.HTTP_201_CREATED)
async def post_path_replan(
    unit_id: str,
    request: PathPlannerRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    return await _plan_or_replan(
        unit_id=unit_id,
        request=request,
        current_user=current_user,
        session=session,
        replan=True,
    )


async def _owned_version_and_lesson(
    session: AsyncSession,
    *,
    unit_id: str,
    lesson_id: str,
    owner_id: str,
):
    unit = await get_owned_unit(session, unit_id=unit_id, owner_id=owner_id)
    version = await get_path_version(session, unit_id=unit.id)
    lesson = await get_path_lesson(session, version_id=version.id, lesson_id=lesson_id)
    return unit, version, lesson


@router.post("/{unit_id}/path:approve")
async def post_path_approve(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await get_path_version(session, unit_id=unit.id)
        await approve_path(session, version)
        await session.commit()
        return await _path_payload(session, version)
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.patch("/{unit_id}/path/lessons/{lesson_id}")
async def patch_path_lesson(
    unit_id: str,
    lesson_id: str,
    request: PathLessonPatch,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        _unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        await patch_lesson(session, lesson=lesson, request=request)
        await invalidate_path_approval(session, version)
        await session.commit()
        return {"id": lesson.id, "objective": lesson.objective, "revision": lesson.revision}
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}:skip")
async def post_path_lesson_skip(
    unit_id: str,
    lesson_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        _unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        await skip_lesson(session, lesson)
        await invalidate_path_approval(session, version)
        await session.commit()
        return {"id": lesson.id, "skipped": lesson.skipped, "revision": lesson.revision}
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}:split")
async def post_path_lesson_split(
    unit_id: str,
    lesson_id: str,
    request: SplitPathLessonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        parts = await split_lesson(
            session, unit=unit, version=version, lesson=lesson, request=request
        )
        await invalidate_path_approval(session, version)
        await session.commit()
        return {"source_lesson_id": lesson.id, "part_ids": [part.id for part in parts]}
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons:merge")
async def post_path_lessons_merge(
    unit_id: str,
    request: MergePathLessonsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await get_path_version(session, unit_id=unit.id)
        merged = await merge_lessons(
            session, unit=unit, version=version, request=request
        )
        await invalidate_path_approval(session, version)
        await session.commit()
        return {"merged_lesson_id": merged.id, "source": merged.source}
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons:reorder")
async def post_path_lessons_reorder(
    unit_id: str,
    request: ReorderPathLessonsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await get_path_version(session, unit_id=unit.id)
        lessons = await reorder_lessons(session, version_id=version.id, request=request)
        await invalidate_path_approval(session, version)
        await session.commit()
        return {"lesson_ids": [lesson.id for lesson in lessons]}
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}:prepare")
async def post_path_lesson_prepare(
    unit_id: str,
    lesson_id: str,
    request: PrepareLessonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        response, _plan = await prepare_path_lesson(
            session, unit=unit, version=version, lesson=lesson, request=request
        )
        await session.commit()
        return response.model_dump(mode="json")
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}:regenerate")
async def post_path_lesson_regenerate(
    unit_id: str,
    lesson_id: str,
    request: RegenerateLessonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        response, _plan = await prepare_path_lesson(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(
                group_ids=request.group_ids,
                lesson_mode=request.lesson_mode,
            ),
            regenerate=True,
            regeneration_reason=request.reason,
        )
        await session.commit()
        return {**response.model_dump(mode="json"), "regeneration_reason": request.reason}
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.get("/{unit_id}/path/lessons/{lesson_id}/status")
async def get_path_lesson_status(
    unit_id: str,
    lesson_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        _unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        if not lesson.pack_id:
            return PreparedLessonStatusResponse(
                path_lesson_id=lesson.id,
                lesson_revision=lesson.revision,
                generation_id=None,
                generation_status="unprepared",
                workflow_stage="unprepared",
                objective_hash=lesson.objective_hash,
                stale=False,
                can_prepare=version.status == "approved" and not lesson.skipped,
                can_regenerate=False,
            ).model_dump(mode="json")
        generation = await session.get(GenerationModel, lesson.pack_id)
        provenance = await session.get(LessonProvenanceModel, lesson.pack_id)
        if generation is None or provenance is None:
            raise PathPreparationBlocked("Prepared lesson linkage is incomplete")
        stale = (
            provenance.objective_hash != lesson.objective_hash
            or provenance.path_lesson_revision not in {None, lesson.revision}
            or provenance.invalidated_at is not None
        )
        try:
            chunked = await load_chunked_state(generation.id, session)
            workflow_stage = str(chunked.get("stage") or generation.status or "unknown")
        except ValueError:
            workflow_stage = str(generation.status or "unknown")
        return PreparedLessonStatusResponse(
            path_lesson_id=lesson.id,
            lesson_revision=lesson.revision,
            generation_id=generation.id,
            generation_status=str(generation.status or "unknown"),
            workflow_stage="stale" if stale else workflow_stage,
            objective_hash=lesson.objective_hash,
            stale=stale,
            can_prepare=False,
            can_regenerate=version.status == "approved" and not lesson.skipped,
        ).model_dump(mode="json")
    except Exception as exc:
        _raise_http(exc)
