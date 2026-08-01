from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    GuardedMergePathLessonsRequest,
    GuardedPrepareLessonRequest,
    GuardedPathLessonPatch,
    GuardedReorderPathLessonsRequest,
    GuardedSplitPathLessonRequest,
    PathLessonMutationRequest,
    PathPlannerRequest,
    PathReplanRequest,
    PathVersionMutationRequest,
    PrepareLessonRequest,
    PreparedLessonStatusResponse,
    RegenerateLessonRequest,
    RestorePathVersionRequest,
    ScheduleSuggestRequest,
    ScheduleWriteRequest,
    ShapeDeviationCreateRequest,
    ShapeDeviationDecisionRequest,
    UnitCreate,
    UnitGroupsWriteRequest,
    UnitUpdate,
)
from planning.schedule import (
    groups_payload,
    schedule_payload,
    suggest_schedule,
    write_groups,
    write_schedule,
)
from planning.shapes import (
    decide_shape_deviation,
    deviation_payload,
    lesson_shape_payload,
    request_shape_deviation,
)
from planning.service import (
    ConceptResolutionError,
    PathNotFoundError,
    StalePathMutationError,
    approve_path,
    assert_lesson_mutation_fresh,
    assert_path_mutation_fresh,
    clone_path_version,
    create_unit,
    get_owned_unit,
    get_path_lesson,
    get_path_version,
    invalidate_path_approval,
    list_path_versions,
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
        "groups_revision": unit.groups_revision,
    }


async def _active_version(session: AsyncSession, unit: UnitModel):
    if not unit.active_path_version_id:
        raise PathNotFoundError("Active path version not found")
    return await get_path_version(
        session,
        unit_id=unit.id,
        version_id=unit.active_path_version_id,
    )


async def _path_payload(session: AsyncSession, version) -> dict[str, object]:
    unit = await session.get(UnitModel, version.unit_id)
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
        "revision": version.revision,
        "status": (
            version.status
            if unit is not None and unit.active_path_version_id == version.id
            else "superseded"
        ),
        "generated_by": version.generated_by,
        "merge_critic_results": version.merge_critic_results,
        "prerequisite_risks": version.prerequisite_risks,
        "forward_verified": version.forward_verified,
        "reaches_destination": version.reaches_destination,
        "completeness_note": (version.source_plan_json.get("completeness") or {}).get("note"),
        "approved_at": version.approved_at,
        "created_at": version.created_at,
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
    if isinstance(exc, (PathApprovalBlocked, PathPreparationBlocked, StalePathMutationError)):
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
    return PathPlannerRequest.model_validate(
        request.model_dump(exclude={"path_version_id", "path_revision"})
    )


