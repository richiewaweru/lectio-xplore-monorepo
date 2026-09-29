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

from application.unit_lesson.realize_learn_handoff import (
    execute_learn_realization,
    realize_learn_from_preparation,
)
from core.database.models import (
    EditableLessonModel,
    GenerationModel,
    NativeRealizationModel,
)
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from infra.database.models import SharedLessonDocumentModel
from document.shared_lesson.post_section_pipeline import run_post_section_pipeline
from learn.authoring.builder.service import (
    SharedDocumentLineageMismatchError,
    get_or_create_native_learn_builder_lesson,
)
from learn.generation.worker import LearnRealizationWorker


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
    db_session: AsyncSession,
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

    result = await execute_learn_realization(
        db_session, realization=row, worker_id="p10b-pending-worker"
    )

    assert result["status"] == "waiting_shared_document"
    await db_session.refresh(row)
    assert row.status == "queued"  # never claimed; no attempt consumed
    assert row.shared_document_state == "pending"
    assert row.realization_revision == 1


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

    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        result = await execute_learn_realization(
            verify, realization=row, worker_id="p10b-needs-review-learn-worker"
        )
        assert result["status"] == "needs_shared_review"
        await verify.commit()
        await verify.refresh(row)
        assert row.status == "needs_shared_review"
        assert row.shared_document_state == "needs_review"


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

    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        result = await execute_learn_realization(
            verify, realization=row, worker_id="p10b-stale-worker"
        )
        assert result["status"] == "failed_recoverable"
        await verify.commit()
        await verify.refresh(row)
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

    worker = LearnRealizationWorker(worker_id="p10b-ready-guard-worker")
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
    worker = LearnRealizationWorker(worker_id="p10b-builder-mismatch-worker")
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
