"""Owner-scoped, read-only HTTP preview for immutable shared documents."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.user import User
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.repository import (
    SharedLessonDocumentRepositoryError,
    load_shared_lesson_document,
)
from infra.auth.middleware import get_current_user
from infra.database.models import GenerationBuildModel, GenerationRunModel
from infra.database.session import get_async_session
from infra.execution.checkpoints import content_hash

router = APIRouter(prefix="/api/v1/shared-documents", tags=["shared-documents"])


def _not_found() -> HTTPException:
    """Use one response for missing, foreign, stale, and conflicting artifacts."""
    return HTTPException(status_code=404, detail="Shared document not found")


def _identity(
    *, artifact_type: str | None, artifact_id: str | None, revision: int | None, digest: str | None
) -> dict[str, Any]:
    return {
        "type": artifact_type,
        "id": artifact_id,
        "revision": revision,
        "hash": digest,
    }


@router.get("/{document_id}/revisions/{revision}")
async def get_shared_document_preview(
    document_id: str,
    revision: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Return a READY document only when its owner's run proves its lineage."""
    candidates = list(
        (
            await session.execute(
                select(GenerationRunModel, GenerationBuildModel.path_lesson_id)
                .join(
                    GenerationBuildModel,
                    GenerationBuildModel.id == GenerationRunModel.build_id,
                )
                .where(
                    GenerationRunModel.owner_user_id == current_user.id,
                    GenerationBuildModel.owner_user_id == current_user.id,
                    GenerationRunModel.run_type == "shared_document",
                    GenerationRunModel.status == "ready",
                    GenerationRunModel.output_artifact_type == "shared_lesson_document",
                    GenerationRunModel.output_artifact_id == document_id,
                    GenerationRunModel.output_revision == revision,
                    GenerationRunModel.output_hash.is_not(None),
                )
                .order_by(GenerationRunModel.updated_at.desc(), GenerationRunModel.id.desc())
            )
        ).all()
    )
    if not candidates:
        raise _not_found()

    try:
        stored = await load_shared_lesson_document(
            session,
            document_id=document_id,
            revision=revision,
            path_lesson_id=candidates[0][1],
        )
    except SharedLessonDocumentRepositoryError:
        raise _not_found() from None

    if stored.status != "ready":
        raise _not_found()

    document = stored.document
    # The repository validates the content hash, but keep both identities
    # explicit at this HTTP boundary before exposing immutable content.
    if shared_lesson_content_hash(document) != document.content_hash:
        raise _not_found()
    expected_output_hash = content_hash(document.model_dump(mode="json"))
    if stored.storage_hash != expected_output_hash:
        raise _not_found()

    run = next(
        (
            candidate[0]
            for candidate in candidates
            if candidate[0].output_hash == expected_output_hash
        ),
        None,
    )
    if run is None:
        raise _not_found()

    return {
        "status": "ready",
        "document": document.model_dump(mode="json"),
        "source": _identity(
            artifact_type=run.source_artifact_type,
            artifact_id=run.source_artifact_id,
            revision=run.source_revision,
            digest=run.source_hash,
        ),
        "output": _identity(
            artifact_type=run.output_artifact_type,
            artifact_id=run.output_artifact_id,
            revision=run.output_revision,
            digest=run.output_hash,
        ),
    }


__all__ = ["get_shared_document_preview", "router"]
