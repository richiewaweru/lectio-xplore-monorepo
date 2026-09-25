from __future__ import annotations

import pytest
from sqlalchemy import select

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson.composer import (
    CompositionChoice,
    validate_and_build_composition,
)
from document.shared_lesson.runtime import (
    SectionRuntimeError,
    TeachingPlanSource,
    admit_section_run,
    admit_writer_work_item,
    cancel_section_run,
    make_section_writer_request,
    restart_section_run,
    retry_failed_section,
    verify_teaching_plan_source,
)
from infra.database.models import (
    ConceptModel,
    GenerationEventModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    CheckpointCompatibilityError,
    ErrorClass,
    LeaseLostError,
    RecoveryAction,
    RuntimeCheckpointCompatibility,
    SourceIdentityConflict,
    WorkItemFailure,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
)


def _teaching_plan() -> TeachingPlan:
    sections = []
    for slot_id, title, previous in (
        ("orient", "Start with the idea", None),
        ("explain", "Explain the idea", "orient"),
    ):
        block_id = f"block-{slot_id}"
        sections.append(
            TeachingPlanSection(
                slot_id=slot_id,
                display_title=title,
                entry_state=[f"Learner enters {slot_id}"],
                must_establish=[f"Learner understands {slot_id}"],
                avoid_repeating=[f"Avoid repeating {previous or 'no prior section'}"],
                bridge_from_previous=(
                    None if previous is None else f"Connect {previous} to explain"
                ),
                exit_state=[f"Learner exits {slot_id}"],
                blocks=[
                    TeachingPlanBlock(
                        id=block_id,
                        position=0,
                        intent=f"Teach {slot_id}",
                        brief=f"Explain {slot_id} clearly.",
                        evidence=f"Learner can explain {slot_id}.",
                    )
                ],
            )
        )
    return TeachingPlan(
        arc="Introduce and explain one idea.",
        contract_version=2,
        learner_title="A lesson about one idea",
        starting_state=["Learner is ready to learn."],
        target_state=["Learner can explain the idea."],
        teaching_plan_id="shared-runtime-plan",
        revision=4,
        sections=sections,
    )


def _source() -> TeachingPlanSource:
    plan = _teaching_plan().model_copy(update={"approval_status": "approved"})
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id=plan.teaching_plan_id,
        revision=plan.revision,
        status="approved",
        preparation_hash=plan.preparation_hash or "preparation-hash",
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-24T00:00:00Z",
        approved_at="2026-09-24T00:00:00Z",
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


async def _seed_build(session, *, suffix: str) -> tuple[str, str]:
    owner_id = f"shared-runtime-owner-{suffix}"
    lesson_id = f"shared-runtime-lesson-{suffix}"
    concept = ConceptModel(
        id=f"shared-runtime-concept-{suffix}",
        canonical_slug=f"shared-runtime.{suffix}",
        subject="Science",
        title="Runtime integration fixture",
        created_by=owner_id,
    )
    unit = UnitModel(
        id=f"shared-runtime-unit-{suffix}",
        owner_id=owner_id,
        title="Runtime integration fixture",
        topic="Runtime persistence",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Prove durable shared lesson work.",
    )
    version = PathVersionModel(
        id=f"shared-runtime-path-{suffix}",
        unit_id=unit.id,
        version=1,
        source_plan_json={},
    )
    lesson = PathLessonModel(
        id=lesson_id,
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="Runtime integration fixture",
        objective="Prove durable shared lesson work.",
        objective_hash="runtime-integration-objective",
        primary_knowledge_type="conceptual",
        position=0,
    )
    session.add_all(
        [
            UserModel(id=owner_id, email=f"{owner_id}@example.invalid"),
            concept,
            unit,
            version,
            lesson,
        ]
    )
    await session.flush()
    return owner_id, lesson_id


def _writer_request(section: TeachingPlanSection):
    block = section.blocks[0]
    composition = validate_and_build_composition(
        section=section,
        choices=(
            CompositionChoice(
                kind="paragraph",
                teaching_block_id=block.id,
                semantic_role="explanation",
            ),
        ),
        tasks=(),
    )
    return make_section_writer_request(
        section=section,
        composition=composition,
        tasks=(),
    )


def _compatibility(item, source: TeachingPlanSource) -> RuntimeCheckpointCompatibility:
    identity = verify_teaching_plan_source(source)
    return RuntimeCheckpointCompatibility(
        schema_version=1,
        source_revision=identity.source_revision,
        source_hash=identity.source_hash,
        input_hash=item.input_hash,
        definition_hash=item.definition_hash,
        composition_identity=item.composition_identity,
    )


