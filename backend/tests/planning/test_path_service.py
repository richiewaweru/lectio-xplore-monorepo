from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from core.database.models import (
    ConceptModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    PathVersionModel,
    UserModel,
)
from planning.models import (
    ConceptCandidate,
    LessonPart,
    MergePathLessonsRequest,
    PathLessonPatch,
    PathPlan,
    ReorderPathLessonsRequest,
    SplitPathLessonRequest,
    UnitCreate,
)
from planning.service import (
    approve_path,
    clone_path_version,
    create_unit,
    merge_lessons,
    patch_lesson,
    persist_path_plan,
    reorder_lessons,
    skip_lesson,
    split_lesson,
)
from planning.validation import PathApprovalBlocked


FIXTURES = Path(__file__).resolve().parents[3] / "handoff" / "fixtures"


def _plan(name: str) -> PathPlan:
    return PathPlan.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


async def _unit(db_session, *, owner_id: str, fixture_name: str):
    plan = _plan(fixture_name)
    request = UnitCreate(
        title=plan.unit or "Unit",
        topic=plan.unit or "Topic",
        subject=plan.subject or "Science",
        grade_level=plan.grade_level or "Grade 4",
        destination_objective=plan.destination_objective or "Destination",
        starting_knowledge=plan.starting_knowledge,
    )
    return await create_unit(db_session, owner_id=owner_id, request=request)


@pytest.fixture
async def owner(db_session):
    user = UserModel(id="path-owner", email="path-owner@example.invalid", name="Path Owner")
    db_session.add(user)
    await db_session.flush()
    return user


async def test_persist_resolves_concepts_and_uuid_prerequisites(db_session, owner) -> None:
    plan = _plan("grade4-photosynthesis-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade4-photosynthesis-path.json",
    )

    version = await persist_path_plan(db_session, unit=unit, plan=plan)

    lessons = list(
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    assert len(lessons) == 5
    assert all(lesson.concept_id for lesson in lessons)
    assert all(len(lesson.objective_hash) == 64 for lesson in lessons)
    assert await db_session.scalar(select(func.count()).select_from(ConceptModel)) == 5
    links = list(await db_session.scalars(select(PathLessonPrerequisiteModel)))
    by_id = {lesson.id: lesson.position for lesson in lessons}
    assert links
    assert all(by_id[link.prerequisite_lesson_id] < by_id[link.path_lesson_id] for link in links)


async def test_replan_retains_concept_ids_and_teacher_edits(db_session, owner) -> None:
    plan = _plan("grade4-photosynthesis-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade4-photosynthesis-path.json",
    )
    first = await persist_path_plan(db_session, unit=unit, plan=plan)
    original = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == first.id)
        .order_by(PathLessonModel.position)
    )
    assert original is not None
    original_concept_id = original.concept_id
    await patch_lesson(
        db_session,
        lesson=original,
        request=PathLessonPatch(objective="Identify the three inputs a plant needs to make food."),
    )

    second = await persist_path_plan(db_session, unit=unit, plan=plan, prior_version=first)
    replanned = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == second.id)
        .order_by(PathLessonModel.position)
    )
    assert replanned is not None
    assert replanned.concept_id == original_concept_id
    assert replanned.objective == original.objective
    assert replanned.teacher_edited is True


async def test_skip_reorder_split_and_merge_are_explicit_state(db_session, owner) -> None:
    plan = _plan("grade4-photosynthesis-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade4-photosynthesis-path.json",
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    lessons = list(
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )

    skipped = await skip_lesson(db_session, lessons[0])
    assert skipped.skipped is True
    with pytest.raises(ValueError, match="forward prerequisite"):
        await reorder_lessons(
            db_session,
            version_id=version.id,
            request=ReorderPathLessonsRequest(
                lesson_ids=[lesson.id for lesson in reversed(lessons)]
            ),
        )
    reordered = await reorder_lessons(
        db_session,
        version_id=version.id,
        request=ReorderPathLessonsRequest(lesson_ids=[lesson.id for lesson in lessons]),
    )
    assert [lesson.position for lesson in reordered] == list(range(5))

    parts = await split_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lessons[1],
        request=SplitPathLessonRequest(
            parts=[
                LessonPart(
                    concept_candidate=ConceptCandidate(slug="split.part-a", title="Part A"),
                    objective="Identify part A.",
                    must_establish=["part A"],
                    primary_knowledge_type="factual",
                ),
                LessonPart(
                    concept_candidate=ConceptCandidate(slug="split.part-b", title="Part B"),
                    objective="Explain part B.",
                    must_establish=["part B"],
                    primary_knowledge_type="conceptual",
                ),
            ]
        ),
    )
    assert [part.source for part in parts] == ["teacher_split", "teacher_split"]
    assert await db_session.get(PathLessonModel, lessons[1].id) is None

    merged = await merge_lessons(
        db_session,
        unit=unit,
        version=version,
        request=MergePathLessonsRequest(
            lesson_ids=[parts[0].id, parts[1].id],
            merged=LessonPart(
                concept_candidate=ConceptCandidate(slug="split.merged", title="Merged"),
                objective="Relate part A to part B.",
                must_establish=["relationship between A and B"],
                primary_knowledge_type="conceptual",
            ),
        ),
    )
    assert [await db_session.get(PathLessonModel, part.id) for part in parts] == [None, None]
    assert merged.source == "teacher_merge"
    assert await db_session.scalar(select(func.count()).select_from(PathLessonModel)) == 5
    skipped.skipped = False
    await approve_path(db_session, version)
    assert version.status == "approved"


async def test_unreachable_path_cannot_be_approved(db_session, owner) -> None:
    plan = _plan("grade8-unreachable-destination-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade8-unreachable-destination-path.json",
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)

    with pytest.raises(PathApprovalBlocked, match="prerequisite"):
        await approve_path(db_session, version)

    assert version.status == "draft"


async def test_structural_checkpoint_preserves_identity_and_prerequisites(db_session, owner) -> None:
    plan = _plan("grade4-photosynthesis-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade4-photosynthesis-path.json",
    )
    first = await persist_path_plan(db_session, unit=unit, plan=plan)
    source_lessons = list(
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == first.id)
            .order_by(PathLessonModel.position)
        )
    )
    source_lessons[0].pack_id = "prepared-pack"

    second, mapping = await clone_path_version(
        db_session,
        unit=unit,
        source=first,
        supersede_active=first,
        generated_by="teacher_reorder",
    )

    cloned = list(
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == second.id)
            .order_by(PathLessonModel.position)
        )
    )
    links = list(
        await db_session.scalars(
            select(PathLessonPrerequisiteModel).where(
                PathLessonPrerequisiteModel.path_lesson_id.in_([lesson.id for lesson in cloned])
            )
        )
    )
    positions = {lesson.id: lesson.position for lesson in cloned}

    assert first.status == "superseded"
    assert second.status == "draft"
    assert unit.active_path_version_id == second.id
    assert [lesson.concept_id for lesson in cloned] == [lesson.concept_id for lesson in source_lessons]
    assert [lesson.objective for lesson in cloned] == [lesson.objective for lesson in source_lessons]
    assert all(lesson.pack_id is None for lesson in cloned)
    assert set(mapping) == {lesson.id for lesson in source_lessons}
    assert all(positions[link.prerequisite_lesson_id] < positions[link.path_lesson_id] for link in links)
    assert await db_session.scalar(select(func.count()).select_from(PathVersionModel)) == 2
