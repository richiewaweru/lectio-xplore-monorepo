from __future__ import annotations

import pytest
from test_shared_qa_runtime import _deterministic, _seed_run, _source_and_document

from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.qa_runtime import (
    DocumentQAWorkItemJob,
    admit_document_qa_work_item,
    execute_document_qa_work_item,
)
from infra.database.models import GenerationWorkItemModel
from infra.execution.leases import LeaseLostError
from infra.generation_runtime import cancel_run


@pytest.mark.asyncio
async def test_qa_claim_and_checkpoint_are_committed_before_provider_and_late_cancel_is_fenced(
    db_session,
    db_session_factory,
) -> None:
    source, document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source, suffix="committed-boundary")
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=_deterministic(document),
    )

    observed: dict[str, object] = {}

    async def provider(_request):
        async with db_session_factory() as observer:
            item = await observer.get(GenerationWorkItemModel, admitted.record.id)
            assert item is not None
            observed["status"] = item.status
            observed["lease_owner"] = item.lease_owner
            observed["checkpoint"] = item.checkpoint_json
            await cancel_run(observer, run_id=run_id, owner_user_id=owner)
            await observer.commit()
        return DocumentSemanticVerdict(status="pass")

    with pytest.raises(LeaseLostError):
        await execute_document_qa_work_item(
            DocumentQAWorkItemJob(
                session=db_session,
                work_item_id=admitted.record.id,
                worker_id="qa-worker-boundary",
                owner_user_id=owner,
                source=source,
                document=document,
                deterministic_qa=_deterministic(document),
                semantic_validator=provider,
            )
        )

    assert observed["status"] == "running"
    assert observed["lease_owner"] == "qa-worker-boundary"
    assert observed["checkpoint"] is not None
    item = await db_session.get(GenerationWorkItemModel, admitted.record.id)
    assert item is not None
    await db_session.refresh(item)
    assert item.status == "cancelled"
