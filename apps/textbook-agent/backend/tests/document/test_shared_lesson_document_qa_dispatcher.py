from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_shared_lesson_handoff import _accepted
from test_shared_qa_runtime import _seed_run

from document.shared_lesson.document_qa_dispatcher import (
    SharedDocumentQADispatchError,
    dispatch_shared_document_qa,
)
from document.shared_lesson.http import get_shared_document_review_draft
from infra.database.models import GenerationRunModel, GenerationWorkItemModel


@pytest.mark.asyncio
async def test_dispatcher_assembles_admits_executes_once_and_reloads_pass(
    db_session,
    db_session_factory,
) -> None:
    source, composition, section = _accepted()
    owner, run_id = await _seed_run(db_session, source, suffix="qa-dispatch-success")
    await db_session.commit()
    calls = 0

    async def semantic_validator(_request):
        nonlocal calls
        calls += 1
        from document.shared_lesson.document_semantic import DocumentSemanticVerdict

        return DocumentSemanticVerdict(status="pass")

    result = await dispatch_shared_document_qa(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        compositions=(composition,),
        sections=(section,),
        document_id="qa-dispatch-document",
        document_revision=1,
        created_at="2026-09-26T12:00:00Z",
        semantic_validator=semantic_validator,
    )

    assert calls == 1
    assert result.work_item_id == result.verified_qa.work_item_id
    assert result.verified_qa.semantic_qa.passed
    async with db_session_factory() as check_session:
        item = await check_session.get(GenerationWorkItemModel, result.work_item_id)
        assert item is not None
        assert item.status == "ready"


@pytest.mark.asyncio
async def test_dispatcher_blocks_before_qa_admission_on_deterministic_or_media_failure(
    db_session,
    db_session_factory,
) -> None:
    source, composition, section = _accepted()
    owner, run_id = await _seed_run(db_session, source, suffix="qa-dispatch-blocked")

    with pytest.raises(SharedDocumentQADispatchError, match="compositions"):
        await dispatch_shared_document_qa(
            db_session_factory,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            compositions=(),
            sections=(section,),
            document_id="qa-dispatch-missing-composition",
            document_revision=1,
            created_at="2026-09-26T12:00:00Z",
        )

    with pytest.raises(SharedDocumentQADispatchError, match="required media declaration"):
        await dispatch_shared_document_qa(
            db_session_factory,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            compositions=(composition,),
            sections=(section,),
            document_id="qa-dispatch-missing-media",
            document_revision=1,
            created_at="2026-09-26T12:00:00Z",
            required_media_by_section={"explain": ("figure-1",)},
        )

    async with db_session_factory() as check_session:
        items = list(
            (
                await check_session.scalars(
                    select(GenerationWorkItemModel).where(
                        GenerationWorkItemModel.run_id == run_id,
                        GenerationWorkItemModel.stage == "document_qa",
                    )
                )
            ).all()
        )
        assert items == []


def test_expired_running_document_qa_leaf_is_dispatchable_after_restart():
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from document.shared_lesson.document_qa_dispatcher import _dispatchable

    now = datetime.now(UTC).replace(tzinfo=None)
    assert _dispatchable(SimpleNamespace(status="queued", lease_expires_at=None))
    assert _dispatchable(
        SimpleNamespace(status="running", lease_expires_at=now - timedelta(minutes=1))
    )
    assert not _dispatchable(
        SimpleNamespace(status="running", lease_expires_at=now + timedelta(minutes=5))
    )
    assert not _dispatchable(SimpleNamespace(status="running", lease_expires_at=None))
    assert not _dispatchable(SimpleNamespace(status="ready", lease_expires_at=None))


@pytest.mark.usefixtures("blocking_quality_gate")
@pytest.mark.asyncio
async def test_dispatcher_routes_accepted_writer_warning_to_review_despite_semantic_pass(
    db_session,
    db_session_factory,
) -> None:
    """A fresh revision-1 dispatch with an accepted writer SOFT issue must not
    reach READY even when the semantic reviewer itself passes the text.
    """
    source, composition, section = _accepted()
    owner, run_id = await _seed_run(db_session, source, suffix="qa-dispatch-writer-warning")
    await db_session.commit()

    async def semantic_validator(_request):
        from document.shared_lesson.document_semantic import DocumentSemanticVerdict

        return DocumentSemanticVerdict(status="pass")

    with pytest.raises(SharedDocumentQADispatchError, match="actionable learner-content issue"):
        await dispatch_shared_document_qa(
            db_session_factory,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            compositions=(composition,),
            sections=(section,),
            document_id="qa-dispatch-writer-warning-document",
            document_revision=1,
            created_at="2026-09-26T12:00:00Z",
            semantic_validator=semantic_validator,
            writer_warnings={"explain": (("unsupported_number", "nodes[0].text"),)},
        )

    async with db_session_factory() as check_session:
        run = await check_session.get(GenerationRunModel, run_id)
        assert run is not None
        assert run.status == "failed_recoverable"
        review = await get_shared_document_review_draft(
            run_id,
            current_user=SimpleNamespace(id=owner),
            session=check_session,
        )
    assert len(review["issues"]) == 1
    issue = review["issues"][0]
    assert issue["issue_code"] == "unsupported_claim"
    assert issue["affected_section_id"] == "explain"
    assert issue["affected_node_ids"] == [composition.items[0].id]


@pytest.mark.asyncio
async def test_dispatcher_reaches_ready_when_writer_warnings_are_empty(
    db_session,
    db_session_factory,
) -> None:
    """An empty (or omitted) writer_warnings mapping behaves exactly as before."""
    source, composition, section = _accepted()
    owner, run_id = await _seed_run(db_session, source, suffix="qa-dispatch-no-warning")
    await db_session.commit()

    async def semantic_validator(_request):
        from document.shared_lesson.document_semantic import DocumentSemanticVerdict

        return DocumentSemanticVerdict(status="pass")

    result = await dispatch_shared_document_qa(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        compositions=(composition,),
        sections=(section,),
        document_id="qa-dispatch-no-warning-document",
        document_revision=1,
        created_at="2026-09-26T12:00:00Z",
        semantic_validator=semantic_validator,
        writer_warnings={"explain": ()},
    )
    assert result.verified_qa.semantic_qa.passed
