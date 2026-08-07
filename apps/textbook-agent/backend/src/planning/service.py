from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
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
    CanonicalPathLesson,
    CanonicalPathPlan,
    CanonicalPathScope,
    CanonicalLessonPart,
    MergePathLessonsRequest,
    PathLessonPatch,
    ReorderPathLessonsRequest,
    SplitPathLessonRequest,
    UnitCreate,
    UnitUpdate,
)
from planning.validation import (
    PathApprovalBlocked,
    PathValidationError,
    adjacent_merge_hints,
    assert_concept_slugs_unique,
    concept_slug_for,
)
from v3_blueprint.planning.objective_ownership import hash_path_objective


class PathNotFoundError(LookupError):
    pass


class ConceptResolutionError(ValueError):
    pass


class StalePathMutationError(RuntimeError):
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
    plan: CanonicalPathPlan,
    generated_by: str = "path_planner",
    prior_version: PathVersionModel | None = None,
    merge_critic_results: list[dict[str, object]] | None = None,
) -> PathVersionModel:
    concept_slugs = assert_concept_slugs_unique(unit.subject, plan)

    existing_scope = await session.get(UnitScopeContractModel, unit.id)
    if existing_scope is None:
        existing_scope = UnitScopeContractModel(unit_id=unit.id)
        session.add(existing_scope)
    existing_scope.must_establish = list(plan.scope.must_cover)
    existing_scope.must_not_introduce = list(plan.scope.do_not_cover)
    existing_scope.may_include = []
    existing_scope.assumed_prerequisites = []
    existing_scope.terminology = []
    existing_scope.notation = None

    prior_by_slug: dict[str, PathLessonModel] = {}
    if prior_version is not None:
        rows = await session.scalars(
            select(PathLessonModel).where(PathLessonModel.path_version_id == prior_version.id)
        )
        prior_by_slug = {lesson.concept_slug: lesson for lesson in rows}
        prior_version.status = "superseded"
        prior_version.revision += 1

    version = PathVersionModel(
        unit_id=unit.id,
        version=await _next_version(session, unit.id),
        status="draft",
        generated_by=generated_by,
        source_plan_json=plan.model_dump(mode="json"),
        merge_critic_results=merge_critic_results if merge_critic_results is not None else [],
        prerequisite_risks=[],
        forward_verified=True,
        reaches_destination=True,
    )
    session.add(version)
    await session.flush()

    lesson_by_key: dict[str, PathLessonModel] = {}
    for position, planned in enumerate(plan.lessons):
        slug = concept_slugs[planned.key]
        concept = await _resolve_concept(
            session,
            slug=slug,
            title=planned.title,
            subject=unit.subject,
            owner_id=unit.owner_id,
        )
        prior = prior_by_slug.get(slug)
        preserve_edit = prior is not None and prior.teacher_edited
        objective = prior.objective if preserve_edit else planned.objective
        lesson = PathLessonModel(
            path_version_id=version.id,
            concept_id=concept.id,
            concept_slug=slug,
            title=prior.title if preserve_edit else planned.title,
            objective=objective,
            objective_hash=hash_path_objective(objective),
            external_prerequisites=[],
            must_establish=(prior.must_establish if preserve_edit else list(planned.must_establish)),
            exclusions=prior.exclusions if preserve_edit else [],
            primary_knowledge_type=(
                prior.primary_knowledge_type if preserve_edit else planned.knowledge_type
            ),
            secondary_demand=(prior.secondary_demand if preserve_edit else None),
            knowledge_type_source="teacher" if preserve_edit else "path_planner",
            merge_warning=False,
            position=position,
            source="replan" if prior_version is not None else "path_planner",
            teacher_edited=preserve_edit,
            revision=(prior.revision if preserve_edit else 1),
        )
        session.add(lesson)
        lesson_by_key[planned.key] = lesson
    await session.flush()

    for planned in plan.lessons:
        lesson = lesson_by_key[planned.key]
        for required_key in planned.requires:
            session.add(
                PathLessonPrerequisiteModel(
                    path_lesson_id=lesson.id,
                    prerequisite_lesson_id=lesson_by_key[required_key].id,
                )
            )
    unit.active_path_version_id = version.id
    await session.flush()
    await _refresh_merge_hints(session, version)
    return version


async def _refresh_merge_hints(session: AsyncSession, version: PathVersionModel) -> None:
    lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    version.merge_critic_results = adjacent_merge_hints(lessons)
    await session.flush()


