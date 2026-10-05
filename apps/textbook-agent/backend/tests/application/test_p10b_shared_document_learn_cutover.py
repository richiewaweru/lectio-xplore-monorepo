"""P10B: Learn creation routes only through a verified SharedLessonDocument.

Covers the closed ``load_realization_source`` state machine end to end from
the Learn admission/worker seam (pending/needs_review/stale/ready), duplicate
admission pinning, lineage stamping, Builder lineage verification on open,
and a monkeypatch proof that the ready path never calls ordinary
composer/writer authoring. The retired ordinary Learn producer
(``learn.generation.native_execution``) no longer exists; an architecture
guard (``tests/architecture/test_p10e_learn_ordinary_authoring_guard.py``)
now proves it stays absent and unreachable from Learn generation.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.application.test_p03_realization_gates import _approved_native_preparation
from tests.application.test_p04_learn_worker import _drive_shared_document_ready

from application.unit_lesson.realization_worker import RealizationWorker
from application.unit_lesson.realize_learn_handoff import realize_learn_from_preparation
from core.database.models import (
    EditableLessonModel,
    GenerationModel,
    NativeRealizationModel,
)
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.auto_retry import scan_and_auto_retry
from infra.database.models import (
    GenerationRunModel,
    GenerationWorkItemModel,
    SharedLessonDocumentModel,
)
from document.shared_lesson.post_section_pipeline import run_post_section_pipeline
from learn.authoring.builder.service import (
    SharedDocumentLineageMismatchError,
    get_or_create_native_learn_builder_lesson,
)


@pytest.mark.asyncio
async def test_duplicate_admission_reuses_same_shared_document_run_pin(
    db_session: AsyncSession,
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p10b-duplicate-admit"
    )

    first = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-duplicate-admit",
        path_lesson_id=lesson.id,
        admission_request_key="admit-once",
    )
    second = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-duplicate-admit",
        path_lesson_id=lesson.id,
        admission_request_key="admit-once",
    )

    assert first["realization_id"] == second["realization_id"]
    row = await db_session.get(NativeRealizationModel, first["realization_id"])
    assert row is not None
    assert row.shared_document_run_id is not None

    # Re-admitting under a different idempotency key for the same lesson still
    # resolves the identical deterministic SharedDocument request key, so the
    # same Run is reused rather than a second one being admitted.
    third = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-duplicate-admit",
        path_lesson_id=lesson.id,
        admission_request_key="admit-once",
    )
    row_again = await db_session.get(NativeRealizationModel, third["realization_id"])
    assert row_again is not None
    assert row_again.shared_document_run_id == row.shared_document_run_id


@pytest.mark.asyncio
async def test_worker_reports_pending_without_consuming_an_attempt(
    db_session: AsyncSession, db_session_factory
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p10b-pending"
    )
    admitted = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-pending",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    assert row is not None
    assert row.status == "queued"

    worker = RealizationWorker(db_session_factory, worker_id="p10b-pending-worker")
    async with db_session_factory() as worker_session:
        await worker.run_one(worker_session)
    await db_session.refresh(row)
    assert row.status == "queued"  # no Run, no lease, no attempt consumed
    assert row.generation_run_id is None
    assert row.shared_document_state == "pending"
    assert row.realization_revision == 1


@pytest.mark.asyncio
async def test_failed_media_leaf_projects_failed_recoverable_then_auto_retry_requeues(
    db_session: AsyncSession, db_session_factory
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p10b-media-failed"
    )
    admitted = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-media-failed",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    assert row is not None and row.shared_document_run_id
    run_id = row.shared_document_run_id

    run = await db_session.get(GenerationRunModel, run_id)
    for item in (
        await db_session.scalars(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run_id)
        )
    ).all():
        item.status = "ready"
        item.output_json = {"ok": True}
        item.output_hash = "f" * 64
    db_session.add(
        GenerationWorkItemModel(
            run_id=run_id,
            item_key="media:fig-1",
            stage="media_generation",
            status="failed_recoverable",
            attempt=1,
            max_attempts=3,
            input_hash="d" * 64,
            definition_hash="e" * 64,
            error_code="provider_http_503",
            error_class="provider_transport",
            error_summary="Figure generation failed: the image provider had a temporary problem (HTTP 503).",
            recovery_action="retry",
        )
    )
    run.status = "failed_recoverable"
    await db_session.commit()

    worker = RealizationWorker(db_session_factory, worker_id="p10b-media-failed-worker")
    async with db_session_factory() as tick:
        await worker.run_one(tick)
    await db_session.refresh(row)
    assert row.status == "failed_recoverable"  # truthful: not "queued"
    assert row.shared_document_state == "recoverable"
    assert row.error_summary.startswith("provider_http_503: Figure generation failed")
    assert row.generation_run_id is None

    # The bounded auto-retry (scans Runs, not realizations) requeues the leaf...
    async with db_session_factory() as retry_session:
        retried = await scan_and_auto_retry(retry_session, delay_seconds=0)
    assert retried == 1
    # ...and the realization follows the Run back to queued on the next tick.
    async with db_session_factory() as tick:
        await worker.run_one(tick)
    await db_session.refresh(row)
    assert row.status == "queued"
    assert row.shared_document_state == "pending"
    assert row.error_summary is None


@pytest.mark.usefixtures("blocking_quality_gate")
@pytest.mark.asyncio
async def test_worker_reports_needs_shared_review_without_authoring(
    db_session: AsyncSession, db_session_factory
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p10b-needs-review"
    )
    admitted = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-needs-review",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    assert row is not None
    run_id = row.shared_document_run_id
    assert run_id is not None

    from tests.application.test_p04_learn_worker import (
        _shared_document_composer,
        _shared_document_writer,
        _SharedDocumentSourcebookProvider,
    )
    from document.shared_lesson.worker import SharedDocumentWorker

    worker = SharedDocumentWorker(
        db_session_factory,
        worker_id="p10b-needs-review-worker",
        provider=_SharedDocumentSourcebookProvider(),
        composer_provider=_shared_document_composer,
        writer_provider=_shared_document_writer,
    )
    for _ in range(4):
        async with db_session_factory() as session:
            progressed = await worker.run_one(session)
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
        run_id=run_id,
        owner_user_id="p10b-needs-review",
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
        qa_semantic_validator=_qa_issue,
        worker_id="p10b-needs-review-post-section",
    )
    assert outcome.state == "blocked"

    realization_worker = RealizationWorker(
        db_session_factory, worker_id="p10b-needs-review-learn-worker"
    )
    async with db_session_factory() as tick_session:
        await realization_worker.run_one(tick_session)
    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        assert row.status == "needs_shared_review"
        assert row.shared_document_state == "needs_review"
        assert row.generation_run_id is None


@pytest.mark.asyncio
async def test_advisory_quality_flags_let_learn_realize_and_are_readable_from_editor(
    db_session: AsyncSession, db_session_factory
) -> None:
    """Advisory gate: a semantic finding no longer parks Learn; it is a flag."""
    from types import SimpleNamespace

    from document.shared_lesson.http import get_shared_document_quality_flags
    from document.shared_lesson.worker import SharedDocumentWorker
    from tests.application.test_p04_learn_worker import (
        _shared_document_composer,
        _shared_document_writer,
        _SharedDocumentSourcebookProvider,
    )

    user_id = "p10b-advisory"
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id=user_id
    )
    admitted = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id=user_id,
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    assert row is not None
    run_id = row.shared_document_run_id
    assert run_id is not None

    worker = SharedDocumentWorker(
        db_session_factory,
        worker_id="p10b-advisory-worker",
        provider=_SharedDocumentSourcebookProvider(),
        composer_provider=_shared_document_composer,
        writer_provider=_shared_document_writer,
    )
    for _ in range(4):
        async with db_session_factory() as session:
            progressed = await worker.run_one(session)
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
        run_id=run_id,
        owner_user_id=user_id,
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
        qa_semantic_validator=_qa_issue,
        worker_id="p10b-advisory-post-section",
    )
    assert outcome.state == "ready", outcome

    realization_worker = RealizationWorker(db_session_factory, worker_id="p10b-advisory-learn")
    async with db_session_factory() as tick_session:
        assert await realization_worker.run_one(tick_session) is True

    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        assert row is not None
        assert row.status == "ready"
        assert row.shared_document_state == "ready"
        output = await verify.get(GenerationModel, row.output_id)
        assert output is not None and output.status == "completed"
        editable = await verify.scalar(
            select(EditableLessonModel).where(EditableLessonModel.source_generation_id == output.id)
        )
        assert editable is not None

        for kwargs in ({"editable_lesson_id": editable.id}, {"generation_id": output.id}):
            payload = await get_shared_document_quality_flags(
                current_user=SimpleNamespace(id=user_id), session=verify, **kwargs
            )
            assert payload["run_id"] == run_id
            assert [f["code"] for f in payload["flags"]] == ["must_establish_uncovered"]
            assert payload["flags"][0]["section_id"] == "orient"
            assert payload["flags"][0]["severity"] == "warning"

        foreign = await get_shared_document_quality_flags(
            editable_lesson_id=editable.id,
            current_user=SimpleNamespace(id="someone-else"),
            session=verify,
        )
        assert foreign == {"run_id": None, "flags": []}


@pytest.mark.asyncio
async def test_worker_reports_stale_after_new_approved_revision(
    db_session: AsyncSession, db_session_factory
) -> None:
    lesson, plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p10b-stale"
    )
    admitted = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-stale",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    await _drive_shared_document_ready(
        db_session,
        db_session_factory,
        owner_user_id="p10b-stale",
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
    )

    async with db_session_factory() as writer:
        generation = await writer.get(GenerationModel, str(lesson.pack_id))
        assert generation is not None
        state = deepcopy(generation.chunked_state_json)
        page_state = state["page_document_v2"]
        store = TeachingRevisionStore(page_state)
        new_plan = plan.model_copy(update={"arc": "A revised arc for the stale-source test."})
        store.record_draft(new_plan, preparation_hash="preparation-hash", revision=2)
        store.approve(
            expected_revision=2,
            expected_content_hash=teaching_plan_content_hash(
                new_plan.model_copy(update={"revision": 2})
            ),
            reviewed_by="p10b-stale",
        )
        generation.chunked_state_json = state
        await writer.commit()

    stale_worker = RealizationWorker(db_session_factory, worker_id="p10b-stale-worker")
    async with db_session_factory() as tick_session:
        await stale_worker.run_one(tick_session)
    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        assert row.status == "failed_recoverable"
        assert row.shared_document_state == "stale"
        assert row.error_summary is not None
        assert row.error_summary.startswith("SHARED_DOCUMENT_STALE")


@pytest.mark.asyncio
async def test_ready_path_never_calls_ordinary_authoring_or_retired_producer(
    db_session: AsyncSession, db_session_factory, monkeypatch
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p10b-ready-guard"
    )
    admitted = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-ready-guard",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    await _drive_shared_document_ready(
        db_session,
        db_session_factory,
        owner_user_id="p10b-ready-guard",
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
    )

    worker = RealizationWorker(db_session_factory, worker_id="p10b-ready-guard-worker")
    async with db_session_factory() as worker_session:
        assert await worker.run_one(worker_session) is True

    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        assert row is not None
        assert row.status == "ready"
        assert row.shared_document_state == "ready"
        assert row.shared_document_id is not None
        assert row.shared_document_revision is not None
        assert row.shared_document_hash is not None

        output = await verify.get(GenerationModel, row.output_id)
        assert output is not None
        assert output.status == "completed"
        assert output.shared_document_id == row.shared_document_id
        node_kinds = {node["kind"] for node in output.document_json["nodes"]}
        assert "paragraph" in node_kinds

        editable = await verify.scalar(
            select(EditableLessonModel).where(
                EditableLessonModel.source_generation_id == output.id
            )
        )
        assert editable is not None
        assert editable.shared_document_id == row.shared_document_id
        assert editable.shared_document_revision == row.shared_document_revision


@pytest.mark.asyncio
async def test_builder_open_rejects_stamped_lineage_mismatch(
    db_session: AsyncSession, db_session_factory
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p10b-builder-mismatch"
    )
    admitted = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p10b-builder-mismatch",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    await _drive_shared_document_ready(
        db_session,
        db_session_factory,
        owner_user_id="p10b-builder-mismatch",
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
    )
    worker = RealizationWorker(db_session_factory, worker_id="p10b-builder-mismatch-worker")
    async with db_session_factory() as worker_session:
        assert await worker.run_one(worker_session) is True

    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        output = await verify.get(GenerationModel, row.output_id)
        assert output is not None and output.shared_document_id is not None

        # Open succeeds while the stamped lineage still verifies.
        lesson_row = await get_or_create_native_learn_builder_lesson(
            verify, generation=output, user_id="p10b-builder-mismatch"
        )
        assert lesson_row.shared_document_id == output.shared_document_id
        await verify.commit()

        # Tamper the stored SharedLessonDocument content hash directly at the
        # storage layer (the ORM rejects an in-place UPDATE against a READY
        # document through the mapper).
        from sqlalchemy import update as sa_update

        await verify.execute(
            sa_update(SharedLessonDocumentModel)
            .where(
                SharedLessonDocumentModel.id == output.shared_document_id,
                SharedLessonDocumentModel.revision == output.shared_document_revision,
            )
            .values(content_hash="f" * 64)
        )
        await verify.commit()

    async with db_session_factory() as reopen:
        output = await reopen.get(GenerationModel, admitted["output_id"])
        assert output is not None
        with pytest.raises(SharedDocumentLineageMismatchError):
            await get_or_create_native_learn_builder_lesson(
                reopen, generation=output, user_id="p10b-builder-mismatch"
            )
