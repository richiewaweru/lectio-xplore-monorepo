from __future__ import annotations

import pytest
from sqlalchemy import func, select

from core.database.models import (
    ConceptCardModel,
    ConceptModel,
    GenerationModel,
    LearningPackModel,
    LessonProvenanceModel,
    LLMCallModel,
    PackItemModel,
    PathLessonModel,
    PathVersionModel,
    ResourceCompositionModel,
    TeachingPeriodLessonModel,
    TeachingPeriodModel,
    UnitGroupModel,
    UnitModel,
    UserModel,
)
from generation.pdf_export.v3_pack_pipeline_document import build_pipeline_document_for_v3_pdf
from planning.models import ResourceComposeRequest
from planning.projections import build_composition_payload


async def _seed_projection_sources(db_session):
    user = UserModel(id="projection-owner", email="projection@example.invalid", name="Projection")
    concept = ConceptModel(
        id="concept-1", canonical_slug="plant.food", subject="Science",
        title="Plant food", created_by=user.id, status="active",
    )
    unit = UnitModel(
        id="unit-1", owner_id=user.id, title="Photosynthesis", topic="Plants",
        subject="Science", grade_level="Grade 4", destination_objective="Explain plant food.",
        starting_knowledge=[], status="approved", active_path_version_id="path-1",
    )
    version = PathVersionModel(
        id="path-1", unit_id=unit.id, version=1, revision=2, status="approved",
        source_plan_json={}, merge_critic_results=[], prerequisite_risks=[],
        forward_verified=True, reaches_destination=True,
    )
    lesson = PathLessonModel(
        id="lesson-1", path_version_id=version.id, concept_id=concept.id,
        concept_slug=concept.canonical_slug, title="How plants make food",
        objective="Explain how leaves make food.", objective_hash="objective-hash",
        external_prerequisites=[], must_establish=["Leaves make food."],
        exclusions=["Cell ultrastructure"], primary_knowledge_type="conceptual",
        knowledge_type_source="path_planner", position=0, pack_id="coordinator-1", revision=1,
    )
    support = UnitGroupModel(
        id="group-support", unit_id=unit.id, label="Support", profile="support",
        description="Guided route", toggle_profile={}, voice={}, position=1,
    )
    core = UnitGroupModel(
        id="group-core", unit_id=unit.id, label="Core", profile="core",
        description="Core route", toggle_profile={}, voice={}, position=2,
    )
    period = TeachingPeriodModel(
        id="period-1", path_version_id=version.id, title="Plant foundations", position=1,
    )
    pack = LearningPackModel(
        id="pack-1", user_id=user.id, learning_job_type="xplore_variants",
        subject="Science", topic=lesson.title, pack_plan_json="{}", status="ready",
        resource_count=2, completed_count=2,
    )
    coordinator = GenerationModel(
        id="coordinator-1", user_id=user.id, subject="Science", context="path",
        mode="v3", status="completed", requested_template_id="guided-concept-path",
        resolved_template_id="guided-concept-path", requested_preset_id="v3-studio",
        resolved_preset_id="v3-studio", pack_id=pack.id,
    )
    source_document = {
        "kind": "v3_booklet_pack", "status": "final_ready", "template_id": "guided-concept-path",
        "sections": [
            {
                "section_id": "explain", "template_id": "guided-concept-path",
                "header": {"title": "Explain", "subject": "Science", "grade_band": "primary"},
                "definition": {"term": "Photosynthesis", "plain": "Plants make food.", "formal": "Leaves use inputs to make food.", "related_terms": []},
            },
            {
                "section_id": "check", "template_id": "guided-concept-path",
                "header": {"title": "Check", "subject": "Science", "grade_band": "primary"},
            },
        ],
    }
    state = {"structural_plan": {"sections": [{"id": "explain", "role": "explain"}, {"id": "check", "role": "check"}]}}
    support_generation = GenerationModel(
        id="support-generation", user_id=user.id, subject="Science", context="Support",
        mode="v3", status="completed", document_json=source_document,
        chunked_state_json=state, requested_template_id="guided-concept-path",
        resolved_template_id="guided-concept-path", requested_preset_id="v3-studio",
        resolved_preset_id="v3-studio", pack_id=pack.id, pack_resource_label="Support",
    )
    core_generation = GenerationModel(
        id="core-generation", user_id=user.id, subject="Science", context="Core",
        mode="v3", status="completed", document_json=source_document,
        chunked_state_json=state, requested_template_id="guided-concept-path",
        resolved_template_id="guided-concept-path", requested_preset_id="v3-studio",
        resolved_preset_id="v3-studio", pack_id=pack.id, pack_resource_label="Core",
    )
    card = ConceptCardModel(
        id="pack-1:concept-1", pack_id=pack.id, slug=concept.id, title=lesson.title,
        objective=lesson.objective, prereqs=[], canonical_concept_id=concept.id,
        misconceptions=[{"id": "m1", "description": "Plants eat soil."}],
    )
    item = PackItemModel(
        id="pack-1:item-1", pack_id=pack.id, card_id=card.id,
        stem="Where is food made?", correct_key="B", diagnoses={"A": "m1"},
        options=[
            {"key": "A", "text": "Roots", "correct": False, "diagnoses": "m1"},
            {"key": "B", "text": "Leaves", "correct": True, "diagnoses": None},
        ],
    )
    provenance = LessonProvenanceModel(
        pack_id=coordinator.id, concept_id=concept.id, path_version_id=version.id,
        path_lesson_id=lesson.id, objective_hash=lesson.objective_hash,
        path_lesson_revision=lesson.revision, lesson_mode="first_exposure",
    )
    db_session.add_all([
        user, concept, unit, version, lesson, support, core, period, pack, coordinator,
        support_generation, core_generation, card, item, provenance,
        TeachingPeriodLessonModel(teaching_period_id=period.id, path_lesson_id=lesson.id, position=1),
    ])
    await db_session.flush()
    return unit, version, lesson, support, core, period, item


