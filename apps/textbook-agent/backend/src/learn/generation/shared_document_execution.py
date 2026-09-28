"""Route Learn realization through the verified SharedLessonDocument (P10B).

This module replaces ``produce_learn_from_approved_teaching`` on the Learn
creation path. It never authors ordinary content: it copies the immutable
shared artifact through ``realize_shared_document_for_learn`` and persists
the result exactly where the old path persisted its output.

``apply_non_ready_shared_document_state`` handles every non-``ready``
``RealizationSourceResult`` the worker can observe. It never busy-polls and
never consumes a bounded retry attempt for a still-pending shared source —
the caller's normal queued-row poll re-observes the row on its own cadence.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import EditableLessonModel, GenerationModel, NativeRealizationModel
from document.shared_lesson.realization_source import (
    ReadyRealizationSource,
    RealizationSourceResult,
)
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from learn.generation.fencing import (
    LearnCancelledError,
    assert_learn_commit_allowed,
    assert_learn_dispatch_allowed,
    claim_learn_execution,
    learn_execution_from_generation,
    write_learn_execution,
)
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    SharedDocumentLearnMappingError,
    realize_shared_document_for_learn,
)
from learn.publishing.publish_validation import validate_publishable_lesson_document


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def apply_non_ready_shared_document_state(
    session: AsyncSession,
    *,
    realization: NativeRealizationModel,
    result: RealizationSourceResult,
) -> dict[str, Any]:
    """Persist the closed, non-``ready`` classification onto the realization.

    Never claims the output lease and never regresses a realization that a
    concurrent worker has already advanced past ``queued``.
    """
    if result.state == "pending":
        pending = result.pending
        realization.shared_document_run_id = pending.run_id if pending else None
        realization.shared_document_state = "pending"
        await session.flush()
        return {
            "status": "waiting_shared_document",
            "realization_id": realization.id,
            "stage": pending.stage if pending else "not_started",
        }
    if result.state == "needs_review":
        needs_review = result.needs_review
        assert needs_review is not None
        realization.status = "needs_shared_review"
        realization.shared_document_run_id = needs_review.run_id
        realization.shared_document_state = "needs_review"
        realization.error_summary = None
        await session.flush()
        return {
            "status": "needs_shared_review",
            "realization_id": realization.id,
            "shared_document_run_id": needs_review.run_id,
            "work_item_id": needs_review.work_item_id,
        }
    if result.state == "stale":
        stale = result.stale
        assert stale is not None
        realization.status = "failed_recoverable"
        realization.shared_document_run_id = stale.run_id
        realization.shared_document_state = "stale"
        realization.error_summary = f"SHARED_DOCUMENT_STALE: {stale.reason}"[:500]
        await session.flush()
        return {
            "status": "failed_recoverable",
            "realization_id": realization.id,
            "error_summary": realization.error_summary,
        }
    if result.state == "failed":
        failed = result.failed
        assert failed is not None
        realization.status = "failed_recoverable"
        if failed.run_id:
            realization.shared_document_run_id = failed.run_id
        realization.shared_document_state = "failed"
        code = failed.error_code or "SHARED_DOCUMENT_FAILED"
        summary = failed.error_summary or "SharedLessonDocument run failed."
        realization.error_summary = f"{code}: {summary}"[:500]
        await session.flush()
        return {
            "status": "failed_recoverable",
            "realization_id": realization.id,
            "error_summary": realization.error_summary,
        }
    raise AssertionError(f"unexpected realization-source state {result.state!r}")


async def execute_learn_realization_from_shared_document(
    session: AsyncSession,
    *,
    realization: NativeRealizationModel,
    ready: ReadyRealizationSource,
    owner_user_id: str,
    subject: str,
    worker_id: str,
) -> dict[str, Any]:
    """Realize one Learn output from a verified, READY SharedLessonDocument.

    Ordinary content is copied; only TaskAnchors are lowered to Learn
    interactions. No composer/writer/task-authoring call is made here.
    """
    output_id = str(realization.output_id or "")
    output = await session.get(GenerationModel, output_id)
    if output is None:
        raise HTTPException(
            status_code=409, detail={"code": "LEARN_OUTPUT_MISSING", "recovery_action": "reprepare"}
        )

    execution = learn_execution_from_generation(output)
    try:
        assert_learn_dispatch_allowed(execution)
    except LearnCancelledError:
        realization.status = "cancelled"
        await session.flush()
        raise

    lease = await claim_learn_execution(session, generation_id=output_id, worker_id=worker_id)
    if lease is None:
        generation = await session.get(GenerationModel, output_id)
        assert generation is not None
        execution = learn_execution_from_generation(generation)
        assert_learn_dispatch_allowed(execution)
        raise LearnCancelledError("Learn execution could not be claimed")

    realization.status = "running"
    await session.flush()
    # Durable persist / heartbeat cannot see uncommitted rows, and a crash (or
    # a later exception in this same session) must not roll "running" back to
    # "queued" — that would misclassify an execution failure as a preflight
    # one. Commit admission identity + lease before any further work.
    await session.commit()
    realization = await session.get(type(realization), realization.id)
    assert realization is not None
    output = await session.get(GenerationModel, output_id)
    assert output is not None

    document = ready.document
    expected_identity = SharedDocumentIdentity(
        id=document.id, revision=document.revision, content_hash=ready.content_hash
    )
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id=str(realization.path_lesson_id),
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )

    try:
        realized = realize_shared_document_for_learn(
            stored,
            expected_identity=expected_identity,
            subject=subject,
            source_generation_id=output_id,
            learn_document_id=output_id,
        )
    except SharedDocumentLearnMappingError as exc:
        execution = learn_execution_from_generation(output)
        execution.update({"status": "failed", "worker_id": None, "heartbeat_at": None})
        write_learn_execution(output, execution)
        output.status = "failed"
        output.error = str(exc)[:500]
        output.error_code = "SHARED_DOCUMENT_UNMAPPABLE"
        realization.status = "failed_recoverable"
        realization.shared_document_run_id = ready.run_id
        realization.shared_document_state = "failed"
        realization.error_summary = f"SHARED_DOCUMENT_UNMAPPABLE: {exc}"[:500]
        await session.flush()
        return {
            "status": "failed_recoverable",
            "output_id": output_id,
            "realization_id": realization.id,
            "error_summary": realization.error_summary,
        }

    learn_document = dict(realized.document.model_dump(mode="json"))
    learn_document["id"] = output_id
    learn_document["source_generation_id"] = output_id
    validate_publishable_lesson_document(learn_document)

    # Fenced commit: expired / cancelled workers cannot publish.
    output = await session.get(GenerationModel, output_id)
    assert output is not None
    execution = learn_execution_from_generation(output)
    assert_learn_commit_allowed(execution, worker_id=lease.worker_id, lease_token=lease.lease_token)

    output.status = "completed"
    output.document_json = learn_document
    output.shared_document_run_id = ready.run_id
    output.shared_document_id = document.id
    output.shared_document_revision = document.revision
    output.shared_document_hash = ready.content_hash
    output.chunked_state_json = {
        **dict(output.chunked_state_json or {}),
        "shared_preparation": False,
        "native_learn": True,
        "learn_document": True,
        "document_version": 2,
        "control": {"pipeline": "shared_document_learn"},
        "teaching_plan_id": ready.plan_id,
        "teaching_plan_revision": ready.plan_revision,
        "teaching_plan_hash": ready.plan_hash,
        "shared_document": {
            "run_id": ready.run_id,
            "id": document.id,
            "revision": document.revision,
            "content_hash": ready.content_hash,
            "teaching_plan_id": ready.plan_id,
            "teaching_plan_revision": ready.plan_revision,
            "teaching_plan_hash": ready.plan_hash,
        },
    }
    execution = learn_execution_from_generation(output)
    execution["status"] = "ready"
    write_learn_execution(output, execution)

    lesson_id = str(uuid.uuid4())
    now = _utcnow()
    editable = EditableLessonModel(
        id=lesson_id,
        user_id=owner_user_id,
        source_generation_id=output_id,
        source_type="learn_document",
        title=str(learn_document.get("title") or "Learn lesson"),
        class_label=None,
        document_json={
            **learn_document,
            "id": lesson_id,
            "updated_at": now.isoformat() + "Z",
            "created_at": now.isoformat() + "Z",
        },
        created_at=now,
        updated_at=now,
        shared_document_run_id=ready.run_id,
        shared_document_id=document.id,
        shared_document_revision=document.revision,
        shared_document_hash=ready.content_hash,
    )
    session.add(editable)

    realization.status = "ready"
    realization.teaching_plan_hash = ready.plan_hash
    realization.shared_document_run_id = ready.run_id
    realization.shared_document_id = document.id
    realization.shared_document_revision = document.revision
    realization.shared_document_hash = ready.content_hash
    realization.shared_document_state = "ready"
    realization.error_summary = None
    await session.flush()

    return {
        "status": "ready",
        "output_id": output_id,
        "editable_lesson_id": lesson_id,
        "realization_id": realization.id,
        "realization_created": False,
        "teaching_plan_hash": ready.plan_hash,
        "teaching_plan_revision": ready.plan_revision,
        "document": learn_document,
        "content_hash": ready.content_hash,
        "replayed": False,
        "shared_document_run_id": ready.run_id,
        "shared_document_id": document.id,
        "shared_document_revision": document.revision,
        "shared_document_hash": ready.content_hash,
    }


__all__ = [
    "apply_non_ready_shared_document_state",
    "execute_learn_realization_from_shared_document",
]
