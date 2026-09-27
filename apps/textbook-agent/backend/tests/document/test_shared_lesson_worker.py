from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_shared_lesson_approved_source import _prepared

from curriculum.lesson_sourcebook.models import LessonSourcebook
from document.shared_lesson import worker
from document.shared_lesson.approved_source import ApprovedSourceVerificationError
from document.shared_lesson.run_admission import admit_shared_document_run
from document.shared_lesson.semantic_inputs import (
    SemanticInputError,
    admit_shared_task_work_item,
)
from infra.database.models import GenerationEventModel, GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import SourceIdentity


def _identity(source) -> SourceIdentity:
    return SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash=source.content_hash,
    )


async def _admitted(
    db_session, *, source, lesson, generation, request_key: str, owner_user_id: str = "source-owner"
):
    result = await admit_shared_document_run(
        db_session,
        owner_user_id=owner_user_id,
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        request_key=request_key,
    )
    await db_session.commit()
    return result


def _bind_source_context(monkeypatch, source):
    async def load_source(**_kwargs):
        return source

    async def verify(_session, requested):
        return requested

    monkeypatch.setattr(worker, "load_current_approved_teaching_plan_source", load_source)
    monkeypatch.setattr(worker, "make_approved_source_verifier", lambda **_kwargs: verify)
    return verify