async def canonical_plan_from_version(
    session: AsyncSession,
    version: PathVersionModel,
) -> CanonicalPathPlan:
    """Rebuild the editable minimal plan from persisted lessons + scope."""
    unit = await session.get(UnitModel, version.unit_id)
    if unit is None:
        raise PathNotFoundError("Unit not found")
    scope = await session.get(UnitScopeContractModel, unit.id)
    lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    if not lessons:
        raise PathValidationError("empty_lesson_list", "Path has no lessons to edit")

    links = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel).where(
                PathLessonPrerequisiteModel.path_lesson_id.in_([lesson.id for lesson in lessons])
            )
        )
    )
    id_to_key = {lesson.id: f"L{index}" for index, lesson in enumerate(lessons, start=1)}
    requires_by_id: dict[str, list[str]] = {lesson.id: [] for lesson in lessons}
    for link in links:
        prereq_key = id_to_key.get(link.prerequisite_lesson_id)
        if prereq_key is not None:
            requires_by_id[link.path_lesson_id].append(prereq_key)

    must_cover = list(scope.must_establish) if scope and scope.must_establish else ["unit outcomes"]
    do_not_cover = (
        list(scope.must_not_introduce)
        if scope and scope.must_not_introduce
        else ["out-of-grade content"]
    )

    return CanonicalPathPlan(
        scope=CanonicalPathScope(must_cover=must_cover, do_not_cover=do_not_cover),
        lessons=[
            CanonicalPathLesson(
                key=id_to_key[lesson.id],
                title=lesson.title,
                objective=lesson.objective,
                requires=requires_by_id[lesson.id],
                must_establish=list(lesson.must_establish or []),
                knowledge_type=lesson.primary_knowledge_type,  # type: ignore[arg-type]
            )
            for lesson in lessons
        ],
    )

def assert_path_mutation_fresh(
    version: PathVersionModel,
    *,
    path_version_id: str,
    path_revision: int,
) -> None:
    if version.id != path_version_id or version.revision != path_revision:
        raise StalePathMutationError(
            "This path changed in another session. Refresh before applying your edit."
        )


def assert_lesson_mutation_fresh(
    lesson: PathLessonModel,
    *,
    lesson_revision: int,
) -> None:
    if lesson.revision != lesson_revision:
        raise StalePathMutationError(
            "This lesson changed in another session. Refresh before applying your edit."
        )


async def clone_path_version(
    session: AsyncSession,
    *,
    unit: UnitModel,
    source: PathVersionModel,
    supersede_active: PathVersionModel,
    generated_by: str,
) -> tuple[PathVersionModel, dict[str, PathLessonModel]]:
    """Create a recoverable draft copy before a structural mutation or restore."""
    source_lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == source.id)
            .order_by(PathLessonModel.position)
        )
    )
    clone = PathVersionModel(
        unit_id=unit.id,
        version=await _next_version(session, unit.id),
        revision=1,
        status="draft",
        generated_by=generated_by,
        source_plan_json=source.source_plan_json,
        merge_critic_results=source.merge_critic_results,
        prerequisite_risks=source.prerequisite_risks,
        forward_verified=source.forward_verified,
        reaches_destination=source.reaches_destination,
    )
    session.add(clone)
    await session.flush()

    lesson_by_source_id: dict[str, PathLessonModel] = {}
    for lesson in source_lessons:
        copied = PathLessonModel(
            path_version_id=clone.id,
            concept_id=lesson.concept_id,
            concept_slug=lesson.concept_slug,
            title=lesson.title,
            objective=lesson.objective,
            objective_hash=lesson.objective_hash,
            external_prerequisites=lesson.external_prerequisites,
            opens_from=lesson.opens_from,
            must_establish=lesson.must_establish,
            exclusions=lesson.exclusions,
            primary_knowledge_type=lesson.primary_knowledge_type,
            secondary_demand=lesson.secondary_demand,
            knowledge_type_source=lesson.knowledge_type_source,
            merge_warning=lesson.merge_warning,
            position=lesson.position,
            source=generated_by,
            teacher_edited=lesson.teacher_edited,
            skipped=lesson.skipped,
            revision=lesson.revision,
            pack_id=None,
        )
        session.add(copied)
        lesson_by_source_id[lesson.id] = copied
    await session.flush()

    if source_lessons:
        source_ids = [lesson.id for lesson in source_lessons]
        links = list(
            await session.scalars(
                select(PathLessonPrerequisiteModel).where(
                    PathLessonPrerequisiteModel.path_lesson_id.in_(source_ids)
                )
            )
        )
        for link in links:
            prerequisite = lesson_by_source_id.get(link.prerequisite_lesson_id)
            dependent = lesson_by_source_id.get(link.path_lesson_id)
            if prerequisite is not None and dependent is not None:
                session.add(
                    PathLessonPrerequisiteModel(
                        path_lesson_id=dependent.id,
                        prerequisite_lesson_id=prerequisite.id,
                    )
                )

    supersede_active.status = "superseded"
    supersede_active.revision += 1
    unit.active_path_version_id = clone.id
    unit.status = "draft"
    await session.flush()
    return clone, lesson_by_source_id


