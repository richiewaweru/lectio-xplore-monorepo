from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.middleware import get_current_user
from core.capabilities import require_xplore_v2
from core.database.models import (
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    ResourceCompositionModel,
    UnitGroupModel,
    UnitModel,
    UnitScopeContractModel,
)
from core.dependencies import get_async_session
from core.entities.user import User
from core.rate_limit import limiter
from planning.agents import (
    run_adjacent_merge_critics,
    run_constructor,
    run_path_planner,
    run_plan_chat_edit,
)
from planning.bridge import PathPreparationBlocked, prepare_path_lesson
from planning.models import (
    ConstructorReadbackRequest,
    GuardedMergePathLessonsRequest,
    GuardedPrepareLessonRequest,
    GuardedPathLessonPatch,
    GuardedReorderPathLessonsRequest,
    GuardedSplitPathLessonRequest,
    LessonActualWriteRequest,
    MarksWriteRequest,
    PathChatEditRequest,
    PathLessonMutationRequest,
    PathPlan,
    PathPlannerRequest,
    PathReplanRequest,
    PathVersionMutationRequest,
    PrepareLessonRequest,
    PreparedLessonStatusResponse,
    RegenerateLessonRequest,
    ResolvePathAssumptionRequest,
    ResourceComposeRequest,
    RestorePathVersionRequest,
    ScheduleSuggestRequest,
    ScheduleWriteRequest,
    ShapeDeviationCreateRequest,
    ShapeDeviationDecisionRequest,
    UnitCreate,
    UnitGroupsWriteRequest,
    UnitUpdate,
)
from planning.outcomes import (
    OutcomeValidationError,
    StaleOutcomeError,
    actual_payload,
    latest_actual,
    marks_summary,
    record_lesson_actual,
    record_marks,
)
from planning.schedule import (
    groups_payload,
    schedule_payload,
    suggest_schedule,
    write_groups,
    write_schedule,
)
from planning.projections import (
    ProjectionUnavailable,
    build_composition_payload,
    composition_payload,
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
    resolve_path_assumption,
    skip_lesson,
    split_lesson,
    update_unit,
)
from planning.validation import (
    PathApprovalBlocked,
    PathValidationError,
    open_assumptions,
    plain_validation_message,
    validate_path_plan,
)
from v3_blueprint.planning.persistence import load_chunked_state


router = APIRouter(
    prefix="/api/v1/units",
    tags=["units", "paths"],
    dependencies=[Depends(require_xplore_v2)],
)


