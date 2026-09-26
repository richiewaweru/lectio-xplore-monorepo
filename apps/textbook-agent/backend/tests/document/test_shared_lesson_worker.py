from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from test_shared_lesson_approved_source import _prepared

from document.shared_lesson import worker
from document.shared_lesson.approved_source import ApprovedSourceVerificationError
from document.shared_lesson.run_admission import admit_shared_document_run
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import SourceIdentity


def _identity(source) -> SourceIdentity:
    return SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash=source.content_hash,
    )


async def _admitted(db_session, *, source, lesson, generation, request_key: str):
    result = await admit_shared_document_run(
        db_session,
        owner_user_id="source-owner",
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
