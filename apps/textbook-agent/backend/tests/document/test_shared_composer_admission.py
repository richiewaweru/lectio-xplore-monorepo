from __future__ import annotations

import pytest
from sqlalchemy import select, update

from curriculum.lesson_sourcebook.models import LessonSourcebook, SourcebookEntry
from curriculum.shared_task_authoring import ApprovedItemSnapshot
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from curriculum.teaching_plan.revisions import (
    TeachingRevisionRecord,
)
from curriculum.teaching_plan.revisions import (
    approved_item_snapshot_hash as revision_snapshot_hash,
)
from document.shared_lesson.composer_admission import (
    ComposerAdmissionError,
    admit_composer_work_items,
)
from document.shared_lesson.runtime import TeachingPlanSource
from document.shared_lesson.semantic_inputs import (
    admit_shared_task_work_item,
    admit_sourcebook_work_item,
)
from infra.database.models import (
    ConceptModel,
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import WorkItemConflict


def _source() -> tuple[TeachingPlanSource, LessonSourcebook]:
    sections = tuple(
        TeachingPlanSection(
            slot_id=slot_id,
            specific_purpose=f"Teach {slot_id}",
            display_title=title,
            entry_state=[f"Learner enters {slot_id}"],
            must_establish=[f"Learner understands {slot_id}"],
            avoid_repeating=[],
            bridge_from_previous=None if index == 0 else "Connect the idea",
            exit_state=[f"Learner exits {slot_id}"],
            blocks=[
                TeachingPlanBlock(
                    id=f"block-{slot_id}",
                    position=0,
                    intent=f"Explain {slot_id}",
                    brief=f"Explain {slot_id} clearly.",
                    evidence=f"Learner can explain {slot_id}.",
                    sourcebook_refs=[f"fact-{index}"],
                )
            ],
        )
        for index, (slot_id, title) in enumerate(
            (("orient", "Start with the idea"), ("explain", "Explain the idea"))
        )
    )
    plan = TeachingPlan(
        arc="Introduce and explain one idea.",
        contract_version=2,
        learner_title="A lesson about one idea",
        starting_state=["Learner is ready to learn."],
        target_state=["Learner can explain the idea."],
        teaching_plan_id="composer-admission-plan",
        revision=4,
        sections=sections,
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
    snapshot = ApprovedItemSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=plan.revision,
        teaching_plan_hash=digest,
        items={},
    )
    record = TeachingRevisionRecord(
        teaching_plan_id=plan.teaching_plan_id,
        revision=plan.revision,
        status="approved",
        preparation_hash="p" * 64,
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-25T00:00:00Z",
        approved_at="2026-09-25T00:00:00Z",
        reviewed_by="teacher-1",
        approval_hash_binding="submitted",
        approved_item_snapshot=snapshot.model_dump(mode="json"),
        approved_item_snapshot_hash=revision_snapshot_hash(snapshot.model_dump(mode="json")),
    )
    source = TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=plan.teaching_plan_id,
        revision=plan.revision,
        content_hash=digest,
    )
    sourcebook = LessonSourcebook(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=plan.revision,
        teaching_plan_hash=digest,
        entries=[
            SourcebookEntry(
                id=f"fact-{index}",
                type="definition",
                purpose="Explain the approved idea.",
                content={"text": f"Approved fact {index}"},
                provenance_refs=[f"source-{index}"],
            )
            for index in range(2)
        ],
    )
    return source, sourcebook


