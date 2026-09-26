from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import update

from curriculum.lesson_sourcebook import LessonSourcebook, SourcebookEntry
from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson.runtime import TeachingPlanSource
from document.shared_lesson.semantic_inputs import (
    SemanticInputError,
    VerifiedSourcebookInput,
    admit_shared_task_work_item,
    admit_sourcebook_work_item,
    load_verified_sourcebook_input,
    load_verified_semantic_inputs,
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
from infra.generation_runtime import (
    SourceIdentity,
    WorkItemAdmission,
    WorkItemReplacement,
    replace_work_item,
)


def _source(
    *, sourcebook_refs: list[str] | None = None, include_shared_ref_block: bool = False
) -> TeachingPlanSource:
    block = TeachingPlanBlock(
        id="block-explain",
        position=0,
        intent="Explain the idea",
        brief="Explain the idea clearly.",
        evidence="Learner can explain the idea.",
        sourcebook_needs=["definition"],
        sourcebook_refs=list(sourcebook_refs or ["definition-main"]),
        task_mode="formative",
        learner_action=LearnerActionBrief(
            action="select-one",
            target="the idea",
            purpose="Check understanding",
            expected_evidence="Learner selects the correct explanation.",
            difficulty="guided",
        ),
    )
    blocks = [block]
    if include_shared_ref_block:
        blocks.append(
            TeachingPlanBlock(
                id="block-reuse",
                position=1,
                intent="Reuse the approved idea",
                brief="Reuse the approved definition.",
                evidence="Learner sees the same approved definition.",
                sourcebook_refs=list(sourcebook_refs or ["definition-main"]),
            )
        )
    plan = TeachingPlan(
        arc="Introduce one idea and check understanding.",
        contract_version=2,
        learner_title="A lesson about one idea",
        starting_state=["Learner is ready."],
        target_state=["Learner can explain the idea."],
        teaching_plan_id="semantic-input-plan",
        revision=3,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                display_title="Explain the idea",
                specific_purpose="Build the core idea.",
                entry_state=["Learner is ready."],
                must_establish=["The idea is clear."],
                avoid_repeating=[],
                bridge_from_previous=None,
                exit_state=["Learner can explain the idea."],
                blocks=blocks,
            )
        ],
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
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
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=plan.teaching_plan_id,
        revision=plan.revision,
        content_hash=digest,
    )


def _sourcebook(
    source: TeachingPlanSource,
    *,
    entry_id: str = "definition-main",
    duplicate_entry: bool = False,
) -> LessonSourcebook:
    entry = SourcebookEntry(
        id=entry_id,
        type="definition",
        purpose="Define the idea.",
        content={"text": "A clear definition."},
        provenance_refs=["block-explain"],
    )
    return LessonSourcebook(
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
        entries=[entry, entry.model_copy()] if duplicate_entry else [entry],
    )


def _tasks(source: TeachingPlanSource) -> list[SharedTaskSpec]:
    return [
        SharedTaskSpec(
            id="task-block-explain",
            teaching_plan_id=source.id,
            teaching_plan_revision=source.revision,
            teaching_plan_hash=source.content_hash,
            teaching_block_id="block-explain",
            mode="formative",
            action="select-one",
            purpose="Check understanding",
            prompt="Which explanation is correct?",
            difficulty="guided",
            sourcebook_refs=["definition-main"],
            expected_evidence="Learner selects the correct explanation.",
            response={
                "type": "single_choice",
                "options": [
                    {"id": "correct", "text": "The correct explanation."},
                    {"id": "wrong", "text": "A wrong explanation."},
                ],
                "answer_lines": 1,
            },
            evaluation={"type": "choice_keys", "correct": ["correct"]},
        )
    ]