async def patch_lesson(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    request: PathLessonPatch,
) -> PathLessonModel:
    changes = request.model_dump(
        exclude_unset=True,
        exclude={"path_version_id", "path_revision", "lesson_revision"},
    )
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


async def invalidate_path_approval(
    session: AsyncSession,
    version: PathVersionModel,
) -> None:
    version.revision += 1
    if version.status == "approved":
        version.status = "draft"
        version.approved_at = None
    unit = await session.get(UnitModel, version.unit_id)
    if unit is not None:
        unit.status = "draft"
    await session.flush()


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
    part: CanonicalLessonPart,
    position: int,
    source: str,
    exclude_lesson_ids: set[str] | None = None,
) -> PathLessonModel:
    slug = concept_slug_for(unit.subject, part.title)
    existing = await session.scalars(
        select(PathLessonModel).where(PathLessonModel.path_version_id == version.id)
    )
    for lesson in existing:
        if exclude_lesson_ids and lesson.id in exclude_lesson_ids:
            continue
        if lesson.concept_slug == slug:
            raise PathValidationError(
                "duplicate_concept_slug",
                f"Lesson title {part.title!r} would reuse concept slug {slug!r}",
            )
    concept = await _resolve_concept(
        session,
        slug=slug,
        title=part.title,
        subject=unit.subject,
        owner_id=unit.owner_id,
    )
    lesson = PathLessonModel(
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=slug,
        title=part.title,
        objective=part.objective,
        objective_hash=hash_path_objective(part.objective),
        external_prerequisites=[],
        must_establish=part.must_establish,
        exclusions=[],
        primary_knowledge_type=part.knowledge_type,
        secondary_demand=None,
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
    all_lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    links = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel).where(
                or_(
                    PathLessonPrerequisiteModel.path_lesson_id == lesson.id,
                    PathLessonPrerequisiteModel.prerequisite_lesson_id == lesson.id,
                )
            )
        )
    )
    incoming_ids = {
        link.prerequisite_lesson_id
        for link in links
        if link.path_lesson_id == lesson.id
    }
    outgoing_ids = {
        link.path_lesson_id
        for link in links
        if link.prerequisite_lesson_id == lesson.id
    }
    for link in links:
        await session.delete(link)
    for offset, existing in enumerate(all_lessons, start=1):
        existing.position = -offset
    await session.flush()

    source_position = lesson.position * -1 - 1
    parts: list[PathLessonModel] = []
    for offset, part in enumerate(request.parts):
        parts.append(
            await _lesson_from_part(
                session,
                version=version,
                unit=unit,
                part=part,
                position=source_position + offset,
                source="teacher_split",
                exclude_lesson_ids={lesson.id},
            )
        )
    parts[0].external_prerequisites = list(lesson.external_prerequisites or [])
    for prerequisite_id in incoming_ids:
        session.add(
            PathLessonPrerequisiteModel(
                path_lesson_id=parts[0].id,
                prerequisite_lesson_id=prerequisite_id,
            )
        )
    for prior, current in zip(parts, parts[1:], strict=False):
        session.add(
            PathLessonPrerequisiteModel(
                path_lesson_id=current.id,
                prerequisite_lesson_id=prior.id,
            )
        )
    for dependent_id in outgoing_ids:
        session.add(
            PathLessonPrerequisiteModel(
                path_lesson_id=dependent_id,
                prerequisite_lesson_id=parts[-1].id,
            )
        )
    await session.delete(lesson)
    remaining = [existing for existing in all_lessons if existing.id != lesson.id]
    ordered = remaining[:source_position] + parts + remaining[source_position:]
    for position, current in enumerate(ordered):
        current.position = position
    await _refresh_merge_hints(session, version)
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
    lessons.sort(key=lambda lesson: lesson.position)
    positions = [lesson.position for lesson in lessons]
    if positions != list(range(positions[0], positions[0] + len(positions))):
        raise ValueError("Only adjacent lessons can be merged")
    source_ids = {lesson.id for lesson in lessons}
    all_lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    links = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel).where(
                or_(
                    PathLessonPrerequisiteModel.path_lesson_id.in_(source_ids),
                    PathLessonPrerequisiteModel.prerequisite_lesson_id.in_(source_ids),
                )
            )
        )
    )
    incoming_ids = {
        link.prerequisite_lesson_id
        for link in links
        if link.path_lesson_id in source_ids and link.prerequisite_lesson_id not in source_ids
    }
    outgoing_ids = {
        link.path_lesson_id
        for link in links
        if link.path_lesson_id not in source_ids and link.prerequisite_lesson_id in source_ids
    }
    for link in links:
        await session.delete(link)
    for offset, existing in enumerate(all_lessons, start=1):
        existing.position = -offset
    await session.flush()

    merged = await _lesson_from_part(
        session,
        version=version,
        unit=unit,
        part=request.merged,
        position=positions[0],
        source="teacher_merge",
        exclude_lesson_ids=source_ids,
    )
    merged.external_prerequisites = list(
        dict.fromkeys(
            prerequisite
            for source in lessons
            for prerequisite in (source.external_prerequisites or [])
        )
    )
    for prerequisite_id in incoming_ids:
        session.add(
            PathLessonPrerequisiteModel(
                path_lesson_id=merged.id,
                prerequisite_lesson_id=prerequisite_id,
            )
        )
    for dependent_id in outgoing_ids:
        session.add(
            PathLessonPrerequisiteModel(
                path_lesson_id=dependent_id,
                prerequisite_lesson_id=merged.id,
            )
        )
    for source in lessons:
        await session.delete(source)
    remaining = [existing for existing in all_lessons if existing.id not in source_ids]
    ordered = remaining[: positions[0]] + [merged] + remaining[positions[0] :]
    for position, current in enumerate(ordered):
        current.position = position
    await _refresh_merge_hints(session, version)
    await session.flush()
    return merged


