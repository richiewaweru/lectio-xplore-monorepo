"""HTTP projections for the canonical Component Lectio generation path."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from core.auth.middleware import get_current_user
from core.dependencies import get_async_session, get_jwt_handler, get_settings
from core.entities.user import User
from generation.canonical import (
    CanonicalGenerationSummary,
    builder_id_for_generation,
    canonical_document,
    get_owned_canonical_generation,
    list_owned_canonical_generations,
    summary_from_generation,
)
from generation.pdf_export.cleanup import cleanup_files
from generation.pdf_export.service import (
    PDFExportRequest,
    export_canonical_generation_pdf,
)
from core.auth.jwt_handler import JWTHandler

# Mounted by ``generation.routes`` beneath its shared ``/api/v1`` prefix.
router = APIRouter(prefix="/generations", tags=["generation"])


class CanonicalGenerationPDFExportRequest(BaseModel):
    school_name: str = Field(min_length=1)
    teacher_name: str = Field(min_length=1)
    date: str | None = None
    include_toc: bool = True
    include_answers: bool = True


async def _canonical_or_404(
    session: AsyncSession,
    *,
    generation_id: str,
    user_id: str,
):
    generation = await get_owned_canonical_generation(
        session,
        generation_id=generation_id,
        user_id=user_id,
    )
    if generation is None:
        # Deliberately collapse unknown, unmarked, and retired generations into
        # one response so historical Studio rows cannot be enumerated.
        raise HTTPException(status_code=404, detail="Generation not found")
    return generation


@router.get("", response_model=list[CanonicalGenerationSummary])
async def list_generations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CanonicalGenerationSummary]:
    generations = await list_owned_canonical_generations(
        session,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return [summary_from_generation(generation) for generation in generations]


@router.get("/{generation_id}", response_model=CanonicalGenerationSummary)
async def get_generation(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CanonicalGenerationSummary:
    generation = await _canonical_or_404(
        session,
        generation_id=generation_id,
        user_id=current_user.id,
    )
    builder_id = await builder_id_for_generation(
        session,
        generation_id=generation.id,
        user_id=current_user.id,
    )
    return summary_from_generation(generation, builder_id=builder_id)


@router.get("/{generation_id}/status", response_model=CanonicalGenerationSummary)
async def get_generation_status(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CanonicalGenerationSummary:
    return await get_generation(generation_id, current_user, session)


@router.get("/{generation_id}/document")
async def get_generation_document(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    generation = await _canonical_or_404(
        session,
        generation_id=generation_id,
        user_id=current_user.id,
    )
    document = canonical_document(generation)
    if document is None:
        if str(generation.status or "").lower() in {"failed", "partial"}:
            raise HTTPException(status_code=422, detail="Generation has no usable LessonDocument")
        raise HTTPException(status_code=409, detail="LessonDocument is not ready")
    return deepcopy(document)


@router.post("/{generation_id}/export/pdf", response_class=FileResponse)
async def export_generation_pdf_route(
    generation_id: str,
    body: CanonicalGenerationPDFExportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> FileResponse:
    """Export an explicitly canonical generation through the shared renderer."""
    generation = await _canonical_or_404(
        session,
        generation_id=generation_id,
        user_id=current_user.id,
    )
    if canonical_document(generation) is None:
        raise HTTPException(status_code=409, detail="LessonDocument is not ready")
    if str(generation.status or "").lower() not in {"completed", "partial"}:
        raise HTTPException(status_code=409, detail="Generation is not ready for PDF export")
    builder_id = await builder_id_for_generation(
        session,
        generation_id=generation.id,
        user_id=current_user.id,
    )
    if not builder_id:
        raise HTTPException(status_code=409, detail="Builder lesson is not ready")

    auth_token = jwt_handler.create_access_token(current_user.id, current_user.email)
    pdf_request = PDFExportRequest(
        school_name=body.school_name,
        teacher_name=body.teacher_name,
        date=body.date,
        include_toc=body.include_toc,
        include_answers=body.include_answers,
    )
    try:
        result = await export_canonical_generation_pdf(
            generation=generation,
            auth_token=auth_token,
            request=pdf_request,
            settings=get_settings(),
            request_id=getattr(request.state, "request_id", None),
            render_path=f"/builder/print/{builder_id}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="PDF export failed") from exc
    return FileResponse(
        path=result.pdf_path,
        media_type="application/pdf",
        filename=result.filename,
        headers={
            "X-Page-Count": str(result.page_count),
            "X-File-Size": str(result.file_size_bytes),
            "X-Generation-Time-Ms": str(result.generation_time_ms),
        },
        background=BackgroundTask(cleanup_files, result.cleanup_paths),
    )


__all__ = ["router"]
