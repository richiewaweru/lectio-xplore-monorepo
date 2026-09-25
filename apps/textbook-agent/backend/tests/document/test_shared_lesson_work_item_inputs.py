from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import update

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson.composer import CompositionChoice, validate_and_build_composition
from document.shared_lesson.models import ParagraphDisplay, ParagraphNode
from document.shared_lesson.runtime import TeachingPlanSource, _stable_hash
from document.shared_lesson.work_item_inputs import (
    SharedLessonInputError,
    _assert_active_chain,
    _parse_output,
    load_verified_shared_lesson_inputs,
)
from document.shared_lesson.writer import SectionWriteResult
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


def _source(*, unicode_slot: bool = False) -> TeachingPlanSource:
    second_slot = "explain-é" if unicode_slot else "explain"
    sections = tuple(
        TeachingPlanSection(
            slot_id=slot,
            specific_purpose=f"Teach {slot}",
            display_title=title,
            entry_state=[f"Learner enters {slot}"],
            must_establish=[f"Learner understands {slot}"],
            avoid_repeating=[],
            bridge_from_previous=None if slot == "orient" else "Connect the idea",
            exit_state=[f"Learner exits {slot}"],
            blocks=[
                TeachingPlanBlock(
                    id=f"block-{slot}",
                    position=0,
                    intent=f"Explain {slot}",
                    brief=f"Explain {slot} clearly.",
                    evidence=f"Learner can explain {slot}.",
                )
            ],
        )
        for slot, title in (("orient", "Start with the idea"), (second_slot, "Explain the idea"))
    )
    plan = TeachingPlan(
        arc="Introduce and explain one idea.",
        contract_version=2,
        learner_title="A lesson about one idea",
        starting_state=["Learner is ready to learn."],
        target_state=["Learner can explain the idea."],
        teaching_plan_id="inputs-plan",
        revision=4,
        sections=sections,
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


def _section_outputs(source: TeachingPlanSource):
    outputs = []
    for section in source.plan.sections:
        composition = validate_and_build_composition(
            section=section,
            choices=(
                CompositionChoice(
                    teaching_block_id=section.blocks[0].id,
                    kind="paragraph",
                    semantic_role="explanation",
                ),
            ),
            tasks=(),
        )
        item = composition.items[0]
        result = SectionWriteResult(
            section_slot_id=section.slot_id,
            title=section.display_title,
            nodes=(
                ParagraphNode(
                    id=item.id,
                    teaching_block_id=item.teaching_block_id,
                    display=ParagraphDisplay(text="This section explains the idea in a clear way."),
                ),
            ),
        )
        outputs.append((composition, result))
    return tuple(outputs)


async def _seed_run(session, source: TeachingPlanSource, *, suffix: str = "main"):
    owner = f"inputs-owner-{suffix}"
    lesson_id = f"inputs-lesson-{suffix}"
    concept = ConceptModel(
        id=f"inputs-concept-{suffix}",
        canonical_slug=f"inputs.{suffix}",
        subject="Science",
        title="Inputs fixture",
        created_by=owner,
    )
    unit = UnitModel(
        id=f"inputs-unit-{suffix}",
        owner_id=owner,
        title="Inputs fixture",
        topic="Shared inputs",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Verify accepted shared section inputs.",
    )
    path = PathVersionModel(
        id=f"inputs-path-{suffix}", unit_id=unit.id, version=1, source_plan_json={}
    )
    lesson = PathLessonModel(
        id=lesson_id,
        path_version_id=path.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="Inputs fixture",
        objective="Verify accepted shared section inputs.",
        objective_hash="inputs-objective",
        primary_knowledge_type="conceptual",
        position=0,
    )
    build = GenerationBuildModel(
        id=f"inputs-build-{suffix}", path_lesson_id=lesson_id, owner_user_id=owner
    )
    run = GenerationRunModel(
        id=f"inputs-run-{suffix}",
        build_id=build.id,
        run_type="shared_document",
        owner_user_id=owner,
        status="running",
        stage="section_writing",
        attempt=1,
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash=source.content_hash,
        request_key=f"inputs-request-{suffix}",
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
    await session.flush()
    items = []
    for section, (composition, result) in zip(
        source.plan.sections, _section_outputs(source), strict=True
    ):
        comp_payload = composition.model_dump(mode="json")
        write_payload = result.model_dump(mode="json")
        items.extend(
            [
                GenerationWorkItemModel(
                    id=f"inputs-compose-{suffix}-{section.slot_id}",
                    run_id=run.id,
                    item_key=f"compose:{section.slot_id}",
                    stage="section_composition",
                    status="ready",
                    attempt=1,
                    max_attempts=3,
                    input_hash="compose-input",
                    definition_hash="compose-definition",
                    output_json=comp_payload,
                    output_hash=content_hash(comp_payload),
                ),
                GenerationWorkItemModel(
                    id=f"inputs-write-{suffix}-{section.slot_id}",
                    run_id=run.id,
                    item_key=f"write:{section.slot_id}",
                    stage="section_writing",
                    status="ready",
                    attempt=1,
                    max_attempts=3,
                    input_hash="write-input",
                    definition_hash="write-definition",
                    composition_identity=_stable_hash(comp_payload),
                    output_json=write_payload,
                    output_hash=content_hash(write_payload),
                ),
            ]
        )
    session.add_all(items)
    await session.commit()
    return owner, run.id, items


@pytest.mark.asyncio
async def test_loader_reconstructs_ordered_verified_inputs(db_session) -> None:
    source = _source()
    owner, run_id, _ = await _seed_run(db_session, source)

    bundle = await load_verified_shared_lesson_inputs(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
    )

    assert tuple(item.section_slot_id for item in bundle.compositions) == ("orient", "explain")
    assert tuple(item.id for item in bundle.sections) == ("orient", "explain")
    assert bundle.source_hash == source.content_hash
    assert set(bundle.work_item_ids) == {
        "compose:orient",
        "write:orient",
        "compose:explain",
        "write:explain",
    }
    with pytest.raises(TypeError):
        bundle.work_item_ids["write:orient"] = "changed"


@pytest.mark.asyncio
async def test_loader_uses_writer_admission_hash_for_unicode_section_identity(db_session) -> None:
    source = _source(unicode_slot=True)
    owner, run_id, _ = await _seed_run(db_session, source, suffix="unicode")

    bundle = await load_verified_shared_lesson_inputs(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
    )

    assert tuple(item.section_slot_id for item in bundle.compositions) == ("orient", "explain-é")


@pytest.mark.asyncio
async def test_loader_rejects_tampered_output_hash(db_session) -> None:
    source = _source()
    owner, run_id, items = await _seed_run(db_session, source)
    item = next(item for item in items if item.item_key == "write:orient")
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == item.id)
        .values(output_json={"section_slot_id": "orient", "title": "forged", "nodes": []})
    )
    await db_session.commit()

    with pytest.raises(SharedLessonInputError, match="hash"):
        await load_verified_shared_lesson_inputs(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )


@pytest.mark.asyncio
async def test_loader_rejects_source_conflict_and_owner_isolation(db_session) -> None:
    source = _source()
    owner, run_id, _ = await _seed_run(db_session, source)
    with pytest.raises(SharedLessonInputError, match="source"):
        await load_verified_shared_lesson_inputs(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source.model_copy(update={"content_hash": "a" * 64}),
        )
    with pytest.raises(SharedLessonInputError, match="unavailable"):
        await load_verified_shared_lesson_inputs(
            db_session, run_id=run_id, owner_user_id="other-owner", source=source
        )


@pytest.mark.asyncio
async def test_loader_rejects_missing_and_extra_active_items(db_session) -> None:
    source = _source()
    owner, run_id, items = await _seed_run(db_session, source)
    missing = next(item for item in items if item.item_key == "compose:orient")
    with pytest.raises(SharedLessonInputError, match="not ready"):
        _parse_output(
            SimpleNamespace(**{**missing.__dict__, "status": "queued"}),
            expected_key=missing.item_key,
        )

    media = GenerationWorkItemModel(
        id="inputs-media",
        run_id=run_id,
        item_key="media:figure-1",
        stage="media_generation",
        status="ready",
        attempt=1,
        max_attempts=3,
        input_hash="media-input",
        definition_hash="media-definition",
        output_json={"ok": True},
        output_hash=content_hash({"ok": True}),
    )
    db_session.add(media)
    await db_session.commit()
    await load_verified_shared_lesson_inputs(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )

    extra = GenerationWorkItemModel(
        id="inputs-extra",
        run_id=run_id,
        item_key="compose:unexpected",
        stage="section_composition",
        status="ready",
        attempt=1,
        max_attempts=3,
        input_hash="extra-input",
        definition_hash="extra-definition",
        output_json={"ok": True},
        output_hash=content_hash({"ok": True}),
    )
    db_session.add(extra)
    await db_session.commit()
    with pytest.raises(SharedLessonInputError, match="extra"):
        await load_verified_shared_lesson_inputs(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )


@pytest.mark.asyncio
async def test_loader_uses_replacement_leaf_and_preserves_siblings(db_session) -> None:
    source = _source()
    owner, run_id, items = await _seed_run(db_session, source)
    predecessor = next(item for item in items if item.item_key == "write:orient")
    replacement_payload = predecessor.output_json
    replacement = GenerationWorkItemModel(
        id="inputs-write-orient-repair",
        run_id=run_id,
        replaces_work_item_id=predecessor.id,
        item_key="write:orient:repair-1",
        stage=predecessor.stage,
        status="ready",
        attempt=1,
        max_attempts=3,
        input_hash="changed-input",
        definition_hash=predecessor.definition_hash,
        composition_identity=predecessor.composition_identity,
        output_json=replacement_payload,
        output_hash=content_hash(replacement_payload),
    )
    db_session.add(replacement)
    await db_session.commit()

    bundle = await load_verified_shared_lesson_inputs(
        db_session, run_id=run_id, owner_user_id=owner, source=source
    )
    assert bundle.work_item_ids["write:orient"] == replacement.id
    assert bundle.work_item_ids["write:explain"] == next(
        item.id for item in items if item.item_key == "write:explain"
    )


@pytest.mark.asyncio
async def test_loader_rejects_malformed_writer_output(db_session) -> None:
    source = _source()
    owner, run_id, items = await _seed_run(db_session, source)
    item = next(item for item in items if item.item_key == "write:explain")
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == item.id)
        .values(
            output_json={
                "section_slot_id": "explain",
                "title": "Explain the idea",
                "nodes": [{"kind": "unknown", "id": "x"}],
            },
            output_hash=content_hash(
                {
                    "section_slot_id": "explain",
                    "title": "Explain the idea",
                    "nodes": [{"kind": "unknown", "id": "x"}],
                }
            ),
        )
    )
    await db_session.commit()
    with pytest.raises(SharedLessonInputError, match="stale or invalid"):
        await load_verified_shared_lesson_inputs(
            db_session, run_id=run_id, owner_user_id=owner, source=source
        )


def test_active_chain_rejects_duplicate_active_identity() -> None:
    first = SimpleNamespace(
        id="first", run_id="run", replaces_work_item_id=None, item_key="write:orient"
    )
    second = SimpleNamespace(
        id="second", run_id="run", replaces_work_item_id=None, item_key="write:orient"
    )
    with pytest.raises(SharedLessonInputError, match="duplicate"):
        _assert_active_chain((first, second), (first, second), "run")
