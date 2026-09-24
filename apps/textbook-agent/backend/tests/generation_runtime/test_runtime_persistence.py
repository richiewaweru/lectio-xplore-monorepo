from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from infra.database.models import (
    ConceptModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.generation_runtime import (
    BuildAdmission,
    RunAdmission,
    RunAdmissionConflict,
    RunContract,
    RunType,
    WorkItemAdmission,
    WorkItemConflict,
    WorkItemContract,
    add_work_item,
    admit_run,
    append_event,
    create_build,
    get_run_status,
)


async def _seed_lesson(session, *, suffix: str = "a") -> tuple[str, str]:
    owner_id = f"runtime-owner-{suffix}"
    lesson_id = f"runtime-lesson-{suffix}"
    user = UserModel(id=owner_id, email=f"{owner_id}@example.invalid")
    concept = ConceptModel(
        id=f"runtime-concept-{suffix}",
        canonical_slug=f"runtime.{suffix}",
        subject="Science",
        title="Runtime fixture",
        created_by=owner_id,
    )
    unit = UnitModel(
        id=f"runtime-unit-{suffix}",
        owner_id=owner_id,
        title="Runtime fixture",
        topic="Persistence",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Persist runtime state.",
    )
    version = PathVersionModel(
        id=f"runtime-path-{suffix}",
        unit_id=unit.id,
        version=1,
        source_plan_json={},
    )
    lesson = PathLessonModel(
        id=lesson_id,
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="Runtime fixture",
        objective="Persist runtime state.",
        objective_hash="objective-hash",
        primary_knowledge_type="conceptual",
        position=0,
    )
    session.add_all([user, concept, unit, version, lesson])
    await session.flush()
    return owner_id, lesson_id


async def _admit(session, *, owner_id: str, lesson_id: str, request_key: str = "req-1"):
    build = await create_build(
        session,
        BuildAdmission(owner_user_id=owner_id, path_lesson_id=lesson_id),
    )
    result = await admit_run(
        session,
        RunAdmission(
            build_id=build.id,
            owner_user_id=owner_id,
            run_type=RunType.SHARED_DOCUMENT,
            request_key=request_key,
            stage="section_composition",
            source_artifact_type="teaching_plan",
            source_artifact_id="plan-1",
            source_revision=3,
            source_hash="sha256:plan-a",
        ),
    )
    return build, result


def test_contracts_keep_closed_status_separate_from_stage() -> None:
    now = datetime.now(UTC)
    run_fields = {
        "id": "run-1",
        "build_id": "build-1",
        "run_type": "shared_document",
        "owner_user_id": "owner-1",
        "stage": "section_writing",
        "attempt": 1,
        "source_artifact_type": "teaching_plan",
        "source_artifact_id": "plan-1",
        "source_revision": 1,
        "source_hash": "source-hash",
        "request_key": "request-1",
        "created_at": now,
        "updated_at": now,
    }
    queued = RunContract.model_validate({**run_fields, "status": "queued"})
    assert queued.stage == "section_writing"
    with pytest.raises(ValidationError, match="complete output"):
        RunContract.model_validate({**run_fields, "status": "ready"})
    with pytest.raises(ValidationError):
        RunContract.model_validate({"status": "writing", "stage": "section_writing"})
    with pytest.raises(ValidationError):
        WorkItemContract.model_validate({"status": "awaiting_review", "stage": "section_writing"})
    with pytest.raises(ValidationError, match="output_json"):
        WorkItemContract.model_validate(
            {
                "id": "item-1",
                "run_id": "run-1",
                "item_key": "section:explain",
                "stage": "section_writing",
                "status": "ready",
                "attempt": 1,
                "max_attempts": 1,
                "input_hash": "input-hash",
                "definition_hash": "definition-hash",
                "created_at": now,
                "updated_at": now,
            }
        )
    list_output = WorkItemContract.model_validate(
        {
            "id": "item-list-output",
            "run_id": "run-1",
            "item_key": "section:examples",
            "stage": "section_writing",
            "status": "ready",
            "attempt": 1,
            "max_attempts": 1,
            "input_hash": "input-hash",
            "definition_hash": "definition-hash",
            "checkpoint_json": ["checkpoint-a", 2],
            "output_json": [{"example": 1}, "complete"],
            "output_hash": "output-hash",
            "created_at": now,
            "updated_at": now,
        }
    )
    assert list_output.checkpoint_json == ["checkpoint-a", 2]
    assert list_output.output_json == [{"example": 1}, "complete"]


@pytest.mark.asyncio
async def test_run_admission_reuses_identical_key_and_rejects_hash_conflict(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    build, first = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    same_request = RunAdmission(
        build_id=build.id,
        owner_user_id=owner_id,
        run_type=RunType.SHARED_DOCUMENT,
        request_key="req-1",
        stage="teaching_planning",
        source_artifact_type="teaching_plan",
        source_artifact_id="plan-1",
        source_revision=3,
        source_hash="sha256:plan-a",
    )

    duplicate = await admit_run(db_session, same_request)

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.record.id == first.record.id
    assert duplicate.record.stage == "section_composition"

    with pytest.raises(RunAdmissionConflict):
        await admit_run(
            db_session, same_request.model_copy(update={"source_hash": "sha256:plan-b"})
        )

    with pytest.raises(RunAdmissionConflict):
        await admit_run(db_session, same_request.model_copy(update={"run_type": RunType.PRINT}))


@pytest.mark.asyncio
async def test_build_rejects_path_lesson_owned_by_another_user(db_session) -> None:
    owner_id, _owner_lesson = await _seed_lesson(db_session)
    _other_owner, other_lesson = await _seed_lesson(db_session, suffix="other")

    with pytest.raises(ValueError, match="unavailable to this owner"):
        await create_build(
            db_session,
            BuildAdmission(owner_user_id=owner_id, path_lesson_id=other_lesson),
        )


@pytest.mark.asyncio
async def test_work_item_key_is_idempotent_only_for_same_identity(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    request = WorkItemAdmission(
        run_id=admitted.record.id,
        item_key="section:explain",
        stage="section_writing",
        input_hash="input-a",
        definition_hash="definition-a",
        composition_identity="section:explain:v1",
    )

    first = await add_work_item(db_session, request)
    duplicate = await add_work_item(db_session, request)

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.record.id == first.record.id
    with pytest.raises(WorkItemConflict):
        await add_work_item(db_session, request.model_copy(update={"input_hash": "input-b"}))


@pytest.mark.asyncio
async def test_events_append_with_per_run_sequence_and_reject_mutation(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item_result = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:orient",
            stage="section_writing",
            input_hash="input-orient",
            definition_hash="writer-v1",
        ),
    )

    first = await append_event(
        db_session,
        run_id=admitted.record.id,
        event_type="work_item_queued",
        work_item_id=item_result.record.id,
        safe_payload={"attempt": 1},
    )
    second = await append_event(
        db_session,
        run_id=admitted.record.id,
        event_type="work_item_started",
        work_item_id=item_result.record.id,
    )

    assert (first.seq, second.seq) == (1, 2)
    assert second.stage == "section_writing"
    assert second.status == "queued"
    first.error_code = "rewritten"
    with pytest.raises(ValueError, match="append-only"):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_run_status_is_owner_scoped_and_ready_output_is_immutable(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    other_owner, _other_lesson = await _seed_lesson(db_session, suffix="b")
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)

    assert (
        await get_run_status(db_session, run_id=admitted.record.id, owner_user_id=other_owner)
        is None
    )
    visible = await get_run_status(db_session, run_id=admitted.record.id, owner_user_id=owner_id)
    assert visible is not None
    assert visible.status == "queued"

    run = await db_session.get(GenerationRunModel, admitted.record.id)
    assert run is not None
    run.output_artifact_type = "shared_lesson_document"
    run.output_artifact_id = "document-1"
    run.output_revision = 1
    run.output_hash = "sha256:document-1"
    run.status = "ready"
    await db_session.flush()

    ready_event = await append_event(
        db_session,
        run_id=admitted.record.id,
        event_type="run_ready_observed",
        safe_payload={"source": "test"},
    )
    assert ready_event.status == "ready"
    assert run.status == "ready"
    assert run.output_hash == "sha256:document-1"

    run.output_hash = "sha256:document-2"
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_work_item_ready_output_is_immutable(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="document-qa",
            stage="document_qa",
            input_hash="input-qa",
            definition_hash="qa-v1",
        ),
    )

    work_item = await db_session.get(GenerationWorkItemModel, item.record.id)
    assert work_item is not None
    work_item.output_json = {"passed": True}
    work_item.output_hash = "sha256:qa-passed"
    work_item.status = "ready"
    await db_session.flush()

    work_item.output_hash = "sha256:qa-failed"
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_database_rejects_unknown_run_status(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    build, _admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    db_session.add(
        GenerationRunModel(
            id="invalid-status-run",
            build_id=build.id,
            run_type="shared_document",
            owner_user_id=owner_id,
            status="writing",
            stage="section_writing",
            attempt=1,
            source_artifact_type="teaching_plan",
            source_artifact_id="plan-invalid",
            source_revision=1,
            source_hash="hash",
            request_key="invalid-status",
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_work_item_cannot_use_run_only_awaiting_review_status(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    db_session.add(
        GenerationWorkItemModel(
            id="invalid-work-item-status",
            run_id=admitted.record.id,
            item_key="invalid",
            stage="section_writing",
            status="awaiting_review",
            attempt=1,
            max_attempts=1,
            input_hash="input",
            definition_hash="definition",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
