from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

import infra.generation_runtime.repository as runtime_repository
from infra.database.models import (
    ConceptModel,
    GenerationEventModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    BuildAdmission,
    InvalidRunTransition,
    RunAdmission,
    RunFailure,
    RunNotFound,
    RunType,
    SourceIdentity,
    WorkItemAdmission,
    add_work_item,
    admit_run,
    claim_work_item,
    complete_work_item,
    create_build,
    fail_run_terminal,
)


def _source() -> SourceIdentity:
    return SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id="plan-terminal",
        source_revision=1,
        source_hash="source-terminal",
    )


def _failure() -> RunFailure:
    return RunFailure(
        error_code="dependency_admission_failed",
        error_class="unsupported_contract",
        safe_summary="A required dependency could not be admitted.",
    )


async def _admit(session, suffix: str):
    owner_id = f"terminal-owner-{suffix}"
    lesson_id = f"terminal-lesson-{suffix}"
    user = UserModel(id=owner_id, email=f"{owner_id}@example.invalid")
    concept = ConceptModel(
        id=f"terminal-concept-{suffix}",
        canonical_slug=f"terminal.{suffix}",
        subject="Science",
        title="Terminal failure fixture",
        created_by=owner_id,
    )
    unit = UnitModel(
        id=f"terminal-unit-{suffix}",
        owner_id=owner_id,
        title="Terminal failure fixture",
        topic="Runtime",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Persist a terminal run failure.",
    )
    version = PathVersionModel(
        id=f"terminal-path-{suffix}",
        unit_id=unit.id,
        version=1,
        source_plan_json={},
    )
    lesson = PathLessonModel(
        id=lesson_id,
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="Terminal failure fixture",
        objective="Persist a terminal run failure.",
        objective_hash="objective-hash",
        primary_knowledge_type="conceptual",
        position=0,
    )
    session.add_all([user, concept, unit, version, lesson])
    await session.flush()
    build = await create_build(
        session,
        BuildAdmission(owner_user_id=owner_id, path_lesson_id=lesson_id),
    )
    admitted = await admit_run(
        session,
        RunAdmission(
            build_id=build.id,
            owner_user_id=owner_id,
            run_type=RunType.SHARED_DOCUMENT,
            request_key=f"terminal-request-{suffix}",
            stage="sourcebook_generation",
            source_artifact_type="teaching_plan",
            source_artifact_id="plan-terminal",
            source_revision=1,
            source_hash="source-terminal",
        ),
    )
    return owner_id, admitted.record


async def _add_item(session, run_id: str, item_key: str):
    result = await add_work_item(
        session,
        WorkItemAdmission(
            run_id=run_id,
            item_key=item_key,
            stage="sourcebook_generation",
            input_hash=f"input-{item_key}",
            definition_hash="definition-sourcebook",
        ),
    )
    return result.record


@pytest.mark.asyncio
async def test_terminal_failure_records_run_event_and_preserves_ready_item(db_session):
    owner_id, run = await _admit(db_session, "ready-sibling")
    item = await _add_item(db_session, run.id, "sourcebook")
    start = datetime(2026, 9, 25, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=item.id,
        worker_id="sourcebook-worker",
        source=_source(),
        now=start,
    )
    output = {"sourcebook": "ready"}
    await complete_work_item(
        db_session,
        work_item_id=item.id,
        worker_id="sourcebook-worker",
        lease_token=claim.lease_token,
        output_json=output,
        output_hash=content_hash(output),
        now=start,
    )

    failed = await fail_run_terminal(
        db_session,
        run_id=run.id,
        owner_user_id=owner_id,
        failure=_failure(),
        now=start,
    )

    assert failed.status == "failed_terminal"
    assert failed.error_code == "dependency_admission_failed"
    assert failed.error_class == "unsupported_contract"
    assert failed.error_summary == "A required dependency could not be admitted."
    assert failed.recovery_action == "none"
    assert failed.completed_at == start.replace(tzinfo=None)
    await db_session.refresh(item)
    assert item.status == "ready"
    assert item.output_json == output
    assert item.output_hash == content_hash(output)
    event = await db_session.scalar(
        select(GenerationEventModel).where(
            GenerationEventModel.run_id == run.id,
            GenerationEventModel.event_type == "run_failed",
        )
    )
    assert event is not None
    assert event.status == "failed_terminal"
    assert event.error_code == "dependency_admission_failed"
    assert event.safe_payload_json == {
        "error_class": "unsupported_contract",
        "safe_summary": "A required dependency could not be admitted.",
        "recovery_action": "none",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("item_status", ["queued", "running"])
async def test_terminal_failure_rejects_active_work_item(db_session, item_status):
    owner_id, run = await _admit(db_session, f"active-{item_status}")
    item = await _add_item(db_session, run.id, f"active-{item_status}")
    if item_status == "running":
        await claim_work_item(
            db_session,
            work_item_id=item.id,
            worker_id="active-worker",
            source=_source(),
            now=datetime(2026, 9, 25, tzinfo=UTC),
        )

    with pytest.raises(InvalidRunTransition, match="active work items"):
        await fail_run_terminal(
            db_session,
            run_id=run.id,
            owner_user_id=owner_id,
            failure=_failure(),
        )

    await db_session.refresh(run)
    await db_session.refresh(item)
    assert run.status in {"queued", "running"}
    assert item.status == item_status
    assert (
        await db_session.scalar(
            select(GenerationEventModel).where(
                GenerationEventModel.run_id == run.id,
                GenerationEventModel.event_type == "run_failed",
            )
        )
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["ready", "cancelled"])
async def test_terminal_failure_rejects_foreign_and_terminal_run(db_session, terminal_status):
    owner_id, run = await _admit(db_session, "scope")

    with pytest.raises(RunNotFound):
        await fail_run_terminal(
            db_session,
            run_id=run.id,
            owner_user_id="foreign-owner",
            failure=_failure(),
        )
    run.status = terminal_status
    if terminal_status == "ready":
        run.output_artifact_type = "shared_lesson_document"
        run.output_artifact_id = "already-ready-document"
        run.output_revision = 1
        run.output_hash = "already-ready-hash"
    await db_session.flush()
    with pytest.raises(InvalidRunTransition, match="only an active run"):
        await fail_run_terminal(
            db_session,
            run_id=run.id,
            owner_user_id=owner_id,
            failure=_failure(),
        )


@pytest.mark.asyncio
async def test_terminal_failure_rolls_back_run_when_event_append_fails(db_session, monkeypatch):
    owner_id, run = await _admit(db_session, "atomic")

    async def fail_event(*_args, **_kwargs):
        raise RuntimeError("injected event failure")

    monkeypatch.setattr(runtime_repository, "append_event", fail_event)
    with pytest.raises(RuntimeError, match="injected event failure"):
        await fail_run_terminal(
            db_session,
            run_id=run.id,
            owner_user_id=owner_id,
            failure=_failure(),
        )

    await db_session.refresh(run)
    assert run.status == "queued"
    assert run.error_code is None
    assert run.completed_at is None