@pytest.mark.asyncio
async def test_sourcebook_dispatch_commits_and_does_not_hold_provider_transaction(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission = await _admitted(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-sourcebook",
    )
    calls = []
    _bind_source_context(monkeypatch, source)

    async def execute(job, **_kwargs):
        calls.append(job)
        row = await db_session.get(GenerationWorkItemModel, job.work_item_id)
        row.status = "ready"
        row.output_json = {"entries": []}
        row.output_hash = content_hash(row.output_json)

    monkeypatch.setattr(worker, "execute_sourcebook_work_item", execute)
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-1")

    assert await worker_instance.run_one(db_session)
    assert len(calls) == 1
    assert calls[0].work_item_id == admission.sourcebook_work_item.id
    assert calls[0].status == "queued"


@pytest.mark.asyncio
async def test_ready_sourcebook_admits_tasks_once_and_preserves_run_lineage(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission = await _admitted(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-task-admission",
    )
    sourcebook = await db_session.get(GenerationWorkItemModel, admission.sourcebook_work_item.id)
    sourcebook.status = "ready"
    sourcebook.output_json = {"entries": []}
    sourcebook.output_hash = content_hash(sourcebook.output_json)
    await db_session.commit()
    _bind_source_context(monkeypatch, source)

    async def load_verified(*_args, **_kwargs):
        return SimpleNamespace(sourcebook_output_hash=sourcebook.output_hash)

    admissions = []

    async def admit_tasks(*_args, **kwargs):
        admissions.append(kwargs)
        return SimpleNamespace(created=True)

    monkeypatch.setattr(worker, "load_verified_sourcebook_input", load_verified)
    monkeypatch.setattr(worker, "admit_shared_task_work_item", admit_tasks)
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-2")

    assert await worker_instance.run_one(db_session)
    assert len(admissions) == 1
    assert admissions[0]["run_id"] == admission.run.id
    assert admissions[0]["sourcebook_output_hash"] == sourcebook.output_hash
    run = await db_session.get(GenerationRunModel, admission.run.id)
    assert run is not None
    assert run.stage == "shared_task_generation"


@pytest.mark.asyncio
async def test_duplicate_poll_after_sourcebook_ready_does_not_call_provider_again(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission = await _admitted(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-duplicate-poll",
    )
    _bind_source_context(monkeypatch, source)
    provider_calls = []

    async def execute(job, **_kwargs):
        provider_calls.append(job.work_item_id)
        row = await db_session.get(GenerationWorkItemModel, job.work_item_id)
        row.status = "ready"
        row.output_json = {"entries": []}
        row.output_hash = content_hash(row.output_json)

    async def load_verified(*_args, **_kwargs):
        row = await db_session.get(GenerationWorkItemModel, admission.sourcebook_work_item.id)
        return SimpleNamespace(sourcebook_output_hash=row.output_hash)

    monkeypatch.setattr(worker, "execute_sourcebook_work_item", execute)
    monkeypatch.setattr(worker, "load_verified_sourcebook_input", load_verified)
    monkeypatch.setattr(worker, "admit_shared_task_work_item", lambda *_a, **_k: _noop())
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-3")

    assert await worker_instance.run_one(db_session)
    assert await worker_instance.run_one(db_session)
    assert provider_calls == [admission.sourcebook_work_item.id]


async def _noop():
    return SimpleNamespace(created=False)


@pytest.mark.asyncio
async def test_expired_lease_is_selected_but_cancelled_run_is_not(db_session, monkeypatch):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission = await _admitted(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-expired",
    )
    item = await db_session.get(GenerationWorkItemModel, admission.sourcebook_work_item.id)
    item.status = "running"
    item.lease_expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    await db_session.commit()
    _bind_source_context(monkeypatch, source)
    calls = []

    async def execute(job, **_kwargs):
        calls.append(job.work_item_id)

    monkeypatch.setattr(worker, "execute_sourcebook_work_item", execute)
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-4")
    assert await worker_instance.run_one(db_session)
    assert calls == [item.id]

    run = await db_session.get(GenerationRunModel, admission.run.id)
    run.status = "cancelled"
    await db_session.commit()
    calls.clear()
    assert await worker_instance.run_one(db_session) is False
    assert calls == []


@pytest.mark.asyncio
async def test_worker_passes_writer_specific_lease_without_changing_other_stage_lease(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission = await _admitted(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-writer-lease",
    )
    captured = {}

    class Dispatcher:
        def __init__(self, _factory, **kwargs):
            captured.update(kwargs)

        async def run_one(self, **_kwargs):
            return SimpleNamespace(blocked=True)

    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-lease")
    candidate = worker._Candidate(
        run=admission.run,
        item=None,
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        dispatch_sections=True,
    )

    async def find_candidate(_session, _now):
        return candidate

    async def source_context(_session, _candidate):
        return source, lambda *_args: _identity(source), None

    monkeypatch.setattr(instance, "_find_candidate", find_candidate)
    monkeypatch.setattr(instance, "_source_context", source_context)
    monkeypatch.setattr(worker, "SharedSectionDispatcher", Dispatcher)

    assert await instance.run_one(db_session)
    assert captured["lease_seconds"] == 300
    assert captured["writer_lease_seconds"] == 360


@pytest.mark.asyncio
async def test_stale_source_context_fails_claimed_item_without_provider_call(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission = await _admitted(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-stale-source",
    )

    async def stale_source(**_kwargs):
        raise ApprovedSourceVerificationError("stale approved source")

    monkeypatch.setattr(worker, "load_current_approved_teaching_plan_source", stale_source)
    provider_calls = []
    monkeypatch.setattr(
        worker,
        "execute_sourcebook_work_item",
        lambda *_a, **_k: provider_calls.append(True),
    )
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-5")

    assert await worker_instance.run_one(db_session)
    assert provider_calls == []
    item = await db_session.get(GenerationWorkItemModel, admission.sourcebook_work_item.id)
    assert item is not None
    assert item.status == "failed_terminal"
    assert item.error_class == "source_conflict"


async def _ready_sourcebook(db_session, *, source, lesson, generation, request_key):
    admission = await _admitted(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key=request_key,
    )
    item = await db_session.get(GenerationWorkItemModel, admission.sourcebook_work_item.id)
    assert item is not None
    item.status = "ready"
    item.output_json = {"entries": []}
    item.output_hash = content_hash(item.output_json)
    await db_session.commit()
    return admission, item


@pytest.mark.asyncio
async def test_ready_sourcebook_dependency_loss_fails_run_durably_and_stops_after_restart(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, sourcebook = await _ready_sourcebook(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-terminal-snapshot-loss",
    )
    _bind_source_context(monkeypatch, source)

    async def missing_snapshot(*_args, **_kwargs):
        raise SemanticInputError("approved item snapshot is unavailable or invalid")

    monkeypatch.setattr(worker, "load_verified_sourcebook_input", missing_snapshot)
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-terminal-1")

    assert await worker_instance.run_one(db_session)
    run = await db_session.get(GenerationRunModel, admission.run.id)
    assert run is not None
    assert run.status == "failed_terminal"
    assert run.error_class == "unsupported_contract"
    assert run.recovery_action == "none"
    await db_session.refresh(sourcebook)
    assert sourcebook.status == "ready"
    assert sourcebook.output_json == {"entries": []}
    event = await db_session.scalar(
        select(GenerationEventModel).where(
            GenerationEventModel.run_id == admission.run.id,
            GenerationEventModel.event_type == "run_failed",
        )
    )
    assert event is not None
    assert event.status == "failed_terminal"
    assert event.safe_payload_json["error_class"] == "unsupported_contract"

    restarted_worker = worker.SharedDocumentWorker(lambda: None, worker_id="worker-terminal-2")
    assert await restarted_worker.run_one(db_session) is False


@pytest.mark.asyncio
async def test_ready_sourcebook_approved_source_loss_fails_as_source_conflict(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, sourcebook = await _ready_sourcebook(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-terminal-source-loss",
    )

    async def stale_source(**_kwargs):
        raise ApprovedSourceVerificationError("approved source no longer exists")

    monkeypatch.setattr(worker, "load_current_approved_teaching_plan_source", stale_source)
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-terminal-3")

    assert await worker_instance.run_one(db_session)
    run = await db_session.get(GenerationRunModel, admission.run.id)
    assert run is not None
    assert run.status == "failed_terminal"
    assert run.error_class == "source_conflict"
    assert run.recovery_action == "none"
    await db_session.refresh(sourcebook)
    assert sourcebook.status == "ready"


@pytest.mark.asyncio
async def test_task_admission_snapshot_loss_fails_run_terminally(db_session, monkeypatch):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, sourcebook = await _ready_sourcebook(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-terminal-task-admission-loss",
    )
    _bind_source_context(monkeypatch, source)

    async def verified(*_args, **_kwargs):
        return SimpleNamespace(sourcebook_output_hash=sourcebook.output_hash)

    async def rejected_admission(*_args, **_kwargs):
        raise SemanticInputError("approved item snapshot is unavailable or invalid")

    monkeypatch.setattr(worker, "load_verified_sourcebook_input", verified)
    monkeypatch.setattr(worker, "admit_shared_task_work_item", rejected_admission)
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-terminal-5")

    assert await worker_instance.run_one(db_session)
    run = await db_session.get(GenerationRunModel, admission.run.id)
    assert run is not None
    assert run.status == "failed_terminal"
    assert run.error_class == "unsupported_contract"
    await db_session.refresh(sourcebook)
    assert sourcebook.status == "ready"


@pytest.mark.asyncio
async def test_ready_sourcebook_programming_error_is_not_classified_as_source_conflict(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, _sourcebook = await _ready_sourcebook(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-terminal-programming-error",
    )

    async def programming_error(**_kwargs):
        raise RuntimeError("unexpected implementation failure")

    monkeypatch.setattr(worker, "load_current_approved_teaching_plan_source", programming_error)
    worker_instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-terminal-4")

    with pytest.raises(RuntimeError, match="unexpected implementation failure"):
        await worker_instance.run_one(db_session)

    run = await db_session.get(GenerationRunModel, admission.run.id)
    assert run is not None
    assert run.status == "queued"
    assert run.error_class is None


async def _ready_semantic_dependencies(
    db_session,
    *,
    source,
    lesson,
    generation,
    request_key,
    task_status="ready",
    owner_user_id="source-owner",
):
    admission = await _admitted(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key=request_key,
        owner_user_id=owner_user_id,
    )
    sourcebook_item = await db_session.get(
        GenerationWorkItemModel, admission.sourcebook_work_item.id
    )
    assert sourcebook_item is not None
    sourcebook = LessonSourcebook(
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
        entries=[],
    )
    sourcebook_payload = sourcebook.model_dump(mode="json")
    sourcebook_item.status = "ready"
    sourcebook_item.output_json = sourcebook_payload
    sourcebook_item.output_hash = content_hash(sourcebook_payload)
    await db_session.commit()
    task_admission = await admit_shared_task_work_item(
        db_session,
        run_id=admission.run.id,
        owner_user_id=admission.run.owner_user_id,
        source=source,
        sourcebook_output_hash=sourcebook_item.output_hash,
    )
    task_item = await db_session.get(GenerationWorkItemModel, task_admission.record.id)
    assert task_item is not None
    task_item.status = task_status
    task_item.output_json = []
    task_item.output_hash = content_hash([])
    run = await db_session.get(GenerationRunModel, admission.run.id)
    assert run is not None
    run.stage = "shared_task_generation"
    await db_session.commit()
    return admission, task_item


@pytest.mark.asyncio
async def test_ready_semantic_leaves_handoff_to_post_section_pipeline(db_session, monkeypatch):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, _task = await _ready_semantic_dependencies(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-section-stage",
    )
    run_id = admission.run.id
    owner_user_id = admission.run.owner_user_id
    for item_key, stage in (
        ("compose:orient", "section_composition"),
        ("write:orient", "section_writing"),
    ):
        item = GenerationWorkItemModel(
            run_id=admission.run.id,
            item_key=item_key,
            stage=stage,
            status="ready",
            input_hash="i" * 64,
            definition_hash="d" * 64,
            output_json={"ready": True},
            output_hash=content_hash({"ready": True}),
        )
        db_session.add(item)
    await db_session.commit()
    verifier = _bind_source_context(monkeypatch, source)
    composer_provider = object()
    writer_provider = object()
    dispatched = []

    class Dispatcher:
        def __init__(self, session_factory, **kwargs):
            assert session_factory is not None
            assert kwargs["composer_provider"] is composer_provider
            assert kwargs["writer_provider"] is writer_provider

        async def run_one(self, **kwargs):
            dispatched.append(kwargs)
            return SimpleNamespace(
                blocked=False,
                writer_dispatched=len(source.plan.sections),
                writer_preserved=0,
            )

    monkeypatch.setattr(worker, "SharedSectionDispatcher", Dispatcher)
    pipeline_calls = []

    async def finalize_pipeline(_session_factory, **kwargs):
        pipeline_calls.append(kwargs)
        run = await db_session.get(GenerationRunModel, run_id)
        assert run is not None
        run.stage = "document_finalization"
        run.status = "ready"
        run.output_artifact_type = "shared_lesson_document"
        run.output_artifact_id = "shared-document:test"
        run.output_revision = 1
        run.output_hash = "h" * 64
        await db_session.commit()
        return SimpleNamespace(state="ready", stage="finalization", error=None)

    monkeypatch.setattr(worker, "run_post_section_pipeline", finalize_pipeline)
    instance = worker.SharedDocumentWorker(
        lambda: None,
        worker_id="worker-section-stage",
        composer_provider=composer_provider,
        writer_provider=writer_provider,
    )

    assert await instance.run_one(db_session)
    assert len(dispatched) == 1
    assert dispatched[0]["run_id"] == run_id
    assert dispatched[0]["owner_user_id"] == owner_user_id
    assert dispatched[0]["source"] == source
    assert dispatched[0]["source_verifier"] is verifier
    run = await db_session.get(GenerationRunModel, run_id)
    assert run is not None and run.stage == "section_writing"
    assert run.status in {"queued", "running"}

    restarted = worker.SharedDocumentWorker(
        lambda: None, worker_id="worker-section-stage-restarted"
    )
    assert await restarted.run_one(db_session)
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["run_id"] == run_id
    assert pipeline_calls[0]["owner_user_id"] == owner_user_id
    assert await restarted.run_one(db_session) is False
    assert len(dispatched) == 1


async def _ready_section_leaves_for_post_pipeline(db_session, admission):
    for item_key, stage in (
        ("compose:orient", "section_composition"),
        ("write:orient", "section_writing"),
    ):
        db_session.add(
            GenerationWorkItemModel(
                run_id=admission.run.id,
                item_key=item_key,
                stage=stage,
                status="ready",
                input_hash="i" * 64,
                definition_hash="d" * 64,
                output_json={"ready": True},
                output_hash=content_hash({"ready": True}),
            )
        )
    run = await db_session.get(GenerationRunModel, admission.run.id)
    assert run is not None
    run.stage = "section_writing"
    await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("pipeline_state", ["pending", "blocked"])
async def test_post_section_pending_or_blocked_is_not_polled_again(
    db_session, monkeypatch, pipeline_state
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, _task = await _ready_semantic_dependencies(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key=f"worker-post-{pipeline_state}",
    )
    run_id = admission.run.id
    await _ready_section_leaves_for_post_pipeline(db_session, admission)
    if pipeline_state == "pending":
        db_session.add(
            GenerationWorkItemModel(
                run_id=run_id,
                item_key="document_qa:post",
                stage="document_qa",
                status="running",
                input_hash="i" * 64,
                definition_hash="d" * 64,
                lease_expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5),
            )
        )
        await db_session.commit()
    _bind_source_context(monkeypatch, source)
    calls = []

    async def pipeline(_session_factory, **kwargs):
        calls.append(kwargs)
        run = await db_session.get(GenerationRunModel, run_id)
        assert run is not None
        run.stage = "document_qa" if pipeline_state == "pending" else "document_finalization"
        await db_session.commit()
        return SimpleNamespace(state=pipeline_state, stage=run.stage, error="test gate")

    monkeypatch.setattr(worker, "run_post_section_pipeline", pipeline)
    instance = worker.SharedDocumentWorker(
        lambda: None,
        worker_id=f"worker-post-{pipeline_state}",
        media_executor=object(),
        boundary_semantic_validator=object(),
        boundary_repair_engine=object(),
        qa_semantic_validator=object(),
    )
    assert await instance.run_one(db_session)
    assert await instance.run_one(db_session) is False
    assert len(calls) == 1
    assert calls[0]["media_executor"] is instance.media_executor
    assert calls[0]["boundary_semantic_validator"] is instance.boundary_semantic_validator
    assert calls[0]["boundary_repair_engine"] is instance.boundary_repair_engine
    assert calls[0]["qa_semantic_validator"] is instance.qa_semantic_validator


@pytest.mark.asyncio
async def test_post_section_retries_failed_leaf_after_run_stage_advances(
    db_session, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, _task = await _ready_semantic_dependencies(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-post-stage-advance",
    )
    run_id = admission.run.id
    await _ready_section_leaves_for_post_pipeline(db_session, admission)
    db_session.add(
        GenerationWorkItemModel(
            run_id=run_id,
            item_key="boundary:orient->practice",
            stage="continuity_validation",
            status="failed_recoverable",
            input_hash="i" * 64,
            definition_hash="d" * 64,
        )
    )
    run = await db_session.get(GenerationRunModel, run_id)
    assert run is not None
    run.stage = "media_generation"
    await db_session.commit()
    _bind_source_context(monkeypatch, source)
    calls = []

    async def pipeline(_session_factory, **kwargs):
        calls.append(kwargs)
        run = await db_session.get(GenerationRunModel, run_id)
        assert run is not None
        run.stage = "continuity_validation"
        await db_session.commit()
        return SimpleNamespace(state="pending", stage=run.stage, error=None)

    monkeypatch.setattr(worker, "run_post_section_pipeline", pipeline)
    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-post-stage-advance")

    assert await instance.run_one(db_session)
    assert await instance.run_one(db_session) is False
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cancelled_ready_sections_are_not_selected_for_post_pipeline(db_session, monkeypatch):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, _task = await _ready_semantic_dependencies(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-post-cancelled",
    )
    run_id = admission.run.id
    await _ready_section_leaves_for_post_pipeline(db_session, admission)
    run = await db_session.get(GenerationRunModel, run_id)
    assert run is not None
    run.status = "cancelled"
    await db_session.commit()
    calls = []
    monkeypatch.setattr(worker, "run_post_section_pipeline", lambda *_a, **_k: calls.append(True))

    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-post-cancelled")
    assert await instance.run_one(db_session) is False
    assert calls == []


@pytest.mark.asyncio
async def test_failed_task_dependency_never_dispatches_sections(db_session, monkeypatch):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission, _task = await _ready_semantic_dependencies(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-section-failed-task",
        task_status="failed_recoverable",
    )
    _bind_source_context(monkeypatch, source)
    dispatch_calls = []

    class Dispatcher:
        def __init__(self, *_args, **_kwargs):
            dispatch_calls.append(True)

    monkeypatch.setattr(worker, "SharedSectionDispatcher", Dispatcher)
    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-failed-task")

    assert await instance.run_one(db_session) is False
    assert dispatch_calls == []
    run = await db_session.get(GenerationRunModel, admission.run.id)
    assert run is not None and run.stage == "shared_task_generation"


@pytest.mark.asyncio
async def test_unexpected_dispatch_failure_terminalizes_run_and_frees_other_runs(
    db_session, monkeypatch
):
    """A poisoned Run's dispatch failure must not starve a fresh queued Run.

    Regression for the live incident: a WorkItemConflict raised from section
    dispatch every iteration, and the worker only logged and retried the
    same Run, starving every other queued Run.
    """
    generation_a, lesson_a, _prov_a, source_a = await _prepared(db_session, user_id="owner-poison-a")
    generation_b, lesson_b, _prov_b, source_b = await _prepared(db_session, user_id="owner-poison-b")

    admission_a, _task_a = await _ready_semantic_dependencies(
        db_session,
        source=source_a,
        lesson=lesson_a,
        generation=generation_a,
        request_key="worker-poison-a",
        owner_user_id="owner-poison-a",
    )
    run_a_id = admission_a.run.id

    admission_b = await _admitted(
        db_session,
        source=source_b,
        lesson=lesson_b,
        generation=generation_b,
        request_key="worker-poison-b",
        owner_user_id="owner-poison-b",
    )
    run_b_id = admission_b.run.id

    # Run A must be older so `_find_candidate` visits it before Run B.
    run_a = await db_session.get(GenerationRunModel, run_a_id)
    run_b = await db_session.get(GenerationRunModel, run_b_id)
    assert run_a is not None and run_b is not None
    run_a.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
    run_b.created_at = datetime.now(UTC).replace(tzinfo=None)
    await db_session.commit()

    _bind_source_context(monkeypatch, source_a)

    class PoisonedDispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        async def run_one(self, **_kwargs):
            raise RuntimeError(
                "item key is already bound to a different work-item identity"
            )

    monkeypatch.setattr(worker, "SharedSectionDispatcher", PoisonedDispatcher)

    sourcebook_calls: list[str] = []

    async def execute_sourcebook(job, **_kwargs):
        sourcebook_calls.append(job.work_item_id)
        row = await db_session.get(GenerationWorkItemModel, job.work_item_id)
        row.status = "ready"
        row.output_json = {"entries": []}
        row.output_hash = content_hash(row.output_json)

    monkeypatch.setattr(worker, "execute_sourcebook_work_item", execute_sourcebook)

    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-poison")

    # First iteration: Run A is the only eligible candidate (initial section
    # dispatch). Its dispatcher raises unexpectedly, so Run A must be
    # terminalized rather than silently retried as a semantic outcome.
    assert await instance.run_one(db_session)

    failed_run = await db_session.get(GenerationRunModel, run_a_id)
    assert failed_run is not None
    assert failed_run.status == "failed_terminal"
    assert failed_run.error_code == "shared_document_dispatch_error"
    assert failed_run.error_class == "internal_programming"
    assert failed_run.recovery_action == "none"
    assert failed_run.error_summary is not None
    assert "RuntimeError" not in failed_run.error_summary
    assert "already bound" not in failed_run.error_summary

    diagnostic = await db_session.scalar(
        select(GenerationEventModel).where(
            GenerationEventModel.run_id == run_a_id,
            GenerationEventModel.event_type == "shared_document_dispatch_error_diagnostic",
        )
    )
    assert diagnostic is not None
    assert diagnostic.safe_payload_json == {"original_exception_type": "RuntimeError"}

    # Second iteration: Run B (a fresh Run queued at sourcebook_generation)
    # must now be dispatched -- it must not have starved behind Run A.
    assert await instance.run_one(db_session)
    assert sourcebook_calls == [admission_b.sourcebook_work_item.id]


@pytest.mark.asyncio
async def test_transient_dispatch_failure_backs_off_without_terminalizing(
    db_session, monkeypatch
):
    """A poisoned Run's dispatch failure must not starve a fresh queued Run.

    Regression for the live incident: a WorkItemConflict raised from section
    dispatch every iteration, and the worker only logged and retried the
    same Run, starving every other queued Run.
    """
    generation_a, lesson_a, _prov_a, source_a = await _prepared(db_session, user_id="owner-transient-a")
    generation_b, lesson_b, _prov_b, source_b = await _prepared(db_session, user_id="owner-transient-b")

    admission_a, _task_a = await _ready_semantic_dependencies(
        db_session,
        source=source_a,
        lesson=lesson_a,
        generation=generation_a,
        request_key="worker-transient-a",
        owner_user_id="owner-transient-a",
    )
    run_a_id = admission_a.run.id

    admission_b = await _admitted(
        db_session,
        source=source_b,
        lesson=lesson_b,
        generation=generation_b,
        request_key="worker-transient-b",
        owner_user_id="owner-transient-b",
    )
    run_b_id = admission_b.run.id

    # Run A must be older so `_find_candidate` visits it before Run B.
    run_a = await db_session.get(GenerationRunModel, run_a_id)
    run_b = await db_session.get(GenerationRunModel, run_b_id)
    assert run_a is not None and run_b is not None
    run_a.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
    run_b.created_at = datetime.now(UTC).replace(tzinfo=None)
    await db_session.commit()

    _bind_source_context(monkeypatch, source_a)

    class PoisonedDispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        async def run_one(self, **_kwargs):
            from sqlalchemy.exc import OperationalError

            raise OperationalError("SELECT 1", {}, Exception("connection reset"))

    monkeypatch.setattr(worker, "SharedSectionDispatcher", PoisonedDispatcher)

    sourcebook_calls: list[str] = []

    async def execute_sourcebook(job, **_kwargs):
        sourcebook_calls.append(job.work_item_id)
        row = await db_session.get(GenerationWorkItemModel, job.work_item_id)
        row.status = "ready"
        row.output_json = {"entries": []}
        row.output_hash = content_hash(row.output_json)

    monkeypatch.setattr(worker, "execute_sourcebook_work_item", execute_sourcebook)

    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-transient")

    # First iteration: Run A is the only eligible candidate (initial section
    # dispatch). Its dispatcher raises unexpectedly, so Run A must be
    # terminalized rather than silently retried as a semantic outcome.
    assert await instance.run_one(db_session)

    still_active = await db_session.get(GenerationRunModel, run_a_id)
    assert still_active is not None
    await db_session.refresh(still_active)
    assert still_active.status != "failed_terminal"
    assert still_active.error_code is None

    # Second iteration: Run B (a fresh Run queued at sourcebook_generation)
    # must now be dispatched -- it must not have starved behind Run A.
    assert await instance.run_one(db_session)
    assert sourcebook_calls == [admission_b.sourcebook_work_item.id]


@pytest.mark.asyncio
async def test_dispatch_failure_with_terminalization_race_still_frees_other_runs(
    db_session, monkeypatch
):
    """Even when terminalizing the poisoned Run itself fails, the in-memory

    fairness guard must still keep the worker from re-picking it forever.
    """
    generation_a, lesson_a, _prov_a, source_a = await _prepared(db_session, user_id="owner-race-a")
    generation_b, lesson_b, _prov_b, source_b = await _prepared(db_session, user_id="owner-race-b")

    admission_a, _task_a = await _ready_semantic_dependencies(
        db_session,
        source=source_a,
        lesson=lesson_a,
        generation=generation_a,
        request_key="worker-race-a",
        owner_user_id="owner-race-a",
    )
    run_a_id = admission_a.run.id
    # A concurrently-admitted, still-active section item makes
    # `fail_run_terminal` raise `InvalidRunTransition`, simulating a race
    # with another in-flight admission/transition.
    db_session.add(
        GenerationWorkItemModel(
            run_id=run_a_id,
            item_key="compose:orient",
            stage="section_composition",
            status="queued",
            input_hash="i" * 64,
            definition_hash="d" * 64,
        )
    )
    await db_session.commit()

    admission_b = await _admitted(
        db_session,
        source=source_b,
        lesson=lesson_b,
        generation=generation_b,
        request_key="worker-race-b",
        owner_user_id="owner-race-b",
    )
    run_b_id = admission_b.run.id

    run_a = await db_session.get(GenerationRunModel, run_a_id)
    run_b = await db_session.get(GenerationRunModel, run_b_id)
    assert run_a is not None and run_b is not None
    run_a.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
    run_b.created_at = datetime.now(UTC).replace(tzinfo=None)
    await db_session.commit()

    _bind_source_context(monkeypatch, source_a)

    class PoisonedDispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        async def run_one(self, **_kwargs):
            raise RuntimeError(
                "item key is already bound to a different work-item identity"
            )

    monkeypatch.setattr(worker, "SharedSectionDispatcher", PoisonedDispatcher)

    sourcebook_calls: list[str] = []

    async def execute_sourcebook(job, **_kwargs):
        sourcebook_calls.append(job.work_item_id)
        row = await db_session.get(GenerationWorkItemModel, job.work_item_id)
        row.status = "ready"
        row.output_json = {"entries": []}
        row.output_hash = content_hash(row.output_json)

    monkeypatch.setattr(worker, "execute_sourcebook_work_item", execute_sourcebook)

    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-race")

    assert await instance.run_one(db_session)

    # Terminalization itself failed (an active work item is still
    # queued/running), so the Run must be left exactly as it was -- not
    # silently marked failed, and not left retriable as a semantic outcome.
    raced_run = await db_session.get(GenerationRunModel, run_a_id)
    assert raced_run is not None
    assert raced_run.status in {"queued", "running"}
    assert raced_run.error_code is None

    diagnostic = await db_session.scalar(
        select(GenerationEventModel).where(
            GenerationEventModel.run_id == run_a_id,
            GenerationEventModel.event_type == "shared_document_dispatch_error_diagnostic",
        )
    )
    assert diagnostic is None

    # Even though Run A could not be terminalized, the bounded skip set
    # must still keep it from starving Run B on the next iteration.
    assert await instance.run_one(db_session)
    assert sourcebook_calls == [admission_b.sourcebook_work_item.id]


@pytest.mark.asyncio
async def test_dispatch_cancelled_error_propagates_without_terminalizing(db_session, monkeypatch):
    generation, lesson, _prov, source = await _prepared(db_session, user_id="owner-cancel")
    admission, _task = await _ready_semantic_dependencies(
        db_session,
        source=source,
        lesson=lesson,
        generation=generation,
        request_key="worker-cancel",
        owner_user_id="owner-cancel",
    )
    run_id = admission.run.id
    _bind_source_context(monkeypatch, source)

    class CancellingDispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        async def run_one(self, **_kwargs):
            raise asyncio.CancelledError()

    monkeypatch.setattr(worker, "SharedSectionDispatcher", CancellingDispatcher)
    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-cancel")

    with pytest.raises(asyncio.CancelledError):
        await instance.run_one(db_session)

    run = await db_session.get(GenerationRunModel, run_id)
    assert run is not None
    assert run.status in {"queued", "running"}
    assert run.error_code is None
    now = datetime.now(UTC).replace(tzinfo=None)
    assert instance._is_dispatch_skipped(run_id, now) is False


def test_dispatch_failure_skip_set_is_bounded():
    instance = worker.SharedDocumentWorker(lambda: None, worker_id="worker-bounds")
    now = datetime.now(UTC).replace(tzinfo=None)
    cap = instance._DISPATCH_FAILURE_SKIP_MAX_ENTRIES
    for index in range(cap + 5):
        instance._mark_dispatch_failure(f"run-{index}", now)
    assert len(instance._dispatch_failure_skip_until) <= cap