@pytest.mark.asyncio
async def test_shared_lesson_runtime_persists_composition_writer_retry_cancel_and_restart(
    db_session, db_session_factory
) -> None:
    owner_id, lesson_id = await _seed_build(db_session, suffix="integration")
    source = _source()
    build, (run, composition_items) = await _admit_run(
        db_session,
        owner_id=owner_id,
        lesson_id=lesson_id,
        source=source,
        request_key="shared-document-request-1",
    )
    run_id = run.id
    build_id = build.id

    sections = {section.slot_id: section for section in source.plan.sections}
    orient_request = _writer_request(sections["orient"])
    explain_request = _writer_request(sections["explain"])
    ready_item = await admit_writer_work_item(
        db_session,
        run_id=run.id,
        section=sections["orient"],
        request=orient_request,
    )
    retry_item = await admit_writer_work_item(
        db_session,
        run_id=run.id,
        section=sections["explain"],
        request=explain_request,
    )
    ready_item_id = ready_item.id
    retry_item_id = retry_item.id
    await db_session.commit()
    composition_item_ids = [item.id for item in composition_items]

    identity = verify_teaching_plan_source(source)
    wrong_identity = identity.model_copy(update={"source_hash": "0" * 64})
    with pytest.raises(SourceIdentityConflict):
        await claim_work_item(
            db_session,
            work_item_id=composition_item_ids[0],
            worker_id="worker-wrong-source",
            source=wrong_identity,
        )
    async with db_session_factory() as check:
        unchanged = await check.get(GenerationWorkItemModel, composition_item_ids[0])
        assert unchanged is not None
        assert unchanged.status == "queued"
        assert unchanged.lease_owner is None

    # Real generic-runtime composition items are independently claimed and completed.
    for index, item in enumerate(composition_items):
        claimed = await claim_work_item(
            db_session,
            work_item_id=item.id,
            worker_id=f"composer-{index}",
            source=identity,
        )
        value = {"section_slot_id": item.item_key.split(":", 1)[1], "items": []}
        completed = await complete_work_item(
            db_session,
            work_item_id=item.id,
            worker_id=f"composer-{index}",
            lease_token=claimed.lease_token,
            output_json=value,
            output_hash=content_hash(value),
        )
        assert completed.status == "ready"

    # Persist an exactly compatible writer checkpoint and prove changed source
    # or composition identity cannot load it.
    ready_claim = await claim_work_item(
        db_session,
        work_item_id=ready_item.id,
        worker_id="writer-orient",
        source=identity,
    )
    ready_compatibility = _compatibility(ready_item, source)
    checkpoint_payload = {
        "composition_identity": ready_item.composition_identity,
        "plan": orient_request.composition_plan.model_dump(mode="json"),
    }
    await persist_checkpoint(
        db_session,
        work_item_id=ready_item.id,
        worker_id="writer-orient",
        lease_token=ready_claim.lease_token,
        compatibility=ready_compatibility,
        payload=checkpoint_payload,
    )
    with pytest.raises(CheckpointCompatibilityError):
        await load_compatible_checkpoint(
            db_session,
            work_item_id=ready_item.id,
            worker_id="writer-orient",
            lease_token=ready_claim.lease_token,
            compatibility=ready_compatibility.model_copy(
                update={"composition_identity": "different-composition"}
            ),
        )

    stable_output = {
        "section_slot_id": "orient",
        "nodes": [{"kind": "paragraph", "text": "The opening explanation."}],
    }
    await complete_work_item(
        db_session,
        work_item_id=ready_item.id,
        worker_id="writer-orient",
        lease_token=ready_claim.lease_token,
        output_json=stable_output,
        output_hash=content_hash(stable_output),
    )

    first_retry_claim = await claim_work_item(
        db_session,
        work_item_id=retry_item.id,
        worker_id="writer-explain-first",
        source=identity,
    )
    await fail_work_item(
        db_session,
        work_item_id=retry_item.id,
        worker_id="writer-explain-first",
        lease_token=first_retry_claim.lease_token,
        failure=WorkItemFailure(
            error_code="section_output_invalid",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary="Section output did not satisfy the document contract.",
            recovery_action=RecoveryAction.RETRY,
        ),
    )
    await db_session.commit()

    retried = await retry_failed_section(
        db_session,
        work_item_id=retry_item.id,
        owner_user_id=owner_id,
    )
    assert retried.status == "queued"
    assert retried.attempt == 2
    await db_session.refresh(ready_item)
    assert ready_item.status == "ready"
    assert ready_item.output_json == stable_output
    assert ready_item.attempt == 1
    await db_session.commit()

    # Cancel the requeued work, preserve ready output, and reject a late worker
    # completion using the pre-cancel fence.
    late_claim = await claim_work_item(
        db_session,
        work_item_id=retry_item.id,
        worker_id="worker-late",
        source=identity,
    )
    await db_session.commit()
    cancelled = await cancel_section_run(
        db_session,
        run_id=run.id,
        owner_user_id=owner_id,
    )
    assert cancelled.status == "cancelled"
    await db_session.commit()

    with pytest.raises(LeaseLostError):
        await complete_work_item(
            db_session,
            work_item_id=retry_item.id,
            worker_id="worker-late",
            lease_token=late_claim.lease_token,
            output_json={"section_slot_id": "explain", "nodes": []},
            output_hash=content_hash({"section_slot_id": "explain", "nodes": []}),
        )
    await db_session.rollback()

    restarted_run, restarted_items = await restart_section_run(
        db_session,
        previous_run_id=run_id,
        build_id=build_id,
        owner_user_id=owner_id,
        request_key="shared-document-request-restart",
        source=source,
    )
    restarted_run_id = restarted_run.id
    assert restarted_run_id != run_id
    assert restarted_run.status == "queued"
    assert {item.item_key for item in restarted_items} == {
        "compose:orient",
        "compose:explain",
    }
    await db_session.commit()

    async with db_session_factory() as verify:
        persisted_ready = await verify.get(GenerationWorkItemModel, ready_item_id)
        persisted_retry = await verify.get(GenerationWorkItemModel, retry_item_id)
        persisted_old_run = await verify.get(GenerationRunModel, run_id)
        persisted_restart = await verify.get(GenerationRunModel, restarted_run_id)
        assert persisted_ready is not None and persisted_ready.status == "ready"
        assert persisted_ready.output_json == stable_output
        assert persisted_retry is not None and persisted_retry.status == "cancelled"
        assert persisted_old_run is not None and persisted_old_run.status == "cancelled"
        assert persisted_restart is not None and persisted_restart.status == "queued"
        events = list(
            (
                await verify.scalars(
                    select(GenerationEventModel).where(
                        GenerationEventModel.run_id == run_id
                    )
                )
            ).all()
        )
        assert any(event.event_type == "work_item_ready" for event in events)
        assert any(event.event_type == "work_item_failed" for event in events)
        assert any(event.event_type == "run_cancelled" for event in events)