async def _seed_run(session, source: TeachingPlanSource, *, suffix: str = "main"):
    owner = f"semantic-owner-{suffix}"
    concept = ConceptModel(
        id=f"semantic-concept-{suffix}",
        canonical_slug=f"semantic.{suffix}",
        subject="Science",
        title="Semantic inputs",
        created_by=owner,
    )
    unit = UnitModel(
        id=f"semantic-unit-{suffix}",
        owner_id=owner,
        title="Semantic inputs",
        topic="Shared semantic inputs",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Verify semantic input trust boundary.",
    )
    path = PathVersionModel(
        id=f"semantic-path-{suffix}", unit_id=unit.id, version=1, source_plan_json={}
    )
    lesson = PathLessonModel(
        id=f"semantic-lesson-{suffix}",
        path_version_id=path.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="Semantic inputs",
        objective="Verify semantic input trust boundary.",
        objective_hash="semantic-objective",
        primary_knowledge_type="conceptual",
        position=0,
    )
    build = GenerationBuildModel(
        id=f"semantic-build-{suffix}", path_lesson_id=lesson.id, owner_user_id=owner
    )
    run = GenerationRunModel(
        id=f"semantic-run-{suffix}",
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
        request_key=f"semantic-request-{suffix}",
    )
    session.add_all(
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
    await session.commit()
    return owner, run.id


async def _ready(session, item: GenerationWorkItemModel, output: object) -> None:
    await session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == item.id)
        .values(status="ready", output_json=output, output_hash=content_hash(output))
    )
    await session.commit()


@pytest.mark.asyncio
async def test_semantic_admission_is_idempotent_and_requires_sourcebook_first(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source)
    with pytest.raises(SemanticInputError, match="sourcebook"):
        await admit_shared_task_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            sourcebook_output_hash="a" * 64,
        )
    first = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    second = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    assert first.created is True
    assert second.created is False
    await _ready(db_session, first.record, _sourcebook(source).model_dump(mode="json"))
    sourcebook_hash = content_hash(first.record.output_json)
    task_first = await admit_shared_task_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        sourcebook_output_hash=sourcebook_hash,
    )
    task_second = await admit_shared_task_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        sourcebook_output_hash=sourcebook_hash,
    )
    assert task_first.created is True
    assert task_second.created is False


@pytest.mark.asyncio
async def test_sourcebook_loader_accepts_ready_leaf_before_tasks_exist(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source, suffix="sourcebook-only")
    sourcebook = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    payload = _sourcebook(source).model_dump(mode="json")
    await _ready(db_session, sourcebook.record, payload)

    verified = await load_verified_sourcebook_input(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )

    assert isinstance(verified, VerifiedSourcebookInput)
    assert verified.sourcebook_output_hash == content_hash(payload)
    assert verified.work_item_id == sourcebook.record.id
    with pytest.raises(ValidationError):
        verified.work_item_id = "forged"


@pytest.mark.asyncio
async def test_sourcebook_loader_rejects_missing_leaf_and_owner_mismatch(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source, suffix="sourcebook-missing")
    with pytest.raises(SemanticInputError, match="sourcebook"):
        await load_verified_sourcebook_input(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )
    with pytest.raises(SemanticInputError, match="unavailable to this owner"):
        await load_verified_sourcebook_input(
            db_session, run_id=run_id, owner_user_id="other-owner", source=source
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "match"),
    [
        ("duplicate", "entry IDs must be unique"),
        ("stale", "bound to a different approved Teaching Plan"),
        ("forged", "output hash does not match output"),
        ("input", "input identity is stale"),
        ("definition", "definition identity is stale"),
        ("composition", "invalid composition identity"),
    ],
)
async def test_sourcebook_loader_rejects_invalid_ready_output(db_session, kind, match) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source, suffix=f"sourcebook-{kind}")
    sourcebook = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    payload = _sourcebook(source, duplicate_entry=kind == "duplicate")
    if kind == "stale":
        payload = payload.model_copy(update={"teaching_plan_hash": "f" * 64})
    payload_json = payload.model_dump(mode="json")
    await _ready(db_session, sourcebook.record, payload_json)
    if kind == "forged":
        await db_session.execute(
            update(GenerationWorkItemModel)
            .where(GenerationWorkItemModel.id == sourcebook.record.id)
            .values(output_hash="f" * 64)
        )
        await db_session.commit()
    if kind == "input":
        await db_session.execute(
            update(GenerationWorkItemModel)
            .where(GenerationWorkItemModel.id == sourcebook.record.id)
            .values(input_hash="f" * 64)
        )
        await db_session.commit()
    if kind == "definition":
        await db_session.execute(
            update(GenerationWorkItemModel)
            .where(GenerationWorkItemModel.id == sourcebook.record.id)
            .values(definition_hash="f" * 64)
        )
        await db_session.commit()
    if kind == "composition":
        await db_session.execute(
            update(GenerationWorkItemModel)
            .where(GenerationWorkItemModel.id == sourcebook.record.id)
            .values(composition_identity="forged-composition")
        )
        await db_session.commit()

    with pytest.raises(SemanticInputError, match=match):
        await load_verified_sourcebook_input(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )


@pytest.mark.asyncio
async def test_task_admission_revalidates_sourcebook_contract(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source, suffix="task-sourcebook-contract")
    sourcebook = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    stale_payload = _sourcebook(source).model_copy(update={"teaching_plan_hash": "f" * 64})
    payload = stale_payload.model_dump(mode="json")
    await _ready(db_session, sourcebook.record, payload)

    with pytest.raises(SemanticInputError, match="bound to a different approved Teaching Plan"):
        await admit_shared_task_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            sourcebook_output_hash=content_hash(payload),
        )


@pytest.mark.asyncio
async def test_reload_validates_exact_sourcebook_and_task_lineage(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source)
    sourcebook_admission = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    sourcebook_payload = _sourcebook(source).model_dump(mode="json")
    await _ready(db_session, sourcebook_admission.record, sourcebook_payload)
    sourcebook_hash = content_hash(sourcebook_payload)
    task_admission = await admit_shared_task_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        sourcebook_output_hash=sourcebook_hash,
    )
    task_payload = [task.model_dump(mode="json") for task in _tasks(source)]
    await session_update_task(db_session, task_admission.record, task_payload, sourcebook_hash)

    verified = await load_verified_semantic_inputs(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    assert verified.sourcebook_output_hash == sourcebook_hash
    assert tuple(task.id for task in verified.tasks) == ("task-block-explain",)
    assert verified.work_item_ids == {
        "sourcebook": sourcebook_admission.record.id,
        "shared_tasks": task_admission.record.id,
    }
    with pytest.raises(TypeError):
        verified.work_item_ids["sourcebook"] = "forged"


async def session_update_task(session, item, payload, sourcebook_hash: str) -> None:
    await session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == item.id)
        .values(
            status="ready",
            output_json=payload,
            output_hash=content_hash(payload),
            composition_identity=sourcebook_hash,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_reload_rejects_sourcebook_ref_mismatch_and_source_naming_adapter(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source)
    sourcebook = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    wrong = _sourcebook(source, entry_id="source-1").model_dump(mode="json")
    await _ready(db_session, sourcebook.record, wrong)
    with pytest.raises(SemanticInputError, match="match approved refs"):
        await load_verified_semantic_inputs(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )


@pytest.mark.asyncio
async def test_reload_uses_active_sourcebook_replacement_and_preserves_task_sibling(
    db_session,
) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source)
    sourcebook = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    sourcebook_payload = _sourcebook(source).model_dump(mode="json")
    await _ready(db_session, sourcebook.record, sourcebook_payload)
    dependency = content_hash(sourcebook_payload)
    task = await admit_shared_task_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        sourcebook_output_hash=dependency,
    )
    task_payload = [item.model_dump(mode="json") for item in _tasks(source)]
    await session_update_task(db_session, task.record, task_payload, dependency)

    replacement = await replace_work_item(
        db_session,
        WorkItemReplacement(
            predecessor_work_item_id=sourcebook.record.id,
            owner_user_id=owner,
            source=SourceIdentity(
                source_artifact_type="teaching_plan",
                source_artifact_id=source.id,
                source_revision=source.revision,
                source_hash=source.content_hash,
            ),
            replacement=WorkItemAdmission(
                run_id=run_id,
                item_key="sourcebook:repair-1",
                stage="sourcebook_generation",
                input_hash=sourcebook.record.input_hash,
                definition_hash=sourcebook.record.definition_hash,
                composition_identity="sourcebook-repair-1",
            ),
        ),
    )
    await db_session.commit()
    await _ready(db_session, replacement, sourcebook_payload)
    sourcebook_verified = await load_verified_sourcebook_input(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    assert sourcebook_verified.work_item_id == replacement.id
    verified = await load_verified_semantic_inputs(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    assert verified.work_item_ids["sourcebook"] == replacement.id
    assert verified.work_item_ids["shared_tasks"] == task.record.id


@pytest.mark.asyncio
async def test_reload_rejects_tampered_output_stale_dependency_and_missing_leaf(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source)
    sourcebook = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    payload = _sourcebook(source).model_dump(mode="json")
    await _ready(db_session, sourcebook.record, payload)
    dependency = content_hash(payload)
    tasks = await admit_shared_task_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        sourcebook_output_hash=dependency,
    )
    task_payload = [task.model_dump(mode="json") for task in _tasks(source)]
    await session_update_task(db_session, tasks.record, task_payload, dependency)

    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == tasks.record.id)
        .values(output_json=task_payload, output_hash="f" * 64)
    )
    await db_session.commit()
    with pytest.raises(SemanticInputError, match="hash"):
        await load_verified_semantic_inputs(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )

    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == tasks.record.id)
        .values(output_hash=content_hash(task_payload), composition_identity="e" * 64)
    )
    await db_session.commit()
    with pytest.raises(SemanticInputError, match="stale sourcebook"):
        await load_verified_semantic_inputs(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )

    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == sourcebook.record.id)
        .values(status="failed_recoverable", output_json=None, output_hash=None)
    )
    await db_session.commit()
    with pytest.raises(SemanticInputError, match="not ready"):
        await load_verified_semantic_inputs(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )


@pytest.mark.asyncio
async def test_admission_rejects_owner_source_and_hash_conflicts(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source)
    with pytest.raises(SemanticInputError, match="unavailable"):
        await admit_sourcebook_work_item(
            db_session, run_id=run_id, owner_user_id="other-owner", source=source
        )
    with pytest.raises(SemanticInputError, match="digest"):
        await admit_shared_task_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            sourcebook_output_hash="not-a-hash",
        )
    changed = source.model_copy(update={"content_hash": "a" * 64})
    with pytest.raises(SemanticInputError, match="source"):
        await admit_sourcebook_work_item(
            db_session, run_id=run_id, owner_user_id=owner, source=changed
        )


@pytest.mark.asyncio
async def test_reload_rejects_duplicate_sourcebook_entry_ids(db_session) -> None:
    source = _source()
    owner, run_id = await _seed_run(db_session, source, suffix="duplicate-entry")
    sourcebook = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    payload = _sourcebook(source, duplicate_entry=True).model_dump(mode="json")
    await _ready(db_session, sourcebook.record, payload)
    with pytest.raises(SemanticInputError, match="entry IDs must be unique"):
        await load_verified_semantic_inputs(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )


@pytest.mark.asyncio
async def test_shared_sourcebook_ref_is_admitted_once_for_multiple_blocks(db_session) -> None:
    source = _source(include_shared_ref_block=True)
    owner, run_id = await _seed_run(db_session, source, suffix="shared-ref")
    sourcebook = await admit_sourcebook_work_item(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    payload = _sourcebook(source).model_dump(mode="json")
    await _ready(db_session, sourcebook.record, payload)
    dependency = content_hash(payload)
    task = await admit_shared_task_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        sourcebook_output_hash=dependency,
    )
    task_payload = [item.model_dump(mode="json") for item in _tasks(source)]
    await session_update_task(db_session, task.record, task_payload, dependency)
    verified = await load_verified_semantic_inputs(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    assert [entry.id for entry in verified.sourcebook.entries] == ["definition-main"]
