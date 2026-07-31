from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    ConceptModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    PathVersionModel,
    UnitModel,
    UnitScopeContractModel,
)
from planning.models import (
    LessonPart,
    MergePathLessonsRequest,
    PathLessonPatch,
    PathPlan,
    ReorderPathLessonsRequest,
    SplitPathLessonRequest,
    UnitCreate,
    UnitUpdate,
)
from planning.validation import PathApprovalBlocked, assert_approvable, validate_path_plan
from v3_blueprint.planning.objective_ownership import hash_path_objective


class PathNotFoundError(LookupError):
    pass


class ConceptResolutionError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_unit(session: AsyncSession, *, owner_id: str, request: UnitCreate) -> UnitModel:
    unit = UnitModel(owner_id=owner_id, **request.model_dump())
    session.add(unit)
    await session.flush()
    return unit


async def update_unit(session: AsyncSession, unit: UnitModel, request: UnitUpdate) -> UnitModel:
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)
    await session.flush()
    return unit


async def get_owned_unit(session: AsyncSession, *, unit_id: str, owner_id: str) -> UnitModel:
    unit = await session.scalar(
        select(UnitModel).where(UnitModel.id == unit_id, UnitModel.owner_id == owner_id)
    )
    if unit is None:
        raise PathNotFoundError("Unit not found")
    return unit


async def _resolve_concept(
    session: AsyncSession,
    *,
    slug: str,
    title: str,
    subject: str,
    owner_id: str,
) -> ConceptModel:
    concept = await session.scalar(select(ConceptModel).where(ConceptModel.canonical_slug == slug))
    if concept is not None:
        if concept.subject.casefold() != subject.casefold():
            raise ConceptResolutionError(
                f"Canonical slug {slug!r} already belongs to subject {concept.subject!r}"
            )
        return concept
    concept = ConceptModel(
        canonical_slug=slug,
        subject=subject,
        title=title,
        status="draft",
        created_by=owner_id,
    )
    session.add(concept)
    await session.flush()
    return concept


async def _next_version(session: AsyncSession, unit_id: str) -> int:
    current = await session.scalar(
        select(func.max(PathVersionModel.version)).where(PathVersionModel.unit_id == unit_id)
    )
    return int(current or 0) + 1


async def persist_path_plan(
    session: AsyncSession,
    *,
    unit: UnitModel,
    plan: PathPlan,
    generated_by: str = "path_planner",
    prior_version: PathVersionModel | None = None,
    merge_critic_results: list[dict[str, object]] | None = None,
) -> PathVersionModel:
    validate_path_plan(plan)
    scope = plan.scope_contract
    existing_scope = await session.get(UnitScopeContractModel, unit.id)
    if existing_scope is None:
        existing_scope = UnitScopeContractModel(unit_id=unit.id)
        session.add(existing_scope)
    for field, value in scope.model_dump().items():
        setattr(existing_scope, field, value)

    prior_by_slug: dict[str, PathLessonModel] = {}
    if prior_version is not None:
        rows = await session.scalars(
            select(PathLessonModel).where(PathLessonModel.path_version_id == prior_version.id)
        )
        prior_by_slug = {lesson.concept_slug: lesson for lesson in rows}

    version = PathVersionModel(
        unit_id=unit.id,
        version=await _next_version(session, unit.id),
        status="draft",
        generated_by=generated_by,
        source_plan_json=plan.model_dump(mode="json"),
        merge_critic_results=merge_critic_results or [],
        prerequisite_risks=[risk.model_dump(mode="json") for risk in plan.prerequisite_risks],
        forward_verified=plan.completeness.forward_verified,
        reaches_destination=plan.completeness.reaches_destination,
    )
    session.add(version)
    await session.flush()

    lesson_by_slug: dict[str, PathLessonModel] = {}
    for position, planned in enumerate(plan.lessons):
        concept = await _resolve_concept(
            session,
            slug=planned.concept_candidate.slug,
            title=planned.concept_candidate.title,
            subject=unit.subject,
            owner_id=unit.owner_id,
        )
        prior = prior_by_slug.get(planned.concept_candidate.slug)
        preserve_edit = prior is not None and prior.teacher_edited
        objective = prior.objective if preserve_edit else planned.objective
        lesson = PathLessonModel(
            path_version_id=version.id,
            concept_id=concept.id,
            concept_slug=planned.concept_candidate.slug,
            title=prior.title if preserve_edit else planned.concept_candidate.title,
            objective=objective,
            objective_hash=hash_path_objective(objective),
            external_prerequisites=planned.external_prerequisites,
            must_establish=(prior.must_establish if preserve_edit else planned.must_establish),
            exclusions=prior.exclusions if preserve_edit else planned.exclusions,
            primary_knowledge_type=(
                prior.primary_knowledge_type if preserve_edit else planned.primary_knowledge_type
            ),
            secondary_demand=(prior.secondary_demand if preserve_edit else planned.secondary_demand),
            knowledge_type_source="teacher" if preserve_edit else "path_planner",
            merge_warning=planned.merge_warning,
            position=position,
            source="replan" if prior_version is not None else "path_planner",
            teacher_edited=preserve_edit,
            revision=(prior.revision if preserve_edit else 1),
        )
        session.add(lesson)
        lesson_by_slug[planned.concept_candidate.slug] = lesson
    await session.flush()

    for planned in plan.lessons:
        lesson = lesson_by_slug[planned.concept_candidate.slug]
        for prerequisite_slug in planned.prerequisites:
            session.add(
                PathLessonPrerequisiteModel(
                    path_lesson_id=lesson.id,
                    prerequisite_lesson_id=lesson_by_slug[prerequisite_slug].id,
                )
            )
    unit.active_path_version_id = version.id
    await session.flush()
    return version


