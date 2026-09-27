from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_shared_document_full_run import (
    _admit,
    _advance_semantic_worker,
)
from test_shared_lesson_approved_source import _prepared

from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.http import (
    ReviewDraftRevisionRequest,
    ReviewDraftSubmitRequest,
    ReviewDraftTextEdit,
    get_shared_document_review_draft,
    post_shared_document_review_draft_revision,
    post_shared_document_review_draft_submit,
)
from document.shared_lesson.models import build_shared_lesson_document
from document.shared_lesson.post_section_pipeline import run_post_section_pipeline
from document.shared_lesson.repository import save_shared_lesson_document
from fastapi import HTTPException
from infra.database.models import GenerationEventModel, GenerationRunModel


async def _issue_then_edit(db_session, db_session_factory, monkeypatch):
    """Bring a Run to a saved (revision-2) review draft awaiting submission."""
    generation, lesson, _provenance, _source = await _prepared(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)
    await _advance_semantic_worker(
        db_session, db_session_factory, generation=generation, lesson=lesson, monkeypatch=monkeypatch
    )

    async def issue_once(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": "orient",
                    "explanation": "The section assumes an unapproved fact.",
                    "required_correction": "Repair the affected section input.",
                },
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=issue_once,
        worker_id="review-submit-issue",
    )
    assert outcome.state == "blocked"
    assert outcome.stage == "finalization" or outcome.stage == "qa_handoff"

    async with db_session_factory() as session:
        run = await session.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "failed_recoverable"

        draft = await get_shared_document_review_draft(
            run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    section = draft["document"]["sections"][0]
    node = section["nodes"][0]
    assert node["kind"] == "paragraph"

    async with db_session_factory() as session:
        edited = await post_shared_document_review_draft_revision(
            run.id,
            ReviewDraftRevisionRequest(
                expected_revision=draft["draft"]["revision"],
                expected_hash=draft["draft"]["hash"],
                edits=(
                    ReviewDraftTextEdit(
                        section_id=section["id"],
                        node_id=node["id"],
                        field="text",
                        value="Roots take in water through tiny root hairs.",
                    ),
                ),
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()
    assert edited["draft"]["revision"] == draft["draft"]["revision"] + 1
    return admission, generation, lesson, edited


@pytest.mark.asyncio
async def test_review_submit_happy_path_promotes_edited_revision(
    db_session, db_session_factory, monkeypatch
):
    admission, generation, lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )

    async with db_session_factory() as session:
        submit_outcome = await post_shared_document_review_draft_submit(
            admission.run.id,
            ReviewDraftSubmitRequest(
                expected_revision=edited["draft"]["revision"],
                expected_hash=edited["draft"]["hash"],
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()
    assert submit_outcome["document_revision"] == edited["draft"]["revision"]

    async def pass_qa(_request):
        return DocumentSemanticVerdict(status="pass")

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=pass_qa,
        worker_id="review-submit-pass",
    )
    assert outcome.state == "ready", outcome.error

    async with db_session_factory() as verify:
        run = await verify.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "ready"
        assert run.output_revision == edited["draft"]["revision"]
        assert run.output_hash

        events = list(
            (
                await verify.scalars(
                    select(GenerationEventModel).where(
                        GenerationEventModel.run_id == admission.run.id,
                        GenerationEventModel.event_type == "review_revision_promoted",
                    )
                )
            ).all()
        )
        assert len(events) == 1
        assert events[0].safe_payload_json["document_revision"] == edited["draft"]["revision"]


@pytest.mark.asyncio
async def test_review_submit_rejects_stale_expected_hash(
    db_session, db_session_factory, monkeypatch
):
    admission, _generation, _lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )
    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_submit(
                admission.run.id,
                ReviewDraftSubmitRequest(
                    expected_revision=edited["draft"]["revision"],
                    expected_hash="0" * 64,
                ),
                current_user=SimpleNamespace(id="source-owner"),
                session=session,
            )
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_review_submit_rejects_no_edit(db_session, db_session_factory, monkeypatch):
    generation, lesson, _provenance, _source = await _prepared(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)
    await _advance_semantic_worker(
        db_session, db_session_factory, generation=generation, lesson=lesson, monkeypatch=monkeypatch
    )

    async def issue_once(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": "orient",
                    "explanation": "unapproved fact",
                    "required_correction": "repair",
                },
            ),
        )

    await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=issue_once,
        worker_id="review-submit-no-edit",
    )
    async with db_session_factory() as session:
        draft = await get_shared_document_review_draft(
            admission.run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_submit(
                admission.run.id,
                ReviewDraftSubmitRequest(
                    expected_revision=draft["draft"]["revision"],
                    expected_hash=draft["draft"]["hash"],
                ),
                current_user=SimpleNamespace(id="source-owner"),
                session=session,
            )
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_review_submit_rejects_forged_structural_edit(
    db_session, db_session_factory, monkeypatch
):
    admission, _generation, lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )
    async with db_session_factory() as session:
        current = await get_shared_document_review_draft(
            admission.run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    payload = current["document"]
    # Forge a structural change (drop a node) bypassing the proof normally
    # enforced by ``post_shared_document_review_draft_revision``.
    payload["revision"] = current["draft"]["revision"] + 1
    payload["sections"][0]["nodes"] = payload["sections"][0]["nodes"][1:]
    payload.pop("content_hash", None)
    forged = build_shared_lesson_document(payload)
    async with db_session_factory() as session:
        await save_shared_lesson_document(
            session, path_lesson_id=lesson.id, document=forged
        )
        await session.commit()

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_submit(
                admission.run.id,
                ReviewDraftSubmitRequest(
                    expected_revision=forged.revision,
                    expected_hash=forged.content_hash,
                ),
                current_user=SimpleNamespace(id="source-owner"),
                session=session,
            )
    assert excinfo.value.status_code == 422


@pytest.mark.asyncio
async def test_review_submit_rejects_foreign_owner(db_session, db_session_factory, monkeypatch):
    admission, _generation, _lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )
    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_submit(
                admission.run.id,
                ReviewDraftSubmitRequest(
                    expected_revision=edited["draft"]["revision"],
                    expected_hash=edited["draft"]["hash"],
                ),
                current_user=SimpleNamespace(id="someone-else"),
                session=session,
            )
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_review_submit_issue_again_keeps_edited_revision_as_latest_draft(
    db_session, db_session_factory, monkeypatch
):
    admission, generation, lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )
    async with db_session_factory() as session:
        await post_shared_document_review_draft_submit(
            admission.run.id,
            ReviewDraftSubmitRequest(
                expected_revision=edited["draft"]["revision"],
                expected_hash=edited["draft"]["hash"],
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()

    async def issue_again(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": "orient",
                    "explanation": "still unapproved",
                    "required_correction": "repair again",
                },
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=issue_again,
        worker_id="review-submit-issue-again",
    )
    assert outcome.state == "blocked"

    async with db_session_factory() as session:
        run = await session.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "failed_recoverable"
        latest = await get_shared_document_review_draft(
            admission.run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    assert latest["draft"]["revision"] == edited["draft"]["revision"]
    assert latest["draft"]["hash"] == edited["draft"]["hash"]
