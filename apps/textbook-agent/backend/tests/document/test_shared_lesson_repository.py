from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import select, update

from document.shared_lesson import build_shared_lesson_document
from document.shared_lesson.repository import (
    SharedLessonDocumentConflict,
    SharedLessonDocumentIntegrityError,
    load_shared_lesson_document,
    load_verified_shared_lesson_artifact,
    save_shared_lesson_document,
    verify_shared_lesson_source,
)
from infra.database.models import SharedLessonDocumentModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime.contracts import SourceIdentity

PLAN_HASH = "a" * 64


def _payload(*, title: str = "Photosynthesis", document_id: str = "lesson-1") -> dict[str, object]:
    return {
        "id": document_id,
        "revision": 1,
        "teaching_plan_id": "plan-1",
        "teaching_plan_revision": 3,
        "teaching_plan_hash": PLAN_HASH,
        "title": title,
        "sections": [
            {
                "id": "section-1",
                "title": "How plants make food",
                "position": 0,
                "nodes": [
                    {
                        "id": "paragraph-1",
                        "kind": "paragraph",
                        "display": {"text": "Plants use light."},
                    }
                ],
            }
        ],
        "created_at": "2026-09-24T09:00:00+03:00",
    }


def _document(**kwargs):
    return build_shared_lesson_document(_payload(**kwargs))


@pytest.mark.asyncio
async def test_exact_duplicate_save_is_idempotent(db_session) -> None:
    document = _document()

    first = await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )
    second = await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )

    assert second == first
    assert second.status == "draft"
    assert second.storage_hash == content_hash(document.model_dump(mode="json"))
    assert (
        await db_session.scalar(
            select(SharedLessonDocumentModel.revision).where(
                SharedLessonDocumentModel.id == document.id
            )
        )
        == document.revision
    )


@pytest.mark.asyncio
async def test_same_identity_conflicting_content_or_path_is_rejected(db_session) -> None:
    document = _document()
    await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )

    with pytest.raises(SharedLessonDocumentConflict, match="different content"):
        await save_shared_lesson_document(
            db_session,
            path_lesson_id="path-lesson-1",
            document=_document(title="Changed title"),
        )
    with pytest.raises(SharedLessonDocumentIntegrityError, match="different lesson"):
        await save_shared_lesson_document(
            db_session, path_lesson_id="path-lesson-2", document=document
        )


@pytest.mark.asyncio
async def test_loader_rejects_corrupted_json_and_explicit_lineage(db_session) -> None:
    document = _document()
    await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )

    changed_json = deepcopy(document.model_dump(mode="json"))
    changed_json["title"] = "Corrupted"
    await db_session.execute(
        update(SharedLessonDocumentModel)
        .where(SharedLessonDocumentModel.id == document.id)
        .values(document_json=changed_json)
    )
    db_session.expire_all()
    with pytest.raises(
        SharedLessonDocumentIntegrityError, match="content hash|canonical|validation"
    ):
        await load_shared_lesson_document(
            db_session, document_id=document.id, revision=document.revision
        )

    await db_session.rollback()
    await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )
    await db_session.execute(
        update(SharedLessonDocumentModel)
        .where(SharedLessonDocumentModel.id == document.id)
        .values(teaching_plan_hash="b" * 64)
    )
    db_session.expire_all()
    with pytest.raises(SharedLessonDocumentIntegrityError, match="teaching_plan_hash"):
        await load_shared_lesson_document(
            db_session, document_id=document.id, revision=document.revision
        )


@pytest.mark.asyncio
async def test_ready_rows_are_immutable_at_repository_event_boundary(db_session) -> None:
    document = _document()
    await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )
    await db_session.execute(
        update(SharedLessonDocumentModel)
        .where(SharedLessonDocumentModel.id == document.id)
        .values(status="ready")
    )
    await db_session.commit()
    db_session.expire_all()
    ready = await db_session.get(
        SharedLessonDocumentModel, {"id": document.id, "revision": document.revision}
    )
    assert ready is not None
    ready.document_json = {**document.model_dump(mode="json"), "title": "Mutation"}
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()
    await db_session.rollback()
    ready = await db_session.get(
        SharedLessonDocumentModel, {"id": document.id, "revision": document.revision}
    )
    assert ready is not None
    await db_session.delete(ready)
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()


@pytest.mark.asyncio
async def test_trusted_runtime_adapters_recompute_source_and_artifact_identity(db_session) -> None:
    document = _document()
    stored = await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )
    source = SourceIdentity(
        source_artifact_type="shared_lesson_document",
        source_artifact_id=document.id,
        source_revision=document.revision,
        source_hash=document.content_hash,
    )

    assert await verify_shared_lesson_source(db_session, source) == source
    with pytest.raises(SharedLessonDocumentIntegrityError, match="only ready"):
        await load_verified_shared_lesson_artifact(
            db_session, "shared_lesson_document", document.id, document.revision
        )
    await db_session.execute(
        update(SharedLessonDocumentModel)
        .where(SharedLessonDocumentModel.id == document.id)
        .values(status="ready")
    )
    await db_session.commit()
    artifact = await load_verified_shared_lesson_artifact(
        db_session, "shared_lesson_document", document.id, document.revision
    )
    assert artifact.output_hash == content_hash(artifact.output_json)
    assert artifact.output_hash == stored.storage_hash

    with pytest.raises(SharedLessonDocumentConflict, match="source hash"):
        await verify_shared_lesson_source(
            db_session,
            source.model_copy(update={"source_hash": "b" * 64}),
        )
