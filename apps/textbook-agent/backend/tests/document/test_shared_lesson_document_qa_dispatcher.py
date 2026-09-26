from __future__ import annotations

import pytest
from sqlalchemy import select
from test_shared_lesson_handoff import _accepted
from test_shared_qa_runtime import _seed_run

from document.shared_lesson.document_qa_dispatcher import (
    SharedDocumentQADispatchError,
    dispatch_shared_document_qa,
)
from infra.database.models import GenerationWorkItemModel


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