async def _plan_or_replan(
    *,
    unit_id: str,
    request: PathPlannerRequest | PathReplanRequest,
    current_user: User,
    session: AsyncSession,
    replan: bool,
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        if replan:
            assert isinstance(request, PathReplanRequest)
            active = await _active_version(session, unit)
            assert_path_mutation_fresh(
                active,
                path_version_id=request.path_version_id,
                path_revision=request.path_revision,
            )
        planner_request = _planner_request_for_unit(unit, request)
        prior = await _active_version(session, unit) if replan else None
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
    request: PathReplanRequest,
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
    version = await _active_version(session, unit)
    lesson = await get_path_lesson(session, version_id=version.id, lesson_id=lesson_id)
    return unit, version, lesson


@router.post("/{unit_id}/path:approve")
async def post_path_approve(
    unit_id: str,
    request: PathVersionMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        await approve_path(session, version)
        await session.commit()
        return await _path_payload(session, version)
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.get("/{unit_id}/path")
async def get_active_path(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        return await _path_payload(session, version)
    except Exception as exc:
        _raise_http(exc)


@router.get("/{unit_id}/path/versions")
async def get_path_history(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, object]]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        versions = await list_path_versions(session, unit_id=unit.id)
        return [
            {
                "id": version.id,
                "version": version.version,
                "revision": version.revision,
                "status": (
                    version.status if unit.active_path_version_id == version.id else "superseded"
                ),
                "generated_by": version.generated_by,
                "forward_verified": version.forward_verified,
                "reaches_destination": version.reaches_destination,
                "risk_count": len(version.prerequisite_risks or []),
                "approved_at": version.approved_at,
                "created_at": version.created_at,
            }
            for version in versions
        ]
    except Exception as exc:
        _raise_http(exc)


@router.get("/{unit_id}/path/versions/{version_id}")
async def get_historical_path(
    unit_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await get_path_version(session, unit_id=unit.id, version_id=version_id)
        return await _path_payload(session, version)
    except Exception as exc:
        _raise_http(exc)


@router.post("/{unit_id}/path/versions/{version_id}:restore")
async def post_path_version_restore(
    unit_id: str,
    version_id: str,
    request: RestorePathVersionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        active = await _active_version(session, unit)
        assert_path_mutation_fresh(
            active,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        if version_id == active.id:
            raise ValueError("The active path version is already selected")
        source = await get_path_version(session, unit_id=unit.id, version_id=version_id)
        restored, _mapping = await clone_path_version(
            session,
            unit=unit,
            source=source,
            supersede_active=active,
            generated_by=f"path_restore:{request.reason.strip()}",
        )
        await session.commit()
        return await _path_payload(session, restored)
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.get("/{unit_id}/path/status")
async def get_path_status(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        lessons = list(
            await session.scalars(
                select(PathLessonModel)
                .where(PathLessonModel.path_version_id == version.id)
                .order_by(PathLessonModel.position)
            )
        )
        pack_ids = [lesson.pack_id for lesson in lessons if lesson.pack_id]
        generations = {
            row.id: row
            for row in (
                list(
                    await session.scalars(
                        select(GenerationModel).where(GenerationModel.id.in_(pack_ids))
                    )
                )
                if pack_ids
                else []
            )
        }
        provenance = {
            row.pack_id: row
            for row in (
                list(
                    await session.scalars(
                        select(LessonProvenanceModel).where(
                            LessonProvenanceModel.pack_id.in_(pack_ids)
                        )
                    )
                )
                if pack_ids
                else []
            )
        }
        statuses = {
            name: 0
            for name in (
                "unprepared",
                "awaiting_review",
                "generating",
                "ready",
                "warning",
                "failed",
                "skipped",
                "stale",
            )
        }
        lesson_states: list[dict[str, object]] = []
        for lesson in lessons:
            warnings: list[str] = []
            if lesson.skipped:
                state = "skipped"
            elif not lesson.pack_id:
                state = "warning" if lesson.merge_warning else "unprepared"
                if lesson.merge_warning:
                    warnings.append("Adjacent merge review requires attention")
            else:
                generation = generations.get(lesson.pack_id)
                record = provenance.get(lesson.pack_id)
                if generation is None or record is None:
                    state = "warning"
                    warnings.append("Preparation linkage is incomplete")
                elif (
                    record.path_lesson_id != lesson.id
                    or record.objective_hash != lesson.objective_hash
                    or record.path_lesson_revision not in {None, lesson.revision}
                    or record.invalidated_at is not None
                ):
                    state = "stale"
                else:
                    raw = str(generation.status or "unknown").casefold()
                    if raw in {"awaiting_review", "review"}:
                        state = "awaiting_review"
                    elif raw in {"queued", "planning", "running", "generating", "writing"}:
                        state = "generating"
                    elif raw in {"completed", "complete", "ready", "landed", "succeeded"}:
                        state = "ready"
                    elif raw in {"failed", "error", "cancelled"}:
                        state = "failed"
                    else:
                        state = "warning"
                        warnings.append(f"Unrecognized generation state: {raw}")
            statuses[state] += 1
            lesson_states.append(
                {
                    "path_lesson_id": lesson.id,
                    "state": state,
                    "generation_id": lesson.pack_id,
                    "warnings": warnings,
                }
            )
        return {
            "path_version_id": version.id,
            "path_revision": version.revision,
            "counts": statuses,
            "lessons": lesson_states,
        }
    except Exception as exc:
        _raise_http(exc)


@router.get("/{unit_id}/schedule")
async def get_teaching_schedule(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        return await schedule_payload(session, version=version)
    except Exception as exc:
        _raise_http(exc)


@router.put("/{unit_id}/schedule")
async def put_teaching_schedule(
    unit_id: str,
    request: ScheduleWriteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        payload = await write_schedule(session, version=version, request=request)
        await session.commit()
        return payload
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/schedule:suggest")
async def post_teaching_schedule_suggestion(
    unit_id: str,
    request: ScheduleSuggestRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        return await suggest_schedule(session, version=version, request=request)
    except Exception as exc:
        _raise_http(exc)


@router.get("/{unit_id}/groups")
async def get_unit_groups(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        return await groups_payload(session, unit=unit)
    except Exception as exc:
        _raise_http(exc)


@router.put("/{unit_id}/groups")
async def put_unit_groups(
    unit_id: str,
    request: UnitGroupsWriteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        payload = await write_groups(session, unit=unit, request=request)
        await session.commit()
        return payload
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.patch("/{unit_id}/path/lessons/{lesson_id}")
async def patch_path_lesson(
    unit_id: str,
    lesson_id: str,
    request: GuardedPathLessonPatch,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        _unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=request.lesson_revision)
        await patch_lesson(session, lesson=lesson, request=request)
        await invalidate_path_approval(session, version)
        await session.commit()
        return {
            "id": lesson.id,
            "objective": lesson.objective,
            "revision": lesson.revision,
            "path_version_id": version.id,
            "path_revision": version.revision,
        }
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}:skip")
async def post_path_lesson_skip(
    unit_id: str,
    lesson_id: str,
    request: PathLessonMutationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=request.lesson_revision)
        cloned, mapping = await clone_path_version(
            session,
            unit=unit,
            source=version,
            supersede_active=version,
            generated_by="teacher_skip",
        )
        copied = mapping[lesson.id]
        await skip_lesson(session, copied)
        await invalidate_path_approval(session, cloned)
        await session.commit()
        return await _path_payload(session, cloned)
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}:split")
async def post_path_lesson_split(
    unit_id: str,
    lesson_id: str,
    request: GuardedSplitPathLessonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=request.lesson_revision)
        cloned, mapping = await clone_path_version(
            session,
            unit=unit,
            source=version,
            supersede_active=version,
            generated_by="teacher_split",
        )
        copied = mapping[lesson.id]
        parts = await split_lesson(
            session, unit=unit, version=cloned, lesson=copied, request=request
        )
        await invalidate_path_approval(session, cloned)
        await session.commit()
        return {
            "path": await _path_payload(session, cloned),
            "source_lesson_id": copied.id,
            "part_ids": [part.id for part in parts],
        }
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons:merge")
async def post_path_lessons_merge(
    unit_id: str,
    request: GuardedMergePathLessonsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        source_lessons = [
            await get_path_lesson(session, version_id=version.id, lesson_id=lesson_id)
            for lesson_id in request.lesson_ids
        ]
        for lesson in source_lessons:
            expected = request.lesson_revisions.get(lesson.id)
            if expected is None:
                raise ValueError("Every merged lesson requires an expected revision")
            assert_lesson_mutation_fresh(lesson, lesson_revision=expected)
        cloned, mapping = await clone_path_version(
            session,
            unit=unit,
            source=version,
            supersede_active=version,
            generated_by="teacher_merge",
        )
        cloned_request = request.model_copy(
            update={"lesson_ids": [mapping[lesson.id].id for lesson in source_lessons]}
        )
        merged = await merge_lessons(
            session, unit=unit, version=cloned, request=cloned_request
        )
        await invalidate_path_approval(session, cloned)
        await session.commit()
        return {
            "path": await _path_payload(session, cloned),
            "merged_lesson_id": merged.id,
            "source": merged.source,
        }
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons:reorder")
async def post_path_lessons_reorder(
    unit_id: str,
    request: GuardedReorderPathLessonsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        cloned, mapping = await clone_path_version(
            session,
            unit=unit,
            source=version,
            supersede_active=version,
            generated_by="teacher_reorder",
        )
        cloned_request = request.model_copy(
            update={"lesson_ids": [mapping[lesson_id].id for lesson_id in request.lesson_ids]}
        )
        lessons = await reorder_lessons(
            session, version_id=cloned.id, request=cloned_request
        )
        await invalidate_path_approval(session, cloned)
        await session.commit()
        return {
            "path": await _path_payload(session, cloned),
            "lesson_ids": [lesson.id for lesson in lessons],
        }
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}:prepare")
async def post_path_lesson_prepare(
    unit_id: str,
    lesson_id: str,
    request: GuardedPrepareLessonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=request.lesson_revision)
        response, _plan = await prepare_path_lesson(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(
                group_ids=request.group_ids,
                lesson_mode=request.lesson_mode,
            ),
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
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=request.lesson_revision)
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
            provenance.path_lesson_id != lesson.id
            or provenance.objective_hash != lesson.objective_hash
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


@router.get("/{unit_id}/path/lessons/{lesson_id}/shape")
async def get_path_lesson_shape(
    unit_id: str,
    lesson_id: str,
    lesson_mode: Literal[
        "first_exposure", "consolidation", "repair", "retrieval", "transfer"
    ] = Query(default="first_exposure"),
    misconception_count: int = Query(default=1, ge=0, le=3),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        _unit, _version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        return await lesson_shape_payload(
            session,
            lesson=lesson,
            lesson_mode=lesson_mode,
            misconception_count=misconception_count,
        )
    except Exception as exc:
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}/shape/deviations")
async def post_path_lesson_shape_deviation(
    unit_id: str,
    lesson_id: str,
    request: ShapeDeviationCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        _unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=request.lesson_revision)
        deviation = await request_shape_deviation(session, lesson=lesson, request=request)
        await session.commit()
        return deviation_payload(deviation)
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


async def _decide_path_lesson_shape_deviation(
    *,
    unit_id: str,
    lesson_id: str,
    deviation_id: str,
    request: ShapeDeviationDecisionRequest,
    current_user: User,
    session: AsyncSession,
    approved: bool,
) -> dict[str, object]:
    try:
        _unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        assert_path_mutation_fresh(
            version,
            path_version_id=request.path_version_id,
            path_revision=request.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=request.lesson_revision)
        deviation = await decide_shape_deviation(
            session,
            lesson=lesson,
            deviation_id=deviation_id,
            approved=approved,
            decided_by=current_user.id,
        )
        await session.commit()
        return {
            **deviation_payload(deviation),
            "lesson_revision": lesson.revision,
        }
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}/shape/deviations/{deviation_id}:approve")
async def approve_path_lesson_shape_deviation(
    unit_id: str,
    lesson_id: str,
    deviation_id: str,
    request: ShapeDeviationDecisionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    return await _decide_path_lesson_shape_deviation(
        unit_id=unit_id,
        lesson_id=lesson_id,
        deviation_id=deviation_id,
        request=request,
        current_user=current_user,
        session=session,
        approved=True,
    )


@router.post("/{unit_id}/path/lessons/{lesson_id}/shape/deviations/{deviation_id}:reject")
async def reject_path_lesson_shape_deviation(
    unit_id: str,
    lesson_id: str,
    deviation_id: str,
    request: ShapeDeviationDecisionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    return await _decide_path_lesson_shape_deviation(
        unit_id=unit_id,
        lesson_id=lesson_id,
        deviation_id=deviation_id,
        request=request,
        current_user=current_user,
        session=session,
        approved=False,
    )