async def patch_lesson(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    request: PathLessonPatch,
) -> PathLessonModel:
    changes = request.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(lesson, field, value)
    if "objective" in changes:
        lesson.objective_hash = hash_path_objective(lesson.objective)
    lesson.teacher_edited = True
    lesson.knowledge_type_source = "teacher"
    lesson.revision += 1
    await session.flush()
    return lesson


async def skip_lesson(session: AsyncSession, lesson: PathLessonModel) -> PathLessonModel:
    lesson.skipped = True
    lesson.teacher_edited = True
    lesson.revision += 1
    await session.flush()
    return lesson


async def reorder_lessons(
    session: AsyncSession,
    *,
    version_id: str,
    request: ReorderPathLessonsRequest,
) -> list[PathLessonModel]:
    lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version_id)
            .order_by(PathLessonModel.position)
        )
    )
    by_id = {lesson.id: lesson for lesson in lessons}
    if len(request.lesson_ids) != len(set(request.lesson_ids)) or set(request.lesson_ids) != set(by_id):
        raise ValueError("Reorder must contain every path lesson exactly once")
    desired_position = {lesson_id: position for position, lesson_id in enumerate(request.lesson_ids)}
    links = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel).where(
                PathLessonPrerequisiteModel.path_lesson_id.in_(request.lesson_ids)
            )
        )
    )
    if any(
        desired_position[link.prerequisite_lesson_id] >= desired_position[link.path_lesson_id]
        for link in links
    ):
        raise ValueError("Reorder would create a forward prerequisite reference")
    for offset, lesson in enumerate(lessons, start=1):
        lesson.position = -(offset)
    await session.flush()
    ordered = [by_id[lesson_id] for lesson_id in request.lesson_ids]
    for position, lesson in enumerate(ordered):
        lesson.position = position
        lesson.teacher_edited = True
    await session.flush()
    return ordered


async def _lesson_from_part(
    session: AsyncSession,
    *,
    version: PathVersionModel,
    unit: UnitModel,
    part: LessonPart,
    position: int,
    source: str,
) -> PathLessonModel:
    concept = await _resolve_concept(
        session,
        slug=part.concept_candidate.slug,
        title=part.concept_candidate.title,
        subject=unit.subject,
        owner_id=unit.owner_id,
    )
    lesson = PathLessonModel(
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=part.concept_candidate.slug,
        title=part.concept_candidate.title,
        objective=part.objective,
        objective_hash=hash_path_objective(part.objective),
        external_prerequisites=[],
        must_establish=part.must_establish,
        exclusions=part.exclusions,
        primary_knowledge_type=part.primary_knowledge_type,
        secondary_demand=part.secondary_demand,
        knowledge_type_source="teacher",
        position=position,
        source=source,
        teacher_edited=True,
    )
    session.add(lesson)
    await session.flush()
    return lesson


async def split_lesson(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    lesson: PathLessonModel,
    request: SplitPathLessonRequest,
) -> list[PathLessonModel]:
    inherited_prerequisites = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel).where(
                PathLessonPrerequisiteModel.path_lesson_id == lesson.id
            )
        )
    )
    lesson.skipped = True
    lesson.teacher_edited = True
    max_position = await session.scalar(
        select(func.max(PathLessonModel.position)).where(PathLessonModel.path_version_id == version.id)
    )
    parts: list[PathLessonModel] = []
    for offset, part in enumerate(request.parts, start=1):
        parts.append(
            await _lesson_from_part(
                session,
                version=version,
                unit=unit,
                part=part,
                position=int(max_position or 0) + offset,
                source="teacher_split",
            )
        )
    for inherited in inherited_prerequisites:
        session.add(
            PathLessonPrerequisiteModel(
                path_lesson_id=parts[0].id,
                prerequisite_lesson_id=inherited.prerequisite_lesson_id,
            )
        )
    for prior, current in zip(parts, parts[1:], strict=False):
        session.add(
            PathLessonPrerequisiteModel(
                path_lesson_id=current.id,
                prerequisite_lesson_id=prior.id,
            )
        )
    await session.flush()
    return parts


