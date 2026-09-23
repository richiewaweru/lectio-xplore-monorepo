"""Native lesson HTTP: Teaching Plan, Learn/Print admission, document edits, retries.

Registered at `/api/v1/v3/...` so current clients keep their URLs. These handlers
are the current product, not the legacy Studio generation island.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from application.unit_lesson.native_pipeline import _load_owned_generation
from core.auth.middleware import get_current_user
from core.database.models import GenerationModel
from core.database.session import async_session_factory
from core.entities.user import User

logger = logging.getLogger(__name__)

native_lesson_router = APIRouter(prefix="/v3", tags=["native-lesson"])


class LessonApproachApproveRequest(BaseModel):
    expected_revision: int = 1
    expected_content_hash: str | None = None
    teacher_note: str | None = None

class LessonApproachRejectRequest(BaseModel):
    expected_revision: int = 1
    teacher_note: str | None = None

class PageBlockPatchRequest(BaseModel):
    expected_document_revision: int
    content_patch: dict[str, Any]

class LectioDocumentPutRequest(BaseModel):
    expected_document_revision: int
    document: dict[str, Any]

class FigureVisualCallbackRequest(BaseModel):
    request_id: str
    block_id: str | None = None
    asset: dict[str, Any]

@native_lesson_router.get("/generations/{generation_id}/lesson-approach")
async def get_lesson_approach(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _load_owned_generation(generation_id, current_user.id)
    from print.generation.whole_lesson.repository import PageDocumentRepository

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        state = await repo.load_page_generation_state()
    if not state.get("teaching_plan"):
        raise HTTPException(status_code=404, detail="Teaching plan not ready")
    from curriculum.teaching_plan.revisions import teaching_plan_review_identity

    return {
        "generation_id": generation_id,
        "teaching_plan": state.get("teaching_plan"),
        "teaching_validation": state.get("teaching_validation"),
        "teaching_qc": state.get("teaching_qc"),
        "teaching_review": state.get("teaching_review"),
        "teaching_plan_identity": teaching_plan_review_identity(state),
        "lesson_packet": state.get("lesson_packet"),
        "catalogue": state.get("catalogue"),
    }

@native_lesson_router.post("/generations/{generation_id}/lesson-approach/approve")
async def post_lesson_approach_approve(
    generation_id: str,
    body: LessonApproachApproveRequest,
    current_user: User = Depends(get_current_user),
    path: str | None = Query(default=None),
) -> JSONResponse:
    await _load_owned_generation(generation_id, current_user.id)
    if not str(body.expected_content_hash or "").strip():
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEACHING_CONTENT_HASH_REQUIRED",
                "message": "Reload the Teaching Plan review and approve the displayed version.",
                "recovery_action": "reload_review",
            },
        )
    from application.unit_lesson.realize_print_handoff import realize_print_from_preparation
    from curriculum.teaching_plan.revisions import (
        TeachingRevisionConflictError,
        TeachingRevisionContentError,
    )
    from print.generation.whole_lesson.repository import PageDocumentRepository

    requested_path = (path or getattr(body, "path", None) or "print").strip().lower()
    if requested_path not in {"print", "learn"}:
        requested_path = "print"

    async with async_session_factory() as session:
        try:
            if requested_path == "learn":
                # Path-neutral teaching approval: persist approval without
                # queuing the Print whole-lesson worker.
                repo = PageDocumentRepository(session, generation_id)
                state = await repo.load_page_generation_state()
                if not state.get("teaching_plan"):
                    raise HTTPException(status_code=409, detail="no teaching plan to approve")
                state = await repo.save_teaching_review(
                    status="approved",
                    expected_revision=body.expected_revision,
                    expected_content_hash=body.expected_content_hash,
                    reviewed_by=current_user.id,
                    teacher_note=body.teacher_note,
                    queue=False,
                )
                # Stamp requested path for Units Learn generate.
                chunked = dict(state)
                chunked["requested_realization_path"] = "learn"
                generation = await session.get(GenerationModel, generation_id)
                if generation is not None:
                    generation.chunked_state_json = {
                        **(generation.chunked_state_json or {}),
                        **chunked,
                        "requested_realization_path": "learn",
                    }
                await session.commit()
                from curriculum.teaching_plan.revisions import teaching_plan_review_identity

                return JSONResponse(
                    status_code=200,
                    content={
                        "generation_id": generation_id,
                        "status": "teaching_approved",
                        "path": "learn",
                        "queued": False,
                        "next": "generate_learn",
                        "teaching_plan_identity": teaching_plan_review_identity(state),
                    },
                )

            repo = PageDocumentRepository(session, generation_id)
            state = await repo.load_page_generation_state()
            if not state.get("teaching_plan"):
                raise HTTPException(status_code=409, detail="no teaching plan to approve")
            state = await repo.save_teaching_review(
                status="approved",
                expected_revision=body.expected_revision,
                expected_content_hash=body.expected_content_hash,
                reviewed_by=current_user.id,
                teacher_note=body.teacher_note,
                queue=False,
                commit=False,
            )
            result = await realize_print_from_preparation(
                session,
                preparation_generation_id=generation_id,
                user_id=current_user.id,
                allow_standalone=True,
            )
            await session.commit()
        except HTTPException:
            raise
        except (TeachingRevisionConflictError, TeachingRevisionContentError) as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": exc.code,
                    "message": str(exc),
                    "recovery_action": "reprepare"
                    if isinstance(exc, TeachingRevisionContentError)
                    else None,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("lesson approach approve failed generation_id=%s", generation_id)
            raise HTTPException(status_code=500, detail=str(exc)[:400]) from exc
    from curriculum.teaching_plan.revisions import teaching_plan_review_identity

    return JSONResponse(
        status_code=202,
        content={
            **result,
            "generation_id": result.get("output_id"),
            "preparation_generation_id": generation_id,
            "status": result.get("status") or "queued",
            "path": "print",
            "document_version": 2,
            "teaching_plan_identity": teaching_plan_review_identity(state),
        },
    )

@native_lesson_router.post("/generations/{generation_id}/realize-learn")
async def post_realize_learn(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    response: Response = None,
) -> dict[str, Any]:
    """Admit Learn from an approved Teaching Plan on this preparation generation.

    Cross-domain handoff goes through application orchestration (not print→learn).
    """
    await _load_owned_generation(generation_id, current_user.id)
    from application.unit_lesson.realize_learn_handoff import realize_learn_from_preparation

    async with async_session_factory() as session:
        try:
            result = await realize_learn_from_preparation(
                session,
                preparation_generation_id=generation_id,
                user_id=current_user.id,
                admission_request_key=idempotency_key,
            )
            await session.commit()
            if response is not None and result.get("status") in {"queued", "running"}:
                response.status_code = 202
        except HTTPException:
            await session.rollback()
            raise
        except Exception as exc:
            await session.rollback()
            logger.exception("realize-learn failed generation_id=%s", generation_id)
            raise HTTPException(status_code=500, detail=str(exc)[:400]) from exc
    return result

@native_lesson_router.post("/generations/{generation_id}/realize-print")
async def post_realize_print(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Queue Print from an approved Teaching Plan on this preparation generation."""
    await _load_owned_generation(generation_id, current_user.id)
    from application.unit_lesson.realize_print_handoff import realize_print_from_preparation

    async with async_session_factory() as session:
        try:
            result = await realize_print_from_preparation(
                session,
                preparation_generation_id=generation_id,
                user_id=current_user.id,
                admission_request_key=idempotency_key,
                allow_standalone=True,
            )
            await session.commit()
        except HTTPException:
            await session.rollback()
            raise
        except Exception as exc:
            await session.rollback()
            logger.exception("realize-print failed generation_id=%s", generation_id)
            raise HTTPException(status_code=500, detail=str(exc)[:400]) from exc
    return result

