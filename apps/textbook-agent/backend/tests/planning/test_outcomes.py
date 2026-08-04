from __future__ import annotations

import pytest
from sqlalchemy import func, select

from core.database.models import (
    ConceptCardModel,
    ConceptModel,
    GenerationModel,
    LearningPackModel,
    LessonActualModel,
    MarksEntryModel,
    PackItemModel,
    PathLessonModel,
    PathVersionModel,
    ResourceCompositionModel,
    UnitGroupModel,
    UnitModel,
    UserModel,
)
from planning.models import LessonActualWriteRequest, MarksWriteRequest
from planning.outcomes import (
    OutcomeValidationError,
    StaleOutcomeError,
    actual_context_for_lessons,
    record_lesson_actual,
    record_marks,
)


async def _seed_outcomes(db_session):
    user = UserModel(id="outcome-owner", email="outcome@example.invalid", name="Outcome")
    concept = ConceptModel(
        id="concept-1", canonical_slug="plant.food", subject="Science",
        title="Plant food", created_by=user.id, status="active",
    )
    unit = UnitModel(
        id="unit-1", owner_id=user.id, title="Plants", topic="Plants", subject="Science",
        grade_level="Grade 4", destination_objective="Explain plant food.",
        starting_knowledge=[], status="approved", active_path_version_id="path-1",
    )
    version = PathVersionModel(
        id="path-1", unit_id=unit.id, version=1, revision=1, status="approved",
        source_plan_json={}, merge_critic_results=[], prerequisite_risks=[],
        forward_verified=True, reaches_destination=True,
    )
    pack = LearningPackModel(
        id="pack-1", user_id=user.id, learning_job_type="xplore_variants",
        subject="Science", topic="Plants", pack_plan_json="{}", status="ready",
        resource_count=1, completed_count=1,
    )
    coordinator = GenerationModel(
        id="generation-1", user_id=user.id, subject="Science", context="path", mode="v3",
        status="completed", requested_template_id="guided-concept-path",
        resolved_template_id="guided-concept-path", requested_preset_id="v3-studio",
        resolved_preset_id="v3-studio", pack_id=pack.id,
    )
    lesson = PathLessonModel(
        id="lesson-1", path_version_id=version.id, concept_id=concept.id,
        concept_slug=concept.canonical_slug, title="Plant food", objective="Explain plant food.",
        objective_hash="objective-hash", external_prerequisites=[],
        must_establish=["Leaves make food."], exclusions=[],
        primary_knowledge_type="conceptual", knowledge_type_source="path_planner",
        position=0, pack_id=coordinator.id, revision=2,
    )
    group = UnitGroupModel(
        id="group-core", unit_id=unit.id, label="Core", profile="core",
        description="Core group", toggle_profile={}, voice={}, position=1,
    )
    card = ConceptCardModel(
        id="card-1", pack_id=pack.id, slug=concept.id, title="Plant food",
        objective=lesson.objective, prereqs=[], canonical_concept_id=concept.id,
        misconceptions=[{"id": "soil-food", "description": "Plants absorb food from soil."}],
    )
    item = PackItemModel(
        id="item-1", pack_id=pack.id, card_id=card.id, stem="Where is food made?",
        correct_key="B", diagnoses={"A": "soil-food"},
        options=[
            {"key": "A", "text": "Roots", "correct": False, "diagnoses": "soil-food"},
            {"key": "B", "text": "Leaves", "correct": True, "diagnoses": None},
            {"key": "C", "text": "Flowers", "correct": False, "diagnoses": None},
        ],
    )
    composition = ResourceCompositionModel(
        id="composition-1", unit_id=unit.id, owner_id=user.id, path_version_id=version.id,
        path_version=1, path_revision=1, projection="quiz", status="ready",
        lesson_ids=[lesson.id], period_ids=[], group_ids=[group.id],
        selected_component_refs=[], selected_item_ids=[item.id], include_keys=False,
        template_version="resource-projection.v1", source_snapshots=[{"hash": "immutable"}],
        document_json={"sections": [{"section_id": "question"}]},
    )
    db_session.add_all([user, concept, unit, version, pack, coordinator, lesson, group, card, item, composition])
    await db_session.flush()
    return user, unit, version, lesson, group, item, composition


def _actual_request(*, revision: int, status: str = "partial") -> LessonActualWriteRequest:
    return LessonActualWriteRequest(
        path_version_id="path-1", path_revision=1, lesson_revision=2,
        actual_revision=revision, status=status, pace="slower",
        established_concepts=["Leaves make food."],
        unresolved_misconceptions=["soil-food"], anchor_used="Leaf sample",
        teacher_note="Revisit the source of plant matter.",
    )