async def test_revision_preview_is_deterministic_and_traceable(db_session) -> None:
    unit, version, lesson, support, core, period, _item = await _seed_projection_sources(db_session)
    before_calls = await db_session.scalar(select(func.count()).select_from(LLMCallModel))
    payload = await build_composition_payload(
        db_session,
        unit=unit,
        version=version,
        request=ResourceComposeRequest(
            path_version_id=version.id, path_revision=version.revision,
            projection="revision_sheet", period_ids=[period.id],
            group_ids=[support.id, core.id],
        ),
        persist=False,
    )
    after_calls = await db_session.scalar(select(func.count()).select_from(LLMCallModel))

    assert payload["status"] == "ready"
    assert payload["lesson_ids"] == [lesson.id]
    assert len(payload["source_snapshots"]) == 2
    assert all(source["objective_hash"] == lesson.objective_hash for source in payload["source_snapshots"])
    assert payload["document"]["sections"][0]["summary"]["items"] == [{"text": "Leaves make food."}]

    render_document = build_pipeline_document_for_v3_pdf(
        generation_id="projection-preview",
        title="Revision sheet",
        subject="Science",
        template_id=payload["document"]["template_id"],
        document_json=payload["document"],
    )
    assert len(render_document.section_manifest) == len(payload["document"]["sections"])
    assert len(render_document.sections) == len(payload["document"]["sections"])
    assert before_calls == after_calls == 0


async def test_unit_exam_pools_owned_items_and_persists_exact_provenance(db_session) -> None:
    unit, version, lesson, support, _core, _period, item = await _seed_projection_sources(db_session)
    payload = await build_composition_payload(
        db_session,
        unit=unit,
        version=version,
        request=ResourceComposeRequest(
            path_version_id=version.id, path_revision=version.revision,
            projection="unit_exam", path_lesson_ids=[lesson.id],
            group_ids=[support.id], item_ids=[item.id], include_keys=True,
        ),
        persist=True,
    )

    row = await db_session.get(ResourceCompositionModel, payload["id"])
    assert row is not None
    assert row.selected_item_ids == [item.id]
    assert row.source_snapshots[0]["source_pack_id"] == "pack-1"
    assert len(row.source_snapshots[0]["source_document_hash"]) == 64
    assert row.document_json["coverage_report"] == {
        "selected_concepts": 1,
        "covered_concept_cards": 1,
        "item_count": 1,
        "card_ids": ["pack-1:concept-1"],
    }
    assert row.document_json["answer_key"]["entries"]


@pytest.mark.parametrize(
    "projection",
    ["full_lesson", "homework", "revision_sheet", "flashcards", "quiz", "answer_key", "unit_exam"],
)
async def test_every_projection_is_available_from_the_same_approved_sources(
    db_session,
    projection: str,
) -> None:
    unit, version, lesson, support, _core, _period, _item = await _seed_projection_sources(db_session)
    before_calls = await db_session.scalar(select(func.count()).select_from(LLMCallModel))

    payload = await build_composition_payload(
        db_session,
        unit=unit,
        version=version,
        request=ResourceComposeRequest(
            path_version_id=version.id,
            path_revision=version.revision,
            projection=projection,
            path_lesson_ids=[lesson.id],
            group_ids=[support.id],
            include_keys=True,
        ),
        persist=False,
    )

    assert payload["status"] == "ready"
    assert payload["can_create"] is True
    assert payload["template_version"] == "resource-projection.v1"
    assert payload["source_snapshots"][0]["path_lesson_revision"] == lesson.revision
    assert payload["document"]["projection"] == projection
    assert await db_session.scalar(select(func.count()).select_from(LLMCallModel)) == before_calls


async def test_stale_source_returns_explicit_unavailable_preview(db_session) -> None:
    unit, version, lesson, support, _core, _period, _item = await _seed_projection_sources(db_session)
    lesson.revision += 1
    await db_session.flush()

    payload = await build_composition_payload(
        db_session,
        unit=unit,
        version=version,
        request=ResourceComposeRequest(
            path_version_id=version.id,
            path_revision=version.revision,
            projection="full_lesson",
            path_lesson_ids=[lesson.id],
            group_ids=[support.id],
        ),
        persist=False,
    )

    assert payload["status"] == "projection_unavailable"
    assert payload["can_create"] is False
    assert any("stale" in reason.lower() for reason in payload["unavailable_reasons"])