@native_lesson_router.post("/generations/{generation_id}/lesson-approach/reject")
async def post_lesson_approach_reject(
    generation_id: str,
    body: LessonApproachRejectRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _load_owned_generation(generation_id, current_user.id)
    from print.generation.whole_lesson.repository import PageDocumentRepository

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        try:
            await repo.save_teaching_review(
                status="rejected",
                expected_revision=body.expected_revision,
                reviewed_by=current_user.id,
                teacher_note=body.teacher_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"generation_id": generation_id, "status": "rejected_by_teacher"}

@native_lesson_router.patch("/generations/{generation_id}/page-blocks/{block_id}")
async def patch_page_block(
    generation_id: str,
    block_id: str,
    body: PageBlockPatchRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _load_owned_generation(generation_id, current_user.id)
    from contracts.lectio_page import validate_document
    from print.generation.whole_lesson.events import make_event
    from print.generation.whole_lesson.repository import PageDocumentRepository
    from print.rendering.page_objects.document_assembly import reload_document

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        repo = PageDocumentRepository(session, generation_id)
        state = await repo.load_page_generation_state()
        current_rev = int(state.get("document_revision") or 0)
        if body.expected_document_revision != current_rev:
            raise HTTPException(status_code=409, detail="stale document revision")
        envelope = generation.document_json or {}
        document = reload_document(envelope)
        found = False
        for section in document.get("sections") or []:
            for block in section.get("blocks") or []:
                if block.get("id") == block_id:
                    content = dict(block.get("content") or {})
                    content.update(body.content_patch)
                    block["content"] = content
                    found = True
                    break
            if found:
                break
        if not found:
            raise HTTPException(status_code=404, detail=f"block {block_id!r} not found")
        errors = validate_document(document)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors[:5]))
        from print.rendering.page_objects.document_assembly import persist_document_json

        generation.document_json = persist_document_json(envelope, document)
        revision = await repo.bump_document_revision()
        await repo.append_event(
            make_event(
                "block_patched",
                generation_id=generation_id,
                block_id=block_id,
                status="ready",
            )
        )
        await session.commit()
    return {"generation_id": generation_id, "block_id": block_id, "document_revision": revision}

