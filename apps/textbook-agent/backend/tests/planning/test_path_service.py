from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from core.database.models import (
    ConceptModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    PathVersionModel,
    UnitScopeContractModel,
    UserModel,
)
from planning.models import (
    CanonicalLessonPart,
    MergePathLessonsRequest,
    PathLessonPatch,
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
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture


FIXTURES = Path(__file__).resolve().parents[3] / "handoff" / "fixtures"


def _plan(name: str):
    return load_canonical_plan(name)


async def _unit(db_session, *, owner_id: str, fixture_name: str):
    return await create_unit(
        db_session,
        owner_id=owner_id,
        request=unit_create_from_fixture(fixture_name),
    )


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
                CanonicalLessonPart(
                    title="Part A",
                    objective="Identify part A.",
                    must_establish=["part A"],
                    knowledge_type="factual",
                ),
                CanonicalLessonPart(
                    title="Part B",
                    objective="Explain part B.",
                    must_establish=["part B"],
                    knowledge_type="conceptual",
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
            merged=CanonicalLessonPart(
                title="Merged Parts",
                objective="Relate part A to part B.",
                must_establish=["relationship between A and B"],
                knowledge_type="conceptual",
            ),
        ),
    )
    assert [await db_session.get(PathLessonModel, part.id) for part in parts] == [None, None]
    assert merged.source == "teacher_merge"
    assert await db_session.scalar(select(func.count()).select_from(PathLessonModel)) == 5
    skipped.skipped = False
    await approve_path(db_session, version)
    assert version.status == "approved"


async def test_unreachable_legacy_fixture_is_approvable_after_canonical_persist(db_session, owner) -> None:
    """Old risk-flagged fixtures map to valid DB graphs; approval no longer reads LLM risks."""
    plan = _plan("grade8-unreachable-destination-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade8-unreachable-destination-path.json",
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    assert version.prerequisite_risks == []
    assert version.reaches_destination is True
    await approve_path(db_session, version)
    assert version.status == "approved"


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


async def test_approve_validates_persisted_graph_not_external_prerequisites(db_session, owner) -> None:
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
    lessons[0].external_prerequisites = ["multiply any two fractions"]
    await db_session.flush()
    await approve_path(db_session, version)
    assert version.status == "approved"


async def test_approve_blocks_objective_hash_mismatch(db_session, owner) -> None:
    plan = _plan("grade4-photosynthesis-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade4-photosynthesis-path.json",
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None
    lesson.objective_hash = "0" * 64
    await db_session.flush()
    with pytest.raises(PathApprovalBlocked, match="objective hash"):
        await approve_path(db_session, version)


async def test_approve_blocks_do_not_cover_violation(db_session, owner) -> None:
    from v3_blueprint.planning.objective_ownership import hash_path_objective

    plan = _plan("grade4-photosynthesis-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade4-photosynthesis-path.json",
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    scope = await db_session.get(UnitScopeContractModel, unit.id)
    assert scope is not None
    prohibited = (scope.must_not_introduce or ["ATP"])[0]
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None
    lesson.objective = f"Explain {prohibited} in detail."
    lesson.objective_hash = hash_path_objective(lesson.objective)
    await db_session.flush()
    with pytest.raises(PathApprovalBlocked, match="must-not-introduce"):
        await approve_path(db_session, version)


async def test_persist_maps_scope_and_compat_fields(db_session, owner) -> None:
    plan = _plan("grade4-photosynthesis-path.json")
    unit = await _unit(
        db_session,
        owner_id=owner.id,
        fixture_name="grade4-photosynthesis-path.json",
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    scope = await db_session.get(UnitScopeContractModel, unit.id)
    assert scope is not None
    assert scope.must_establish == plan.scope.must_cover
    assert scope.must_not_introduce == plan.scope.do_not_cover
    assert scope.may_include == []
    assert scope.assumed_prerequisites == []
    assert version.merge_critic_results == []
    assert version.prerequisite_risks == []
    assert version.forward_verified is True
    assert version.reaches_destination is True
    assert version.source_plan_json["scope"]["must_cover"] == plan.scope.must_cover
    lessons = list(
        await db_session.scalars(
            select(PathLessonModel).where(PathLessonModel.path_version_id == version.id)
        )
    )
    assert all(lesson.external_prerequisites == [] for lesson in lessons)
    assert all(lesson.merge_warning is False for lesson in lessons)
    assert all(lesson.concept_slug.startswith("science.") for lesson in lessons)
