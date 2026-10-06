"""Route Print realization through the verified SharedLessonDocument (P11).

This module replaces ``execute_after_teaching_approval`` (form planning,
section/block writing, ordinary assembly) for every detached Print
realization admitted through ``ensure_shared_document_run``. It never
authors ordinary content: it copies the immutable shared artifact through
``realize_shared_document_for_print`` and persists the result on the output
generation so every downstream reader (GET /document, PDF export, answer key)
sees the same hash-verified, reload-proofed document it always has.

Option D (4A): the function is a pure, idempotent materializer.  It owns no
lease and no worker state machine; the ``RealizationWorker`` runs it under a
shared-runtime work-item lease and realization status is projected from the
Run.  Figure media is already produced by the document Run.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel, NativeRealizationModel
from document.shared_lesson.media import BoundUnavailableFigureMedia, FigureMediaResult
from document.shared_lesson.realization_source import (
    ReadyRealizationSource,
    RealizationOutputError,
)
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from print.contracts.lectio_page import validate_document
from print.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    realize_shared_document_for_print,
)
from print.generation.whole_lesson.repository import PageDocumentRepository
from print.rendering.page_objects.document_assembly import (
    canonical_document_sha256,
    reload_document,
)


class PrintSharedDocumentAssemblyError(RuntimeError):
    """A verified shared document failed persisted-row hash re-verification."""


async def materialize_print_output_from_shared_document(
    session: AsyncSession,
    *,
    realization: NativeRealizationModel,
    ready: ReadyRealizationSource,
) -> dict[str, Any]:
    """Realize one Print output from a verified, READY SharedLessonDocument.

    Ordinary content is copied; only TaskAnchors are lowered to paper
    treatments (choices/questions) with a matching answer key. The caller owns
    the transaction: this only flushes.  Re-running on the same immutable
    inputs rewrites an identical document.
    """
    generation_id = str(realization.output_id or "")
    generation = await session.get(GenerationModel, generation_id)
    if generation is None:
        raise RealizationOutputError("The Print output row is missing.")
    metadata = (generation.chunked_state_json or {}).get("print_realization") or {}
    if metadata.get("realization_id") != realization.id:
        raise RealizationOutputError("The Print output does not match its pinned realization.")

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
    # A required figure with only a deferred (unrendered) media binding must
    # never be silently dropped or replaced with a placeholder; excluding it
    # here lets the adapter's own required-figure check raise truthfully
    # instead of a caller inventing degraded Print content (18_PRINT_REALIZATION).
    figure_media = [
        m
        for m in ready.media_results
        if isinstance(m, (FigureMediaResult, BoundUnavailableFigureMedia))
    ]

    # SharedDocumentPrintMappingError propagates typed; the worker turns it
    # into a terminal validation failure on the work item.
    realized = realize_shared_document_for_print(
        stored,
        expected_identity=expected_identity,
        figure_media=figure_media,
        document_id=f"doc-{generation_id}",
    )

    document_sha256 = canonical_document_sha256(realized.document)
    repo = PageDocumentRepository(session, generation_id)
    await repo.write_shared_document_output(
        realized.document, document_sha256=document_sha256
    )

    # Reload the row this transaction just wrote and verify it round-trips
    # (never trust the in-memory candidate).
    generation = await session.get(GenerationModel, generation_id, populate_existing=True)
    assert generation is not None
    reloaded = reload_document(generation.document_json)
    errors = validate_document(reloaded)
    if errors:
        raise PrintSharedDocumentAssemblyError(f"persisted document validation failed: {errors[:5]}")
    if canonical_document_sha256(reloaded) != document_sha256:
        raise PrintSharedDocumentAssemblyError("persisted document hash mismatch")

    generation.shared_document_run_id = ready.run_id
    generation.shared_document_id = document.id
    generation.shared_document_revision = document.revision
    generation.shared_document_hash = ready.content_hash

    # Lineage only; ``realization.status`` is projected from the Run.
    realization.shared_document_run_id = ready.run_id
    realization.shared_document_id = document.id
    realization.shared_document_revision = document.revision
    realization.shared_document_hash = ready.content_hash
    realization.shared_document_state = "ready"
    realization.teaching_plan_hash = ready.plan_hash
    await session.flush()

    return {
        "output_id": generation_id,
        "document_sha256": document_sha256,
        "content_hash": ready.content_hash,
    }


__all__ = [
    "PrintSharedDocumentAssemblyError",
    "materialize_print_output_from_shared_document",
]