def _unit_payload(unit: UnitModel) -> dict[str, object]:
    return {
        "id": unit.id,
        "title": unit.title,
        "topic": unit.topic,
        "subject": unit.subject,
        "grade_level": unit.grade_level,
        "curriculum_context": unit.curriculum_context,
        "class_notes": unit.class_notes,
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
    scope = await session.get(UnitScopeContractModel, version.unit_id) if unit is not None else None
    assumptions = (
        open_assumptions(
            starting_knowledge=unit.starting_knowledge if unit is not None else [],
            assumed_prerequisites=scope.assumed_prerequisites if scope is not None else [],
            lessons=lessons,
            prerequisite_risks=version.prerequisite_risks,
        )
        if unit is not None
        else []
    )
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
        "open_assumptions": assumptions,
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
    if isinstance(
        exc,
        (PathApprovalBlocked, PathPreparationBlocked, StalePathMutationError, StaleOutcomeError),
    ):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ProjectionUnavailable):
        raise HTTPException(
            status_code=409,
            detail={"code": "projection_unavailable", "message": str(exc)},
        ) from exc
    if isinstance(exc, PathValidationError):
        raise HTTPException(status_code=422, detail=plain_validation_message(exc)) from exc
    if isinstance(exc, (ConceptResolutionError, OutcomeValidationError, ValueError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.post("/constructor/readback")
@limiter.limit("20/minute")
async def post_constructor_readback(
    request: Request,
    body: ConstructorReadbackRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    from core.prompts import bind_prompt_cache, reset_prompt_cache, resolve_all_prompts

    prompt_texts, _prompt_hashes = await resolve_all_prompts(current_user.id, session)
    cache_token = bind_prompt_cache(prompt_texts)
    try:
        result = await run_constructor(
            body.subject,
            body.grade_level,
            body.raw_text,
            correction=body.correction,
            clarifying_answer=body.clarifying_answer,
            trace_id=f"constructor:{current_user.id}",
        )
    finally:
        reset_prompt_cache(cache_token)
    return result.model_dump(mode="json")


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
        from core.prompts import bind_prompt_cache, reset_prompt_cache, resolve_all_prompts

        prompt_texts, _prompt_hashes = await resolve_all_prompts(current_user.id, session)
        cache_token = bind_prompt_cache(prompt_texts)
        try:
            plan = await run_path_planner(planner_request, trace_id=f"unit:{unit.id}")
            merge_results = await run_adjacent_merge_critics(
                plan,
                trace_id=f"unit:{unit.id}",
            )
        finally:
            reset_prompt_cache(cache_token)
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
@limiter.limit("6/minute")
async def post_path_plan(
    request: Request,
    unit_id: str,
    body: PathPlannerRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    return await _plan_or_replan(
        unit_id=unit_id,
        request=body,
        current_user=current_user,
        session=session,
        replan=False,
    )


@router.post("/{unit_id}/path:replan", status_code=status.HTTP_201_CREATED)
@limiter.limit("6/minute")
async def post_path_replan(
    request: Request,
    unit_id: str,
    body: PathReplanRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    return await _plan_or_replan(
        unit_id=unit_id,
        request=body,
        current_user=current_user,
        session=session,
        replan=True,
    )


@router.post("/{unit_id}/path:edit-chat")
@limiter.limit("12/minute")
async def post_path_chat_edit(
    request: Request,
    unit_id: str,
    body: PathChatEditRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        assert_path_mutation_fresh(
            version,
            path_version_id=body.path_version_id,
            path_revision=body.path_revision,
        )
        current_plan = PathPlan.model_validate(version.source_plan_json)

        from core.prompts import bind_prompt_cache, reset_prompt_cache, resolve_all_prompts

        prompt_texts, _prompt_hashes = await resolve_all_prompts(current_user.id, session)
        cache_token = bind_prompt_cache(prompt_texts)
        try:
            edited_plan = await run_plan_chat_edit(
                current_plan,
                body.message,
                unit_context={
                    "topic": unit.topic,
                    "subject": unit.subject,
                    "grade_level": unit.grade_level,
                    "destination_objective": unit.destination_objective,
                    "starting_knowledge": unit.starting_knowledge,
                    "curriculum_context": unit.curriculum_context,
                },
                trace_id=f"unit:{unit.id}:chat-edit",
            )
        finally:
            reset_prompt_cache(cache_token)

        try:
            validate_path_plan(edited_plan)
        except PathValidationError as exc:
            return {
                "path": await _path_payload(session, version),
                "validation_messages": [plain_validation_message(exc)],
            }

        new_version = await persist_path_plan(
            session,
            unit=unit,
            plan=edited_plan,
            generated_by="chat_editor",
            prior_version=version,
            merge_critic_results=version.merge_critic_results or [],
        )
        unit.status = "draft"
        await session.commit()
        return {
            "path": await _path_payload(session, new_version),
            "validation_messages": [],
        }
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


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


@router.post("/{unit_id}/path/assumptions/resolve")
async def post_resolve_path_assumption(
    unit_id: str,
    request: ResolvePathAssumptionRequest,
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
        await resolve_path_assumption(
            session,
            unit=unit,
            version=version,
            claimed=request.claimed,
            decision=request.decision,
        )
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
@limiter.limit("12/minute")
async def post_path_lesson_prepare(
    request: Request,
    unit_id: str,
    lesson_id: str,
    body: GuardedPrepareLessonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        assert_path_mutation_fresh(
            version,
            path_version_id=body.path_version_id,
            path_revision=body.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=body.lesson_revision)
        response, _plan = await prepare_path_lesson(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(
                group_ids=body.group_ids,
                lesson_mode=body.lesson_mode,
            ),
        )
        await session.commit()
        return response.model_dump(mode="json")
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}:regenerate")
@limiter.limit("6/minute")
async def post_path_lesson_regenerate(
    request: Request,
    unit_id: str,
    lesson_id: str,
    body: RegenerateLessonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        assert_path_mutation_fresh(
            version,
            path_version_id=body.path_version_id,
            path_revision=body.path_revision,
        )
        assert_lesson_mutation_fresh(lesson, lesson_revision=body.lesson_revision)
        response, _plan = await prepare_path_lesson(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(
                group_ids=body.group_ids,
                lesson_mode=body.lesson_mode,
            ),
            regenerate=True,
            regeneration_reason=body.reason,
        )
        await session.commit()
        return {**response.model_dump(mode="json"), "regeneration_reason": body.reason}
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


@router.get("/{unit_id}/path/lessons/{lesson_id}/actual")
async def get_path_lesson_actual(
    unit_id: str,
    lesson_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object] | None:
    try:
        _unit, _version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        actual = await latest_actual(session, path_lesson_id=lesson.id)
        return actual_payload(actual) if actual else None
    except Exception as exc:
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}/actual")
async def post_path_lesson_actual(
    unit_id: str,
    lesson_id: str,
    request: LessonActualWriteRequest,
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
        actual = await record_lesson_actual(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=request,
            user_id=current_user.id,
        )
        await session.commit()
        return actual_payload(actual)
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.post("/{unit_id}/path/lessons/{lesson_id}/marks")
async def post_path_lesson_marks(
    unit_id: str,
    lesson_id: str,
    request: MarksWriteRequest,
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
        payload = await record_marks(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=request,
            user_id=current_user.id,
        )
        await session.commit()
        return payload
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.get("/{unit_id}/path/lessons/{lesson_id}/marks-summary")
async def get_path_lesson_marks_summary(
    unit_id: str,
    lesson_id: str,
    group_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit, _version, lesson = await _owned_version_and_lesson(
            session, unit_id=unit_id, lesson_id=lesson_id, owner_id=current_user.id
        )
        if group_id is not None:
            group = await session.get(UnitGroupModel, group_id)
            if group is None or group.unit_id != unit.id:
                raise OutcomeValidationError("Marks group is not owned by this unit")
        return await marks_summary(session, lesson=lesson, group_id=group_id)
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


@router.post("/{unit_id}/compose:preview")
@limiter.limit("60/minute")
async def preview_unit_resource(
    request: Request,
    unit_id: str,
    body: ResourceComposeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        return await build_composition_payload(
            session,
            unit=unit,
            version=version,
            request=body,
            persist=False,
        )
    except Exception as exc:
        _raise_http(exc)


@router.post("/{unit_id}/compose", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def compose_unit_resource(
    request: Request,
    unit_id: str,
    body: ResourceComposeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        version = await _active_version(session, unit)
        payload = await build_composition_payload(
            session,
            unit=unit,
            version=version,
            request=body,
            persist=True,
        )
        await session.commit()
        return payload
    except Exception as exc:
        await session.rollback()
        _raise_http(exc)


@router.get("/{unit_id}/compositions")
async def list_unit_compositions(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, object]]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        rows = await session.scalars(
            select(ResourceCompositionModel)
            .where(ResourceCompositionModel.unit_id == unit.id)
            .order_by(ResourceCompositionModel.created_at.desc())
        )
        return [composition_payload(row) for row in rows]
    except Exception as exc:
        _raise_http(exc)


@router.get("/{unit_id}/compositions/{composition_id}")
async def get_unit_composition(
    unit_id: str,
    composition_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        unit = await get_owned_unit(session, unit_id=unit_id, owner_id=current_user.id)
        row = await session.get(ResourceCompositionModel, composition_id)
        if row is None or row.unit_id != unit.id or row.owner_id != current_user.id:
            raise PathNotFoundError("Resource composition not found")
        return composition_payload(row)
    except Exception as exc:
        _raise_http(exc)
