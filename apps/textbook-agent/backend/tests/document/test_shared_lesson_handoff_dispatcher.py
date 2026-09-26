from __future__ import annotations

import pytest
from test_shared_lesson_handoff import _accepted
from test_shared_qa_runtime import _seed_run

from document.shared_lesson import handoff
from document.shared_lesson.document_qa_dispatcher import dispatch_shared_document_qa
from document.shared_lesson.handoff_dispatcher import (
    SharedDocumentHandoffDispatchError,
    handoff_qa_dispatch_result,
)


@pytest.mark.asyncio
async def test_handoff_bridge_reuses_durable_semantic_pass_without_second_provider_call(
    db_session,
    db_session_factory,
    monkeypatch,
) -> None:
    source, composition, section = _accepted()
    owner, run_id = await _seed_run(db_session, source, suffix="handoff-dispatch-success")
    await db_session.commit()
    calls = 0

    async def semantic_validator(_request):
        nonlocal calls
        calls += 1
        from document.shared_lesson.document_semantic import DocumentSemanticVerdict

        return DocumentSemanticVerdict(status="pass")

    dispatched = await dispatch_shared_document_qa(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        compositions=(composition,),
        sections=(section,),
        document_id="handoff-dispatch-document",
        document_revision=1,
        created_at="2026-09-26T12:00:00Z",
        semantic_validator=semantic_validator,
    )

    async def unexpected_provider_call(*_args, **_kwargs):
        raise AssertionError("handoff must not call the semantic provider")

    monkeypatch.setattr(handoff, "qa_shared_lesson_document_semantics", unexpected_provider_call)
    evidence = await handoff_qa_dispatch_result(
        dispatched,
        source=source,
        compositions=(composition,),
        sections=(section,),
    )

    assert calls == 1
    assert evidence.document == dispatched.document
    assert evidence.document.content_hash == dispatched.document.content_hash
    assert evidence.semantic_qa == dispatched.verified_qa.semantic_qa


@pytest.mark.asyncio
async def test_handoff_bridge_rejects_stale_dispatch_identity_and_media_declaration(
    db_session,
    db_session_factory,
) -> None:
    source, composition, section = _accepted()
    owner, run_id = await _seed_run(db_session, source, suffix="handoff-dispatch-failure")
    await db_session.commit()

    async def semantic_validator(_request):
        from document.shared_lesson.document_semantic import DocumentSemanticVerdict

        return DocumentSemanticVerdict(status="pass")

    dispatched = await dispatch_shared_document_qa(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        compositions=(composition,),
        sections=(section,),
        document_id="handoff-dispatch-forged",
        document_revision=1,
        created_at="2026-09-26T12:00:00Z",
        semantic_validator=semantic_validator,
    )
    forged_document = dispatched.document.model_copy(update={"content_hash": "f" * 64})
    forged = dispatched.model_copy(update={"document": forged_document})
    with pytest.raises(SharedDocumentHandoffDispatchError, match="content hash"):
        await handoff_qa_dispatch_result(
            forged,
            source=source,
            compositions=(composition,),
            sections=(section,),
        )

    with pytest.raises(SharedDocumentHandoffDispatchError, match="required media declaration"):
        await handoff_qa_dispatch_result(
            dispatched,
            source=source,
            compositions=(composition,),
            sections=(section,),
            required_media_by_section={"explain": ("figure-1",)},
        )
