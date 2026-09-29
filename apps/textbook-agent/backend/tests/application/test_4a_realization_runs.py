"""Option D 4A: Learn/Print realization jobs run on the shared generation runtime.

Covers dispatch (no Run while the document is not READY, idempotent Run
admission once it is), execution/finalization, typed failure and bounded retry,
the single status projection, legacy rows, and lease reclaim.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from tests.application.test_p03_realization_gates import _approved_native_preparation
from tests.application.test_p04_learn_worker import _drive_shared_document_ready

from application.unit_lesson.realization_worker import RealizationWorker
from application.unit_lesson.realize_learn_handoff import (
    realize_learn_from_preparation,
    retry_learn_realization,
)
from application.unit_lesson.realize_print_handoff import (
    realize_print_from_preparation,
    retry_print_realization,
)
from application.unit_lesson.realizations import to_identity
from core.database.models import EditableLessonModel, GenerationModel, NativeRealizationModel
from infra.database.models import (
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)


def _naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _admit(db_session: AsyncSession, path: str, *, user_id: str):
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id=user_id
    )
    admit = realize_learn_from_preparation if path == "learn" else realize_print_from_preparation
    admitted = await admit(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id=user_id,
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    return lesson, admitted


async def _make_doc_ready(db_session, db_session_factory, lesson, *, user_id: str) -> str:
    return await _drive_shared_document_ready(
        db_session,
        db_session_factory,
        owner_user_id=user_id,
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
    )


async def _tick(worker: RealizationWorker, factory, *, now: datetime | None = None) -> bool:
    async with factory() as session:
        progressed = await worker.run_one(session, now=now)
        await session.commit()
    return progressed


async def _row(factory, realization_id: str) -> NativeRealizationModel:
    async with factory() as session:
        row = await session.get(NativeRealizationModel, realization_id)
        assert row is not None
        session.expunge(row)
        return row


async def _runs(factory, run_type: str) -> list[GenerationRunModel]:
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(GenerationRunModel).where(GenerationRunModel.run_type == run_type)
                )
            ).all()
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["learn", "print"])
async def test_doc_not_ready_admits_no_run_and_does_not_busy_loop(
    db_session: AsyncSession, db_session_factory, path: str
) -> None:
    user_id = f"4a-wait-{path}"
    _lesson, admitted = await _admit(db_session, path, user_id=user_id)
    worker = RealizationWorker(db_session_factory, worker_id=f"4a-wait-{path}")

    first = await _tick(worker, db_session_factory)  # first observation records "pending"
    second = await _tick(worker, db_session_factory)
    third = await _tick(worker, db_session_factory)

    assert second is False and third is False  # nothing to do: the loop may sleep
    del first
    row = await _row(db_session_factory, admitted["realization_id"])
    assert row.status == "queued"
    assert row.generation_run_id is None
    assert row.shared_document_state == "pending"
    assert await _runs(db_session_factory, path) == []
    async with db_session_factory() as session:
        leases = await session.scalar(
            select(func.count()).select_from(GenerationWorkItemModel).where(
                GenerationWorkItemModel.lease_owner.is_not(None)
            )
        )
    assert leases == 0


@pytest.mark.asyncio
async def test_doc_awaiting_review_projects_needs_shared_review(
    db_session: AsyncSession, db_session_factory
) -> None:
    from document.shared_lesson.continuity import ContinuityIssue
    from document.shared_lesson.document_semantic import DocumentSemanticVerdict
    from document.shared_lesson.post_section_pipeline import run_post_section_pipeline
    from document.shared_lesson.worker import SharedDocumentWorker
    from tests.application.test_p04_learn_worker import (
        _shared_document_composer,
        _shared_document_writer,
        _SharedDocumentSourcebookProvider,
    )

    user_id = "4a-review"
    lesson, admitted = await _admit(db_session, "learn", user_id=user_id)
    row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    doc_run_id = row.shared_document_run_id
    assert doc_run_id is not None

    doc_worker = SharedDocumentWorker(
        db_session_factory,
        worker_id="4a-review-doc",
        provider=_SharedDocumentSourcebookProvider(),
        composer_provider=_shared_document_composer,
        writer_provider=_shared_document_writer,
    )
    for _ in range(4):
        async with db_session_factory() as session:
            progressed = await doc_worker.run_one(session)
            await session.commit()
        if not progressed:
            break

    async def _qa_issue(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                ContinuityIssue(
                    issue_code="must_establish_uncovered",
                    affected_section_id="orient",
                    explanation="The section never establishes the target state.",
                    required_correction="Add a sentence establishing the target state.",
                ),
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=doc_run_id,
        owner_user_id=user_id,
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
        qa_semantic_validator=_qa_issue,
        worker_id="4a-review-post-section",
    )
    assert outcome.state == "blocked"

    worker = RealizationWorker(db_session_factory, worker_id="4a-review-worker")
    await _tick(worker, db_session_factory)
    row = await _row(db_session_factory, admitted["realization_id"])
    assert row.status == "needs_shared_review"
    assert row.generation_run_id is None
    assert row.shared_document_state == "needs_review"
    assert await _runs(db_session_factory, "learn") == []
    identity = to_identity(row)
    assert identity.recovery_action == "review"
    # Repeated ticks stay quiet.
    assert await _tick(worker, db_session_factory) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["learn", "print"])
async def test_doc_ready_admits_run_on_doc_build_executes_and_finalizes(
    db_session: AsyncSession, db_session_factory, path: str
) -> None:
    user_id = f"4a-ready-{path}"
    lesson, admitted = await _admit(db_session, path, user_id=user_id)
    doc_run_id = await _make_doc_ready(db_session, db_session_factory, lesson, user_id=user_id)
    worker = RealizationWorker(db_session_factory, worker_id=f"4a-ready-{path}")

    assert await _tick(worker, db_session_factory) is True  # admit + execute

    row = await _row(db_session_factory, admitted["realization_id"])
    assert row.status == "ready", row.error_summary
    assert row.generation_run_id is not None
    async with db_session_factory() as session:
        doc_run = await session.get(GenerationRunModel, doc_run_id)
        run = await session.get(GenerationRunModel, row.generation_run_id)
        assert run is not None and doc_run is not None
        assert run.run_type == path
        assert run.build_id == doc_run.build_id  # one timeline
        assert run.status == "ready"
        assert (
            run.source_artifact_type,
            run.source_artifact_id,
            run.source_revision,
            run.source_hash,
        ) == (
            doc_run.output_artifact_type,
            doc_run.output_artifact_id,
            doc_run.output_revision,
            doc_run.output_hash,
        )
        assert run.request_key == f"{path}-realization:{row.id}:{row.realization_revision}"
        assert run.output_artifact_type == f"{path}_output"
        assert run.output_artifact_id == row.output_id
        assert run.output_revision == row.realization_revision
        item = await session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run.id)
        )
        assert item is not None
        assert item.item_key == f"{path}:realize"
        assert item.status == "ready"
        assert item.output_json["output_id"] == row.output_id
        output = await session.get(GenerationModel, row.output_id)
        assert output is not None and output.document_json
        assert output.status == ("completed" if path == "learn" else "ready")
        builds = await session.scalar(
            select(func.count()).select_from(GenerationBuildModel)
        )
        assert builds == 1
    identity = to_identity(row)
    assert identity.status == "ready"
    assert identity.run_id == row.generation_run_id


@pytest.mark.asyncio
async def test_admission_is_idempotent_across_ticks_and_workers(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "4a-idem"
    lesson, admitted = await _admit(db_session, "learn", user_id=user_id)
    await _make_doc_ready(db_session, db_session_factory, lesson, user_id=user_id)
    worker_a = RealizationWorker(db_session_factory, worker_id="4a-idem-a")
    worker_b = RealizationWorker(db_session_factory, worker_id="4a-idem-b")

    await _tick(worker_a, db_session_factory)
    await _tick(worker_b, db_session_factory)
    await _tick(worker_a, db_session_factory)

    assert len(await _runs(db_session_factory, "learn")) == 1
    row = await _row(db_session_factory, admitted["realization_id"])
    assert row.status == "ready"
    async with db_session_factory() as session:
        editables = await session.scalar(
            select(func.count()).select_from(EditableLessonModel)
        )
    assert editables == 1


class _FlakyOnce:
    """Raise a transient DB error the first ``n`` calls, then delegate."""

    def __init__(self, real, n: int = 1) -> None:
        self.real = real
        self.remaining = n
        self.calls = 0

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise OperationalError("SELECT 1", {}, Exception("connection reset"))
        return await self.real(*args, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["learn", "print"])
async def test_typed_retryable_failure_then_retry_route_reaches_ready(
    db_session: AsyncSession, db_session_factory, monkeypatch, path: str
) -> None:
    user_id = f"4a-retry-{path}"
    lesson, admitted = await _admit(db_session, path, user_id=user_id)
    await _make_doc_ready(db_session, db_session_factory, lesson, user_id=user_id)

    target = (
        "learn.generation.shared_document_execution"
        if path == "learn"
        else "print.generation.shared_document_execution"
    )
    import importlib

    module = importlib.import_module(target)
    name = (
        "materialize_learn_output_from_shared_document"
        if path == "learn"
        else "materialize_print_output_from_shared_document"
    )
    flaky = _FlakyOnce(getattr(module, name), n=1)
    monkeypatch.setattr(module, name, flaky)

    worker = RealizationWorker(db_session_factory, worker_id=f"4a-retry-{path}")
    await _tick(worker, db_session_factory)

    row = await _row(db_session_factory, admitted["realization_id"])
    assert row.status == "failed_recoverable"
    assert row.generation_run_id is not None
    identity = to_identity(row)
    assert identity.recovery_action == "retry"
    assert identity.run_id == row.generation_run_id
    async with db_session_factory() as session:
        run = await session.get(GenerationRunModel, row.generation_run_id)
        assert run.status == "failed_recoverable"
        item = await session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run.id)
        )
        assert item.error_class == "provider_transport"
        assert item.recovery_action == "retry"

    retry = retry_learn_realization if path == "learn" else retry_print_realization
    async with db_session_factory() as session:
        result = await retry(session, realization_id=row.id, user_id=user_id)
        await session.commit()
    assert result["status"] == "queued"
    reopened = await _row(db_session_factory, row.id)
    assert reopened.status == "queued"
    assert reopened.generation_run_id == row.generation_run_id  # same Run, retried in place
    assert reopened.realization_revision == row.realization_revision

    await _tick(worker, db_session_factory)
    final = await _row(db_session_factory, row.id)
    assert final.status == "ready", final.error_summary
    assert len(await _runs(db_session_factory, path)) == 1
    assert flaky.calls == 2


@pytest.mark.asyncio
async def test_terminal_failure_then_retry_bumps_revision_and_admits_new_run(
    db_session: AsyncSession, db_session_factory, monkeypatch
) -> None:
    user_id = "4a-terminal"
    lesson, admitted = await _admit(db_session, "learn", user_id=user_id)
    await _make_doc_ready(db_session, db_session_factory, lesson, user_id=user_id)

    import learn.generation.shared_document_execution as learn_exec
    from learn.generation.shared_document_adapter import SharedDocumentLearnMappingError

    real = learn_exec.materialize_learn_output_from_shared_document
    state = {"fail": True}

    async def _maybe_fail(*args, **kwargs):
        if state["fail"]:
            raise SharedDocumentLearnMappingError("unsupported block")
        return await real(*args, **kwargs)

    monkeypatch.setattr(learn_exec, "materialize_learn_output_from_shared_document", _maybe_fail)
    worker = RealizationWorker(db_session_factory, worker_id="4a-terminal")
    await _tick(worker, db_session_factory)

    failed = await _row(db_session_factory, admitted["realization_id"])
    assert failed.status == "failed_terminal"
    first_run_id = failed.generation_run_id
    assert to_identity(failed).recovery_action == "regenerate"
    async with db_session_factory() as session:
        item = await session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == first_run_id)
        )
        assert item.error_class == "validation"
        assert item.status == "failed_terminal"

    state["fail"] = False
    async with db_session_factory() as session:
        result = await retry_learn_realization(session, realization_id=failed.id, user_id=user_id)
        await session.commit()
    assert result["status"] == "queued"
    bumped = await _row(db_session_factory, failed.id)
    assert bumped.realization_revision == failed.realization_revision + 1
    assert bumped.generation_run_id is None
    assert bumped.output_id != failed.output_id

    await _tick(worker, db_session_factory)
    final = await _row(db_session_factory, failed.id)
    assert final.status == "ready", final.error_summary
    assert final.generation_run_id not in {None, first_run_id}
    assert len(await _runs(db_session_factory, "learn")) == 2


@pytest.mark.asyncio
async def test_legacy_midflight_row_projects_terminal_regenerate_and_retry_recovers(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "4a-legacy"
    lesson, admitted = await _admit(db_session, "learn", user_id=user_id)
    row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    row.status = "running"  # left mid-flight by the retired Learn worker
    row.generation_run_id = None
    await db_session.commit()

    identity = to_identity(await _row(db_session_factory, row.id))
    assert identity.status == "failed_terminal"
    assert identity.recovery_action == "regenerate"
    assert identity.run_id is None
    assert identity.error_summary == "Created before the job update — regenerate this output."

    # The workspace DTO carries the additive fields.
    from curriculum.workspace_projection import project_lesson_workspace

    workspace = project_lesson_workspace(
        generation_id=None,
        learn_realization=identity.model_dump(mode="json"),
    )
    assert workspace.learn.state == "failed_terminal"
    assert workspace.learn.recovery_action == "regenerate"
    assert workspace.learn.run_id is None

    # Queued / ready / stale rows are never legacy.
    for status in ("queued", "ready", "stale", "read_only"):
        async with db_session_factory() as session:
            live = await session.get(NativeRealizationModel, row.id)
            live.status = status
            await session.commit()
        assert to_identity(await _row(db_session_factory, row.id)).status == status

    async with db_session_factory() as session:
        live = await session.get(NativeRealizationModel, row.id)
        live.status = "running"
        await session.commit()
    async with db_session_factory() as session:
        result = await retry_learn_realization(session, realization_id=row.id, user_id=user_id)
        await session.commit()
    assert result["status"] == "queued"
    recovered = await _row(db_session_factory, row.id)
    assert recovered.status == "queued"
    assert recovered.realization_revision == 2


@pytest.mark.asyncio
async def test_expired_lease_is_reclaimed_by_a_second_worker(
    db_session: AsyncSession, db_session_factory, monkeypatch
) -> None:
    user_id = "4a-lease"
    lesson, admitted = await _admit(db_session, "print", user_id=user_id)
    await _make_doc_ready(db_session, db_session_factory, lesson, user_id=user_id)

    import print.generation.shared_document_execution as print_exec

    real = print_exec.materialize_print_output_from_shared_document

    class _Crash(BaseException):
        """Simulate a dead process: nothing after the claim commits."""

    async def _crash(*args, **kwargs):
        raise _Crash()

    monkeypatch.setattr(print_exec, "materialize_print_output_from_shared_document", _crash)
    dead = RealizationWorker(db_session_factory, worker_id="4a-lease-dead", lease_seconds=30)
    start = _naive_now()
    with pytest.raises(_Crash):
        async with db_session_factory() as session:
            await dead.run_one(session, now=start)

    row = await _row(db_session_factory, admitted["realization_id"])
    assert row.generation_run_id is not None
    async with db_session_factory() as session:
        item = await session.scalar(
            select(GenerationWorkItemModel).where(
                GenerationWorkItemModel.run_id == row.generation_run_id
            )
        )
        assert item.status == "running"
        assert item.lease_owner == "4a-lease-dead"
        first_token = item.lease_token

    monkeypatch.setattr(print_exec, "materialize_print_output_from_shared_document", real)
    alive = RealizationWorker(db_session_factory, worker_id="4a-lease-alive", lease_seconds=30)
    # Lease still live: the second worker must not take it (it only projects
    # the Run's "running" state onto the realization).
    await _tick(alive, db_session_factory, now=start + timedelta(seconds=5))
    assert (await _row(db_session_factory, row.id)).status == "running"
    async with db_session_factory() as session:
        held = await session.scalar(
            select(GenerationWorkItemModel).where(
                GenerationWorkItemModel.run_id == row.generation_run_id
            )
        )
        assert held.lease_owner == "4a-lease-dead"
        assert held.lease_token == first_token

    # After expiry it is reclaimed and completed.
    assert await _tick(alive, db_session_factory, now=start + timedelta(seconds=120)) is True
    final = await _row(db_session_factory, row.id)
    assert final.status == "ready", final.error_summary
    async with db_session_factory() as session:
        item = await session.scalar(
            select(GenerationWorkItemModel).where(
                GenerationWorkItemModel.run_id == row.generation_run_id
            )
        )
        assert item.status == "ready"
        assert item.lease_owner == "4a-lease-alive"
        assert item.lease_token > first_token