@native_lesson_router.get("/generations/{generation_id}/lectio-document")
async def get_lectio_document(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _load_owned_generation(generation_id, current_user.id)
    from print.generation.whole_lesson.repository import PageDocumentRepository
    from print.rendering.page_objects.document_assembly import reload_document

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        repo = PageDocumentRepository(session, generation_id)
        state = await repo.load_page_generation_state()
        envelope = generation.document_json or {}
        document = reload_document(envelope)
    return {
        "generation_id": generation_id,
        "document_revision": int(state.get("document_revision") or 0),
        "document": document,
    }

@native_lesson_router.put("/generations/{generation_id}/lectio-document")
async def put_lectio_document(
    generation_id: str,
    body: LectioDocumentPutRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Replace the native LectioDocument v2 with optimistic revision control."""
    await _load_owned_generation(generation_id, current_user.id)
    from contracts.lectio_page import validate_document
    from print.generation.whole_lesson.events import make_event
    from print.generation.whole_lesson.repository import PageDocumentRepository
    from print.rendering.page_objects.document_assembly import persist_document_json

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        repo = PageDocumentRepository(session, generation_id)
        state = await repo.load_page_generation_state()
        current_rev = int(state.get("document_revision") or 0)
        if body.expected_document_revision != current_rev:
            raise HTTPException(status_code=409, detail="stale document revision")
        errors = validate_document(body.document)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(str(err) for err in errors[:8]))
        envelope = generation.document_json or {}
        generation.document_json = persist_document_json(envelope, body.document)
        revision = await repo.bump_document_revision()
        await repo.append_event(
            make_event(
                "lectio_document_saved",
                generation_id=generation_id,
                status="ready",
            )
        )
        await session.commit()
    return {
        "generation_id": generation_id,
        "document_revision": revision,
        "document": body.document,
    }

@native_lesson_router.post("/generations/{generation_id}/visuals/callback")
async def post_figure_visual_callback(
    generation_id: str,
    body: FigureVisualCallbackRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Idempotent figure asset completion keyed by request_id."""
    await _load_owned_generation(generation_id, current_user.id)
    from print.generation.whole_lesson.repository import (
        PageDocumentRepository,
        VisualCompletionConflict,
        VisualCompletionInvariantError,
        VisualCompletionStateError,
        VisualRequestNotFound,
    )

    request_id = str(body.request_id or "").strip()
    if not request_id:
        raise HTTPException(status_code=400, detail="request_id is required")
    asset = dict(body.asset or {})
    asset["request_id"] = request_id

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        try:
            result = await repo.apply_visual_completion(
                request_id=request_id,
                asset=asset,
                supplied_block_id=body.block_id,
            )
        except VisualRequestNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (
            VisualCompletionConflict,
            VisualCompletionStateError,
            VisualCompletionInvariantError,
        ) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            from print.rendering.page_objects.visual_completion import VisualCompletionError

            if isinstance(exc, VisualCompletionError):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise

    return {
        "generation_id": result.generation_id,
        "block_id": result.block_id,
        "request_id": result.request_id,
        "status": result.status,
        "document_revision": result.document_revision,
        "idempotent": result.idempotent,
    }

@native_lesson_router.post("/generations/{generation_id}/visuals/retry")
async def post_visuals_retry(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Visuals-only redispath for native generations stuck in awaiting_visuals.

    Never requeues writers, form planning, teaching, or item generation.
    """
    await _load_owned_generation(generation_id, current_user.id)
    from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson
    from print.generation.whole_lesson.repository import PageDocumentRepository
    from print.generation.whole_lesson.visual_dispatch import dispatch_and_patch_from_repo

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        repo = PageDocumentRepository(session, generation_id)
        chunked = dict(generation.chunked_state_json or {})
        if not generation_is_native_whole_lesson(chunked, generation):
            raise HTTPException(
                status_code=409,
                detail="visuals/retry is only available for native whole-lesson generations",
            )
        status = str(generation.status or "")
        if status == "ready":
            # Narrowly reopen only persisted QC-flagged visuals. The repository
            # fences this transition and invalidates current revision proof.
            try:
                await repo.reopen_flagged_visuals()
                generation = await session.get(GenerationModel, generation_id)
                status = str(generation.status or "") if generation else status
            except Exception as exc:
                from print.generation.whole_lesson.repository import VisualCompletionStateError

                if isinstance(exc, VisualCompletionStateError):
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                raise
        if status != "awaiting_visuals":
            raise HTTPException(
                status_code=409,
                detail=f"visuals/retry requires awaiting_visuals, got {status!r}",
            )
        try:
            dispatch = await dispatch_and_patch_from_repo(
                session=session,
                generation_id=generation_id,
            )
        except Exception as exc:
            await repo.persist_visual_dispatch_failure(exc=exc)
            raise HTTPException(
                status_code=502,
                detail=f"visual redispath failed: {str(exc)[:400]}",
            ) from exc
        generation = await session.get(GenerationModel, generation_id)
        terminal = str(generation.status or status) if generation else status
        page = await repo.load_page_generation_state()
        last_error = (page.get("execution") or {}).get("last_error")
    return {
        "generation_id": generation_id,
        "status": terminal,
        "visual_dispatch": dispatch,
        "next_action": (
            "retry_visuals"
            if terminal == "awaiting_visuals"
            and (dispatch.get("failed") or last_error)
            else ("done" if terminal == "ready" else "wait_visuals")
        ),
        "error_detail": last_error if isinstance(last_error, dict) else None,
    }

@native_lesson_router.post("/generations/{generation_id}/retry-native")
async def post_retry_native(
    generation_id: str,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Accept-only native retry: durable checkpoint + worker-owned recovery.

    Routes by execution.last_error.stage:
    - item_generation → checkpoint item_generation (work_kind pre_worker_item_retry)
    - planning_teaching → checkpoint planning_teaching (work_kind pre_worker_teaching_retry)
    - post-approval stages → queued for worker reclaim
    Visual failures must use /visuals/retry.
    """
    model = await _load_owned_generation(generation_id, current_user.id)
    from print.generation.whole_lesson.native_retry import (
        NativeRetryConflict,
        accept_native_retry,
    )
    from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson
    from curriculum.planning.persistence import load_chunked_state

    state = await load_chunked_state(generation_id)
    if not generation_is_native_whole_lesson(state, model):
        raise HTTPException(
            status_code=409,
            detail="retry-native is only available for native whole-lesson generations",
        )
    try:
        result = await accept_native_retry(
            generation_id, user_id=current_user.id
        )
    except NativeRetryConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_type": exc.code,
                "message": str(exc),
                "stage": exc.status or str(model.status or ""),
                "retry_target": exc.target.value if exc.target else None,
                "generation_id": generation_id,
                **(exc.detail or {}),
            },
        ) from exc
    return JSONResponse(status_code=202, content=result)