@pytest.mark.asyncio
async def test_shared_document_admission_rejects_hashed_pending_teaching_revision(
    db_session,
) -> None:
    """A correctly hashed pending revision cannot enter SharedDocument work."""
    owner_id, lesson_id = await _seed_build(db_session, suffix="pending-source")
    plan = _teaching_plan().model_copy(update={"approval_status": "pending"})
    pending_record = TeachingRevisionRecord(
        teaching_plan_id=plan.teaching_plan_id,
        revision=plan.revision,
        status="pending",
        preparation_hash="preparation-hash",
        content_hash=teaching_plan_content_hash(plan),
        approval_hash_binding=None,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-24T00:00:00Z",
    )
    source = TeachingPlanSource(
        plan=TeachingPlan.model_validate(pending_record.plan),
        revision_record=pending_record,
        id=pending_record.teaching_plan_id,
        revision=pending_record.revision,
        content_hash=pending_record.content_hash or "",
    )
    from infra.generation_runtime import BuildAdmission, create_build

    build = await create_build(
        db_session,
        BuildAdmission(owner_user_id=owner_id, path_lesson_id=lesson_id),
    )
    with pytest.raises(SectionRuntimeError, match="approved"):
        await admit_section_run(
            db_session,
            build_id=build.id,
            owner_user_id=owner_id,
            request_key="pending-plan-request",
            source=source,
        )
    run_count = await db_session.scalar(
        select(GenerationRunModel.id).where(
            GenerationRunModel.build_id == build.id,
        )
    )
    assert run_count is None


async def _admit_run(
    session,
    *,
    owner_id: str,
    lesson_id: str,
    source: TeachingPlanSource,
    request_key: str,
):
    from infra.generation_runtime import BuildAdmission, create_build

    build = await create_build(
        session,
        BuildAdmission(owner_user_id=owner_id, path_lesson_id=lesson_id),
    )
    run, composition_items = await admit_section_run(
        session,
        build_id=build.id,
        owner_user_id=owner_id,
        request_key=request_key,
        source=source,
    )
    return build, (run, composition_items)