async def merge_lessons(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    request: MergePathLessonsRequest,
) -> PathLessonModel:
    lessons = list(
        await session.scalars(
            select(PathLessonModel).where(
                PathLessonModel.path_version_id == version.id,
                PathLessonModel.id.in_(request.lesson_ids),
            )
        )
    )
    if len(lessons) != len(request.lesson_ids):
        raise PathNotFoundError("One or more merge lessons were not found")
    positions = sorted(lesson.position for lesson in lessons)
    if positions != list(range(positions[0], positions[0] + len(positions))):
        raise ValueError("Only adjacent lessons can be merged")
    source_ids = {lesson.id for lesson in lessons}
    inherited_prerequisite_ids = {
        link.prerequisite_lesson_id
        for link in await session.scalars(
            select(PathLessonPrerequisiteModel).where(
                PathLessonPrerequisiteModel.path_lesson_id.in_(source_ids)
            )
        )
        if link.prerequisite_lesson_id not in source_ids
    }
    for lesson in lessons:
        lesson.skipped = True
        lesson.teacher_edited = True
    max_position = await session.scalar(
        select(func.max(PathLessonModel.position)).where(PathLessonModel.path_version_id == version.id)
    )
    merged = await _lesson_from_part(
        session,
        version=version,
        unit=unit,
        part=request.merged,
        position=int(max_position or 0) + 1,
        source="teacher_merge",
    )
    for prerequisite_id in inherited_prerequisite_ids:
        session.add(
            PathLessonPrerequisiteModel(
                path_lesson_id=merged.id,
                prerequisite_lesson_id=prerequisite_id,
            )
        )
    await session.flush()
    return merged


async def approve_path(session: AsyncSession, version: PathVersionModel) -> PathVersionModel:
    plan = PathPlan.model_validate(version.source_plan_json)
    assert_approvable(plan)
    if version.prerequisite_risks or not version.reaches_destination:
        raise PathApprovalBlocked("Path approval blocked by persisted prerequisite risks")
    lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    if not lessons:
        raise PathApprovalBlocked("Path approval blocked: path has no lessons")
    if any(lesson.skipped for lesson in lessons):
        raise PathApprovalBlocked(
            "Path approval blocked: skipped lessons require replan or explicit scope review"
        )
    if len({lesson.concept_slug for lesson in lessons}) != len(lessons):
        raise PathApprovalBlocked("Path approval blocked: duplicate canonical concept slug")
    positions = {lesson.id: lesson.position for lesson in lessons}
    links = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel).where(
                PathLessonPrerequisiteModel.path_lesson_id.in_(positions)
            )
        )
    )
    if any(
        link.prerequisite_lesson_id not in positions
        or positions[link.prerequisite_lesson_id] >= positions[link.path_lesson_id]
        for link in links
    ):
        raise PathApprovalBlocked(
            "Path approval blocked: every prerequisite must resolve to an earlier lesson"
        )
    unit = await session.get(UnitModel, version.unit_id)
    if unit is None:
        raise PathNotFoundError("Unit not found")
    scope = await session.get(UnitScopeContractModel, unit.id)
    if scope is None:
        raise PathApprovalBlocked("Path approval blocked: scope contract is missing")
    allowed_external = {
        value.casefold()
        for value in [*(scope.assumed_prerequisites or []), *(unit.starting_knowledge or [])]
    }
    prohibited = [term.casefold() for term in (scope.must_not_introduce or []) if term.strip()]
    for lesson in lessons:
        if lesson.objective_hash != hash_path_objective(lesson.objective):
            raise PathApprovalBlocked("Path approval blocked: objective hash mismatch")
        if any(
            prerequisite.casefold() not in allowed_external
            for prerequisite in (lesson.external_prerequisites or [])
        ):
            raise PathApprovalBlocked(
                "Path approval blocked: undeclared external prerequisite"
            )
        inspected = "\n".join([lesson.objective, *(lesson.must_establish or [])]).casefold()
        if any(term in inspected for term in prohibited):
            raise PathApprovalBlocked("Path approval blocked: must-not-introduce violation")
    version.status = "approved"
    version.approved_at = _utcnow()
    unit.status = "approved"
    unit.active_path_version_id = version.id
    await session.flush()
    return version


async def get_path_version(
    session: AsyncSession,
    *,
    unit_id: str,
    version_id: str | None = None,
) -> PathVersionModel:
    statement = select(PathVersionModel).where(PathVersionModel.unit_id == unit_id)
    if version_id is not None:
        statement = statement.where(PathVersionModel.id == version_id)
    else:
        statement = statement.order_by(PathVersionModel.version.desc())
    version = await session.scalar(statement)
    if version is None:
        raise PathNotFoundError("Path version not found")
    return version


async def get_path_lesson(
    session: AsyncSession,
    *,
    version_id: str,
    lesson_id: str,
) -> PathLessonModel:
    lesson = await session.scalar(
        select(PathLessonModel).where(
            PathLessonModel.path_version_id == version_id,
            PathLessonModel.id == lesson_id,
        )
    )
    if lesson is None:
        raise PathNotFoundError("Path lesson not found")
    return lesson
