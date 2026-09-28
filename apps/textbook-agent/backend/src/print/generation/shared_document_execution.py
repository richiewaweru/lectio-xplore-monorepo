"""Route Print realization through the verified SharedLessonDocument (P11).

This module replaces ``execute_after_teaching_approval`` (form planning,
section/block writing, ordinary assembly) for every detached Print
realization admitted through ``ensure_shared_document_run``. It never
authors ordinary content: it copies the immutable shared artifact through
``realize_shared_document_for_print`` and persists the result through the
existing lease-fenced ``PageDocumentRepository`` candidate/finalize seam so
every downstream reader (GET /document, PDF export, answer key) sees the
same hash-verified, reload-proofed document it always has.

The non-``ready`` branch (``pending``/``needs_review``/``stale``/``failed``)
is handled directly inside
``print.generation.whole_lesson.repository.claim_next_native_job`` — a
non-ready shared source must never claim the output lease, so that
classification happens *before* any lease exists. This module only handles
the ``ready`` path, once a lease has already been claimed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel, NativeRealizationModel
from document.shared_lesson.media import FigureMediaResult
from document.shared_lesson.realization_source import ReadyRealizationSource
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from print.contracts.lectio_page import validate_document
from print.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    SharedDocumentPrintMappingError,
    realize_shared_document_for_print,
)
from print.generation.whole_lesson.repository import PageDocumentRepository
from print.generation.whole_lesson.states import ExecutionLease
from print.rendering.page_objects.document_assembly import (
    canonical_document_sha256,
    reload_document,
)


class PrintSharedDocumentAssemblyError(RuntimeError):
    """A verified shared document failed fresh-session hash re-verification."""


async def execute_print_realization_from_shared_document(
    session: AsyncSession,
    *,
    realization: NativeRealizationModel,
    ready: ReadyRealizationSource,
    lease: ExecutionLease,
) -> dict[str, Any]:
    """Realize one Print output from a verified, READY SharedLessonDocument.

    Ordinary content is copied; only TaskAnchors are lowered to paper
    treatments (choices/questions) with a matching answer key. No
    composer/writer/whole-lesson-form call is made here.
    """
    generation_id = lease.generation_id
    repo = PageDocumentRepository(session, generation_id)

    generation = await session.get(GenerationModel, generation_id)
    assert generation is not None
    if str(generation.status or "") == "planning_forms":
        # planning_forms -> assembling: skip ordinary form planning/writing.
        await repo.enter_assembling_for_shared_document(
            worker_id=lease.worker_id, lease_token=lease.lease_token
        )
    # A resumed lease may already be in "assembling" (a crash between
    # entering assembling and the fresh-session finalize below). Re-running
    # the pure adapter and the hash-fenced candidate/finalize seam on the
    # same immutable inputs is idempotent, so no extra branch is needed here.

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
    figure_media = [m for m in ready.media_results if isinstance(m, FigureMediaResult)]

    try:
        realized = realize_shared_document_for_print(
            stored,
            expected_identity=expected_identity,
            figure_media=figure_media,
            document_id=f"doc-{generation_id}",
        )
    except SharedDocumentPrintMappingError as exc:
        await repo.fail_shared_document_mapping(
            message=str(exc),
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
        )
        realization.shared_document_run_id = ready.run_id
        realization.shared_document_state = "failed"
        realization.error_summary = f"SHARED_DOCUMENT_UNMAPPABLE: {exc}"[:500]
        await session.commit()
        return {
            "status": "failed_recoverable",
            "output_id": generation_id,
            "realization_id": realization.id,
            "error_summary": realization.error_summary,
        }

    before_hash = canonical_document_sha256(realized.document)
    await repo.persist_document_candidate(
        realized.document,
        document_sha256=before_hash,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
    )

    # Fresh-session reload/verify before finalizing, matching the ordinary
    # whole-lesson assembly seam exactly (never trust the in-session write).
    from core.database.session import async_session_factory

    async with async_session_factory() as fresh:
        gen2 = await fresh.get(GenerationModel, generation_id)
        if gen2 is None:
            raise PrintSharedDocumentAssemblyError(f"generation {generation_id!r} vanished")
        reloaded = reload_document(gen2.document_json)
        errors = validate_document(reloaded)
        if errors:
            raise PrintSharedDocumentAssemblyError(
                f"fresh-session validation failed: {errors[:5]}"
            )
        after_hash = canonical_document_sha256(reloaded)
        if after_hash != before_hash:
            raise PrintSharedDocumentAssemblyError("fresh-session hash mismatch")

    await repo.finalize_verified_document(
        expected_document_sha256=before_hash,
        reloaded_sha256=after_hash,
        pending_visuals=False,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
    )

    generation = await session.get(GenerationModel, generation_id)
    assert generation is not None
    generation.shared_document_run_id = ready.run_id
    generation.shared_document_id = document.id
    generation.shared_document_revision = document.revision
    generation.shared_document_hash = ready.content_hash

    realization.shared_document_run_id = ready.run_id
    realization.shared_document_id = document.id
    realization.shared_document_revision = document.revision
    realization.shared_document_hash = ready.content_hash
    realization.shared_document_state = "ready"
    realization.teaching_plan_hash = ready.plan_hash
    realization.error_summary = None
    await session.commit()

    return {
        "status": "ready",
        "output_id": generation_id,
        "realization_id": realization.id,
        "document_sha256": before_hash,
        "shared_document_run_id": ready.run_id,
        "shared_document_id": document.id,
        "shared_document_revision": document.revision,
        "shared_document_hash": ready.content_hash,
    }


__all__ = [
    "PrintSharedDocumentAssemblyError",
    "execute_print_realization_from_shared_document",
]
