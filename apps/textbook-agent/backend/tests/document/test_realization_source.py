from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import func, select, update
from test_shared_document_full_run import _advance_semantic_worker
from test_shared_lesson_approved_source import _prepared

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.post_section_pipeline import run_post_section_pipeline
from document.shared_lesson.realization_source import (
    RealizationAttemptsExhausted,
    RealizationSourceNotFound,
    ensure_shared_document_run,
    load_realization_source,
)
from infra.database.models import (
    GenerationRunModel,
    SharedLessonDocumentModel,
)


async def _drive_to_ready(db_session, db_session_factory, monkeypatch, *, generation, lesson):
    run = await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )
    run_id = run.id
    await db_session.commit()

    await _advance_semantic_worker(
        db_session,
        db_session_factory,
        generation=generation,
        lesson=lesson,
        monkeypatch=monkeypatch,
    )

    async def qa_pass(_request):
        return DocumentSemanticVerdict(status="pass")

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=run_id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=qa_pass,
        worker_id="realization-source-ready-worker",
    )
    assert outcome.state == "ready", outcome.error
    return run_id


async def _approve_new_revision(db_session, *, generation, plan, revision: int, owner: str):
    """Record and approve a new Teaching Plan revision on the same generation."""
    state = deepcopy(generation.chunked_state_json)
    page_state = state["page_document_v2"]
    store = TeachingRevisionStore(page_state)
    new_plan = plan.model_copy(update={"arc": f"A revised arc for revision {revision}."})
    store.record_draft(new_plan, preparation_hash="preparation-hash", revision=revision)
    store.approve(
        expected_revision=revision,
        expected_content_hash=teaching_plan_content_hash(
            new_plan.model_copy(update={"teaching_plan_id": plan.teaching_plan_id, "revision": revision})
        ),
        reviewed_by=owner,
    )
    generation.chunked_state_json = state
    await db_session.flush()


@pytest.mark.asyncio
async def test_ensure_is_idempotent_across_repeated_calls(db_session) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)

    first = await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )
    await db_session.commit()
    second = await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )

    assert second.id == first.id
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationRunModel)
            .where(GenerationRunModel.owner_user_id == "source-owner")
        )
        == 1
    )


@pytest.mark.asyncio
async def test_ensure_admits_new_attempt_after_terminal_run(db_session) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)

    first = await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )
    await db_session.commit()

    first_row = await db_session.get(GenerationRunModel, first.id)
    first_row.status = "failed_terminal"
    await db_session.commit()

    second = await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )
    await db_session.commit()

    assert second.id != first.id
    assert second.request_key == f"{first.request_key}:attempt-2"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationRunModel)
            .where(GenerationRunModel.owner_user_id == "source-owner")
        )
        == 2
    )

    # Repeating ensure again is idempotent at the new attempt.
    third = await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )
    assert third.id == second.id


@pytest.mark.asyncio
async def test_ensure_raises_after_max_terminal_attempts(db_session) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)

    for _ in range(3):
        run = await ensure_shared_document_run(
            db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
        )
        await db_session.commit()
        row = await db_session.get(GenerationRunModel, run.id)
        row.status = "failed_terminal"
        await db_session.commit()

    with pytest.raises(RealizationAttemptsExhausted):
        await ensure_shared_document_run(
            db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
        )

    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationRunModel)
            .where(GenerationRunModel.owner_user_id == "source-owner")
        )
        == 3
    )


@pytest.mark.asyncio
async def test_load_pending_before_any_worker_progress(db_session) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)
    await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )
    await db_session.commit()

    result = await load_realization_source(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )

    assert result.state == "pending"
    assert result.pending is not None
    assert result.pending.status == "queued"
    assert result.pending.stage == "sourcebook_generation"


@pytest.mark.asyncio
async def test_load_ready_recomputes_hash_and_binds_media(
    db_session, db_session_factory, monkeypatch
) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session)
    run_id = await _drive_to_ready(
        db_session, db_session_factory, monkeypatch, generation=generation, lesson=lesson
    )

    async with db_session_factory() as verify:
        result = await load_realization_source(
            verify, owner_user_id="source-owner", path_lesson_id=lesson.id
        )

    assert result.state == "ready", result.failed
    assert result.ready is not None
    assert result.ready.run_id == run_id
    assert result.ready.document.content_hash == result.ready.content_hash
    assert result.ready.plan_id == source.plan.teaching_plan_id
    assert result.ready.plan_revision == 1
    assert result.ready.media_results == ()