async def insert_foundation_lesson(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    before_lesson_id: str,
    part: CanonicalLessonPart,
) -> PathLessonModel:
    all_lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    target = next((lesson for lesson in all_lessons if lesson.id == before_lesson_id), None)
    if target is None:
        raise PathNotFoundError(f"Lesson {before_lesson_id!r} was not found on this path")

    target_index = target.position
    for offset, existing in enumerate(all_lessons, start=1):
        existing.position = -offset
    await session.flush()

    new_lesson = await _lesson_from_part(
        session,
        version=version,
        unit=unit,
        part=part,
        position=target_index,
        source="teacher_foundation",
    )
    session.add(
        PathLessonPrerequisiteModel(
            path_lesson_id=target.id,
            prerequisite_lesson_id=new_lesson.id,
        )
    )
    ordered = all_lessons[:target_index] + [new_lesson] + all_lessons[target_index:]
    for position, current in enumerate(ordered):
        current.position = position
    await _refresh_merge_hints(session, version)
    await session.flush()
    return new_lesson


async def mark_starting_knowledge(
    session: AsyncSession,
    *,
    unit: UnitModel,
    knowledge: str,
) -> UnitModel:
    items = list(unit.starting_knowledge or [])
    folded = {value.casefold() for value in items if isinstance(value, str)}
    if knowledge.casefold() not in folded:
        items.append(knowledge)
        unit.starting_knowledge = items
        await session.flush()
    return unit


async def approve_path(session: AsyncSession, version: PathVersionModel) -> PathVersionModel:
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
    prohibited = [term.casefold() for term in (scope.must_not_introduce or []) if term.strip()]
    for lesson in lessons:
        if lesson.objective_hash != hash_path_objective(lesson.objective):
            raise PathApprovalBlocked("Path approval blocked: objective hash mismatch")
        inspected = "\n".join([lesson.objective, *(lesson.must_establish or [])]).casefold()
        if any(term in inspected for term in prohibited):
            raise PathApprovalBlocked("Path approval blocked: must-not-introduce violation")
    version.status = "approved"
    version.approved_at = _utcnow()
    version.revision += 1
    # Compatibility persistence values for columns no longer owned by the LLM.
    version.forward_verified = True
    version.reaches_destination = True
    version.prerequisite_risks = []
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


async def list_path_versions(
    session: AsyncSession,
    *,
    unit_id: str,
) -> list[PathVersionModel]:
    return list(
        await session.scalars(
            select(PathVersionModel)
            .where(PathVersionModel.unit_id == unit_id)
            .order_by(PathVersionModel.version.desc())
        )
    )


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