async def test_actual_edits_append_audited_revisions_without_rewriting_artifacts(db_session) -> None:
    user, unit, version, lesson, _group, _item, composition = await _seed_outcomes(db_session)
    first = await record_lesson_actual(
        db_session, unit=unit, version=version, lesson=lesson,
        request=_actual_request(revision=0), user_id=user.id,
    )
    second = await record_lesson_actual(
        db_session, unit=unit, version=version, lesson=lesson,
        request=_actual_request(revision=1, status="established"), user_id=user.id,
    )

    assert (first.revision, second.revision) == (1, 2)
    assert second.supersedes_actual_id == first.id
    assert await db_session.scalar(select(func.count()).select_from(LessonActualModel)) == 2
    context = await actual_context_for_lessons(db_session, path_lesson_ids=[lesson.id])
    assert context[0]["status"] == "established"
    assert context[0]["advisory"] is True
    await db_session.refresh(composition)
    assert composition.source_snapshots == [{"hash": "immutable"}]
    assert composition.document_json == {"sections": [{"section_id": "question"}]}

    with pytest.raises(StaleOutcomeError, match="expected 2"):
        await record_lesson_actual(
            db_session, unit=unit, version=version, lesson=lesson,
            request=_actual_request(revision=1), user_id=user.id,
        )


async def test_marks_reconcile_owned_options_and_keep_null_distractors_unclaimed(db_session) -> None:
    user, unit, version, lesson, group, item, _composition = await _seed_outcomes(db_session)
    summary = await record_marks(
        db_session, unit=unit, version=version, lesson=lesson, user_id=user.id,
        request=MarksWriteRequest(
            path_version_id=version.id, path_revision=version.revision,
            lesson_revision=lesson.revision, marks_revision=0, group_id=group.id,
            items=[{"item_id": item.id, "option_counts": {"A": 9, "B": 2, "C": 1}}],
        ),
    )

    assert summary["revision"] == 1
    assert summary["items"][0]["total_count"] == 12
    assert summary["misconceptions"] == [{
        "misconception_id": "soil-food",
        "label": "Plants absorb food from soil.",
        "count": 9,
    }]
    assert summary["unclaimed_distractor_count"] == 1
    assert summary["advisory"] is True
    assert "do not diagnose individual learners" in summary["advisory_note"]
    assert await db_session.scalar(select(func.count()).select_from(MarksEntryModel)) == 3

    revised = await record_marks(
        db_session, unit=unit, version=version, lesson=lesson, user_id=user.id,
        request=MarksWriteRequest(
            path_version_id=version.id, path_revision=version.revision,
            lesson_revision=lesson.revision, marks_revision=1, group_id=group.id,
            items=[{"item_id": item.id, "option_counts": {"A": 4, "B": 7, "C": 1}}],
        ),
    )
    assert revised["revision"] == 2
    assert revised["items"][0]["total_count"] == 12
    assert await db_session.scalar(select(func.count()).select_from(MarksEntryModel)) == 6

    with pytest.raises(OutcomeValidationError, match="every answer option"):
        await record_marks(
            db_session, unit=unit, version=version, lesson=lesson, user_id=user.id,
            request=MarksWriteRequest(
                path_version_id=version.id, path_revision=version.revision,
                lesson_revision=lesson.revision, marks_revision=2, group_id=group.id,
                items=[{"item_id": item.id, "option_counts": {"A": 1, "B": 1}}],
            ),
        )


async def test_marks_reject_cross_pack_item_ownership(db_session) -> None:
    user, unit, version, lesson, group, _item, _composition = await _seed_outcomes(db_session)
    foreign_card = ConceptCardModel(
        id="foreign-card", pack_id="foreign-pack", slug="foreign", title="Foreign",
        objective="Foreign", prereqs=[], misconceptions=[],
    )
    foreign_item = PackItemModel(
        id="foreign-item", pack_id="foreign-pack", card_id=foreign_card.id,
        stem="Foreign?", options=[{"key": "A", "text": "Yes", "correct": True}],
        correct_key="A", diagnoses={},
    )
    db_session.add_all([foreign_card, foreign_item])
    await db_session.flush()
    with pytest.raises(OutcomeValidationError, match="owned by this lesson pack"):
        await record_marks(
            db_session, unit=unit, version=version, lesson=lesson, user_id=user.id,
            request=MarksWriteRequest(
                path_version_id=version.id, path_revision=version.revision,
                lesson_revision=lesson.revision, marks_revision=0, group_id=group.id,
                items=[{"item_id": foreign_item.id, "option_counts": {"A": 1}}],
            ),
        )