async def _seed_run(db_session) -> tuple[str, str, TeachingPlanSource, LessonSourcebook]:
    source, sourcebook = _source()
    owner = "composer-admission-owner"
    lesson_id = "composer-admission-lesson"
    concept = ConceptModel(
        id="composer-admission-concept",
        canonical_slug="composer-admission",
        subject="Science",
        title="Composer admission fixture",
        created_by=owner,
    )
    unit = UnitModel(
        id="composer-admission-unit",
        owner_id=owner,
        title="Composer admission fixture",
        topic="Shared document",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Verify composer admission.",
    )
    path = PathVersionModel(
        id="composer-admission-path", unit_id=unit.id, version=1, source_plan_json={}
    )
    lesson = PathLessonModel(
        id=lesson_id,
        path_version_id=path.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="Composer admission fixture",
        objective="Verify composer admission.",
        objective_hash="composer-admission-objective",
        primary_knowledge_type="conceptual",
        position=0,
    )
    build = GenerationBuildModel(
        id="composer-admission-build", path_lesson_id=lesson_id, owner_user_id=owner
    )
    run = GenerationRunModel(
        id="composer-admission-run",
        build_id=build.id,
        run_type="shared_document",
        owner_user_id=owner,
        status="running",
        stage="sourcebook_generation",
        attempt=1,
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash=source.content_hash,
        request_key="composer-admission-request",
    )
    db_session.add_all(
        [
            UserModel(id=owner, email=f"{owner}@example.invalid"),
            concept,
            unit,
            path,
            lesson,
            build,
            run,
        ]
    )
    await db_session.flush()

    sourcebook_admission = await admit_sourcebook_work_item(
        db_session,
        run_id=run.id,
        owner_user_id=owner,
        source=source,
    )
    sourcebook_item = sourcebook_admission.record
    sourcebook_payload = sourcebook.model_dump(mode="json")
    sourcebook_item.status = "ready"
    sourcebook_item.output_json = sourcebook_payload
    sourcebook_item.output_hash = content_hash(sourcebook_payload)
    await db_session.flush()
    task_admission = await admit_shared_task_work_item(
        db_session,
        run_id=run.id,
        owner_user_id=owner,
        source=source,
        sourcebook_output_hash=sourcebook_item.output_hash,
    )
    task_item = task_admission.record
    task_item.status = "ready"
    task_item.output_json = []
    task_item.output_hash = content_hash([])
    await db_session.commit()
    return owner, run.id, source, sourcebook


async def _verifier(_session, requested):
    return requested


@pytest.mark.asyncio
async def test_admission_derives_section_inputs_and_uses_existing_run(db_session) -> None:
    owner, run_id, source, _sourcebook = await _seed_run(db_session)

    admitted = await admit_composer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )

    assert tuple(item.section.slot_id for item in admitted) == ("orient", "explain")
    assert tuple(item.sources[0].id for item in admitted) == ("fact-0", "fact-1")
    assert all(item.tasks == () for item in admitted)
    rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.item_key.like("compose:%"),
                )
            )
        ).all()
    )
    assert {row.id for row in rows} == {item.work_item_id for item in admitted}
    assert all(row.status == "queued" for row in rows)


@pytest.mark.asyncio
async def test_admission_is_idempotent_and_changed_identity_conflicts(db_session) -> None:
    owner, run_id, source, _sourcebook = await _seed_run(db_session)
    first = await admit_composer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    second = await admit_composer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    assert tuple(item.work_item_id for item in second) == tuple(item.work_item_id for item in first)

    first_item = first[0]
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == first_item.work_item_id)
        .values(input_hash="0" * 64)
    )
    await db_session.commit()
    with pytest.raises(WorkItemConflict):
        await admit_composer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            source_verifier=_verifier,
        )


@pytest.mark.asyncio
async def test_admission_rejects_wrong_owner_source_and_tampered_semantic_leaf(db_session) -> None:
    owner, run_id, source, _sourcebook = await _seed_run(db_session)

    with pytest.raises(ComposerAdmissionError, match="durable"):
        await admit_composer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id="another-owner",
            source=source,
            source_verifier=_verifier,
        )

    async def wrong_source_verifier(_session, requested):
        return requested.model_copy(update={"source_hash": "f" * 64})

    with pytest.raises(ComposerAdmissionError, match="exact admitted identity"):
        await admit_composer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            source_verifier=wrong_source_verifier,
        )

    sourcebook_item = await db_session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.run_id == run_id,
            GenerationWorkItemModel.item_key == "sourcebook",
        )
    )
    assert sourcebook_item is not None
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == sourcebook_item.id)
        .values(output_json={"forged": True})
    )
    await db_session.commit()
    with pytest.raises(ComposerAdmissionError, match="durable"):
        await admit_composer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            source_verifier=_verifier,
        )