@pytest.mark.usefixtures("blocking_quality_gate")
@pytest.mark.asyncio
async def test_load_needs_review_on_semantic_issue(
    db_session, db_session_factory, monkeypatch
) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)
    run = await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )
    run_id = run.id
    await db_session.commit()

    await _advance_semantic_worker(
        db_session,
        db_session_factory,
        generation=generation,
        lesson=lesson,
        monkeypatch=monkeypatch,
    )

    async def qa_issue(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                ContinuityIssue(
                    issue_code="must_establish_uncovered",
                    affected_section_id="orient",
                    explanation="The section never establishes root uptake.",
                    required_correction="Add a sentence establishing root uptake.",
                ),
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=run_id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=qa_issue,
        worker_id="realization-source-review-worker",
    )
    assert outcome.state == "blocked"

    async with db_session_factory() as verify:
        result = await load_realization_source(
            verify, owner_user_id="source-owner", path_lesson_id=lesson.id
        )

    assert result.state == "needs_review"
    assert result.needs_review is not None
    assert result.needs_review.run_id == run_id


@pytest.mark.asyncio
async def test_advisory_semantic_issue_reaches_ready_with_flags_and_learn_print_source(
    db_session, db_session_factory, monkeypatch
) -> None:
    """Advisory gate: a semantic finding is a flag; the doc is READY for Learn/Print."""
    generation, lesson, _provenance, _source = await _prepared(db_session)
    run = await ensure_shared_document_run(
        db_session, owner_user_id="source-owner", path_lesson_id=lesson.id
    )
    run_id = run.id
    await db_session.commit()

    await _advance_semantic_worker(
        db_session,
        db_session_factory,
        generation=generation,
        lesson=lesson,
        monkeypatch=monkeypatch,
    )

    async def qa_issue(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                ContinuityIssue(
                    issue_code="must_establish_uncovered",
                    affected_section_id="orient",
                    explanation="The section never establishes root uptake.",
                    required_correction="Add a sentence establishing root uptake.",
                ),
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=run_id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=qa_issue,
        worker_id="realization-source-advisory-worker",
    )
    assert outcome.state == "ready", outcome

    async with db_session_factory() as verify:
        result = await load_realization_source(
            verify, owner_user_id="source-owner", path_lesson_id=lesson.id
        )

    assert result.state == "ready", result
    assert result.ready is not None
    assert result.ready.run_id == run_id
    # The document identity is untouched by flags.
    assert result.ready.document.content_hash == result.ready.content_hash
    [flag] = result.ready.quality_flags
    assert flag.code == "must_establish_uncovered"
    assert flag.source == "semantic_qa"
    assert flag.section_id == "orient"
    assert flag.required_correction == "Add a sentence establishing root uptake."


@pytest.mark.asyncio
async def test_load_stale_after_new_approved_revision(
    db_session, db_session_factory, monkeypatch
) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session)
    run_id = await _drive_to_ready(
        db_session, db_session_factory, monkeypatch, generation=generation, lesson=lesson
    )

    async with db_session_factory() as writer:
        gen_row = await writer.get(type(generation), generation.id)
        await _approve_new_revision(
            writer, generation=gen_row, plan=source.plan, revision=2, owner="source-owner"
        )
        await writer.commit()

    async with db_session_factory() as verify:
        result = await load_realization_source(
            verify, owner_user_id="source-owner", path_lesson_id=lesson.id
        )

    assert result.state == "stale"
    assert result.stale is not None
    assert result.stale.run_id == run_id


@pytest.mark.asyncio
async def test_load_foreign_owner_is_not_found(db_session) -> None:
    _generation, lesson, _provenance, _source = await _prepared(db_session)

    with pytest.raises(RealizationSourceNotFound):
        await load_realization_source(
            db_session, owner_user_id="a-different-owner", path_lesson_id=lesson.id
        )

    with pytest.raises(RealizationSourceNotFound):
        await load_realization_source(
            db_session, owner_user_id="source-owner", path_lesson_id="unknown-lesson"
        )


@pytest.mark.asyncio
async def test_load_rejects_tampered_stored_document_hash(
    db_session, db_session_factory, monkeypatch
) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)
    await _drive_to_ready(
        db_session, db_session_factory, monkeypatch, generation=generation, lesson=lesson
    )

    # The ORM mapper rejects any UPDATE against an already-READY document
    # (see ``_reject_shared_lesson_document_update``), so simulate tampering
    # at the storage layer directly with a Core-level statement that bypasses
    # the mapper event, exactly like a corrupted row would look on read-back.
    async with db_session_factory() as writer:
        row = await writer.scalar(select(SharedLessonDocumentModel))
        assert row is not None
        await writer.execute(
            update(SharedLessonDocumentModel)
            .where(
                SharedLessonDocumentModel.id == row.id,
                SharedLessonDocumentModel.revision == row.revision,
            )
            .values(content_hash="f" * 64)
        )
        await writer.commit()

    async with db_session_factory() as verify:
        result = await load_realization_source(
            verify, owner_user_id="source-owner", path_lesson_id=lesson.id
        )

    assert result.state == "failed"
    assert result.failed is not None
    assert result.failed.error_code == "REALIZATION_DOCUMENT_INVALID"
