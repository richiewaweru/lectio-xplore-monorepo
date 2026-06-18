from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from pipeline.api import PipelineDocument
from generation.entities.generation import Generation
from generation.ports.document_repository import DocumentRepository
from generation.ports.generation_repository import GenerationRepository

INTERRUPTED_GENERATION_ERROR = "Generation was interrupted before it finished. Please try again."
INTERRUPTED_GENERATION_ERROR_TYPE = "runtime_error"
INTERRUPTED_GENERATION_ERROR_CODE = "stale_generation"
WORKER_RESTART_GENERATION_ERROR = (
    "Your generation was interrupted by a server update. Please try again."
)
WORKER_RESTART_GENERATION_ERROR_TYPE = "worker_restart"
WORKER_RESTART_GENERATION_ERROR_CODE = "worker_restart"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _failed_document_snapshot(
    generation: Generation,
    *,
    completed_at: datetime,
    error: str,
    existing: PipelineDocument | None,
) -> PipelineDocument:
    if existing is None:
        return PipelineDocument(
            generation_id=generation.id,
            subject=generation.subject,
            context=generation.context,
            template_id=generation.resolved_template_id or generation.requested_template_id,
            preset_id=generation.resolved_preset_id or generation.requested_preset_id,
            status="failed",
            quality_passed=False,
            error=error,
            created_at=generation.created_at,
            updated_at=completed_at,
            completed_at=completed_at,
        )

    return existing.model_copy(
        update={
            "status": "failed",
            "quality_passed": False,
            "error": error,
            "updated_at": completed_at,
            "completed_at": completed_at,
        }
    )


async def persist_interrupted_generation_failure(
    generation: Generation,
    *,
    generation_repository: GenerationRepository,
    document_repository: DocumentRepository,
    report_repository=None,
    error: str = INTERRUPTED_GENERATION_ERROR,
    error_type: str = INTERRUPTED_GENERATION_ERROR_TYPE,
    error_code: str = INTERRUPTED_GENERATION_ERROR_CODE,
) -> None:
    completed_at = _utc_now()

    existing_document = None
    if generation.document_path:
        try:
            existing_document = await document_repository.load_document(generation.document_path)
        except FileNotFoundError:
            existing_document = None

    failed_document = _failed_document_snapshot(
        generation,
        completed_at=completed_at,
        error=error,
        existing=existing_document,
    )
    document_path = await document_repository.save_document(failed_document)

    await generation_repository.update_status(
        generation.id,
        status="failed",
        document_path=document_path,
        error=error,
        error_type=error_type,
        error_code=error_code,
        quality_passed=False,
    )


async def mark_stale_generations_failed(
    generations: Sequence[Generation],
    *,
    generation_repository: GenerationRepository,
    document_repository: DocumentRepository,
    report_repository=None,
) -> int:
    count = 0
    for generation in generations:
        await persist_interrupted_generation_failure(
            generation,
            generation_repository=generation_repository,
            document_repository=document_repository,
            report_repository=report_repository,
            error=WORKER_RESTART_GENERATION_ERROR,
            error_type=WORKER_RESTART_GENERATION_ERROR_TYPE,
            error_code=WORKER_RESTART_GENERATION_ERROR_CODE,
        )
        count += 1
    return count

