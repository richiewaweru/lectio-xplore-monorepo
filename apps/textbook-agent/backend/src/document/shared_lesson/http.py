"""Owner-scoped, read-only HTTP preview for immutable shared documents."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.user import User
from document.shared_lesson.approved_source import ApprovedSourceVerificationError
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import (
    SharedLessonDocument,
    build_shared_lesson_document,
)
from document.shared_lesson.repository import (
    SharedLessonDocumentRepositoryError,
    load_shared_lesson_document,
    save_shared_lesson_document,
)
from document.shared_lesson.review_revision import (
    ReviewRevisionValidationError,
    prove_review_draft_revision,
)
from document.shared_lesson.review_submit import (
    ReviewSubmitConflict,
    ReviewSubmitError,
    ReviewSubmitInvalid,
    ReviewSubmitNotFound,
    load_review_draft_context,
    submit_review_draft_for_requalification,
)
from document.shared_lesson.run_admission import (
    SharedRunAdmissionError,
    admit_shared_document_run,
)
from infra.auth.middleware import get_current_user
from infra.database.models import GenerationBuildModel, GenerationRunModel
from infra.database.session import get_async_session
from infra.execution.checkpoints import content_hash
from infra.generation_runtime.http import _run_status
from infra.generation_runtime.repository import RunAdmissionConflict, RunNotFound, get_run_status

router = APIRouter(prefix="/api/v1/shared-documents", tags=["shared-documents"])


class SharedDocumentAdmissionRequest(BaseModel):
    """Closed owner-scoped request for a shadow SharedDocument generation."""

    model_config = ConfigDict(extra="forbid")

    path_lesson_id: str = Field(min_length=1)
    preparation_generation_id: str = Field(min_length=1)
    request_key: str = Field(min_length=1)


class ReviewDraftTextEdit(BaseModel):
    """One allowlisted text-only edit targeting an existing ordinary node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    field: Literal[
        "text",
        "callout_title",
        "callout_body",
        "figure_caption",
        "figure_alt_text",
        "list_item_text",
        "table_cell_text",
        "accessibility_description",
    ]
    value: str = Field(min_length=1)
    item_index: int | None = Field(default=None, ge=0)
    row_index: int | None = Field(default=None, ge=0)
    column_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_indices(self) -> ReviewDraftTextEdit:
        if self.field == "list_item_text":
            if self.item_index is None or self.row_index is not None or self.column_index is not None:
                raise ValueError("list_item_text requires only item_index")
        elif self.field == "table_cell_text":
            if self.row_index is None or self.column_index is None or self.item_index is not None:
                raise ValueError("table_cell_text requires row_index and column_index")
        elif any(
            value is not None for value in (self.item_index, self.row_index, self.column_index)
        ):
            raise ValueError("indices are only valid for list and table text edits")
        return self


class ReviewDraftRevisionRequest(BaseModel):
    """Closed optimistic-concurrency request for one immutable draft revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_revision: int = Field(ge=1)
    expected_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    edits: tuple[ReviewDraftTextEdit, ...] = Field(min_length=1)


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


@router.post("/generations", status_code=202)
async def post_shared_document_generation(
    body: SharedDocumentAdmissionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Queue one owner-scoped SharedDocument Run from an approved preparation."""

    try:
        async with session.begin():
            result = await admit_shared_document_run(
                session,
                owner_user_id=current_user.id,
                path_lesson_id=body.path_lesson_id,
                preparation_generation_id=body.preparation_generation_id,
                request_key=body.request_key,
            )
    except (RunNotFound, ApprovedSourceVerificationError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except (RunAdmissionConflict, SharedRunAdmissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail="SharedDocument admission failed") from exc

    run = await get_run_status(session, run_id=result.run.id, owner_user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="SharedDocument Run not found")
    status = _run_status(run)
    return {
        **status,
        "run_id": result.run.id,
        "sourcebook_work_item_id": result.sourcebook_work_item.id,
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


async def _load_review_draft_context(
    session: AsyncSession, *, run_id: str, owner_user_id: str
) -> tuple[GenerationRunModel, str, SharedLessonDocument, list[ContinuityIssue]]:
    """Resolve the immutable semantic-issue origin and its latest saved revision."""
    try:
        context = await load_review_draft_context(
            session, run_id=run_id, owner_user_id=owner_user_id
        )
    except ReviewSubmitError:
        raise _not_found() from None
    return context.run, context.path_lesson_id, context.latest, list(context.issues)


@router.get("/runs/{run_id}/review-draft")
async def get_shared_document_review_draft(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Return the latest deterministic-QA-passing semantic ISSUE revision."""
    _run, _path_lesson_id, document, issues = await _load_review_draft_context(
        session, run_id=run_id, owner_user_id=current_user.id
    )
    digest = shared_lesson_content_hash(document)

    return {
        "status": "draft",
        "draft": {
            "id": document.id,
            "revision": document.revision,
            "hash": digest,
        },
        "document": document.model_dump(mode="json"),
        "issues": [issue.model_dump(mode="json") for issue in issues],
    }


@router.post("/runs/{run_id}/review-draft/revisions", status_code=201)
async def post_shared_document_review_draft_revision(
    run_id: str,
    body: ReviewDraftRevisionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Save one immutable text-only correction revision for an owned draft."""
    try:
        _run, path_lesson_id, current, _issues = await _load_review_draft_context(
            session, run_id=run_id, owner_user_id=current_user.id
        )
    except HTTPException:
        raise
    if current.revision != body.expected_revision or current.content_hash != body.expected_hash:
        raise HTTPException(status_code=409, detail="Review draft changed; reload before editing")

    payload = current.model_dump(mode="json")
    sections = {section["id"]: section for section in payload["sections"]}
    for edit in body.edits:
        section = sections.get(edit.section_id)
        if section is None:
            raise HTTPException(status_code=422, detail="Review edit target is invalid")
        node = next((node for node in section["nodes"] if node["id"] == edit.node_id), None)
        if node is None:
            raise HTTPException(status_code=422, detail="Review edit target is invalid")
        field_name = edit.field
        if field_name == "text" and node["kind"] in {"paragraph", "heading"}:
            node["display"]["text"] = edit.value
        elif field_name == "callout_title" and node["kind"] == "callout":
            node["display"]["title"] = edit.value
        elif field_name == "callout_body" and node["kind"] == "callout":
            node["display"]["body"] = edit.value
        elif field_name == "figure_caption" and node["kind"] == "figure":
            node["display"]["caption"] = edit.value
        elif field_name == "figure_alt_text" and node["kind"] == "figure":
            node["accessibility"]["alt_text"] = edit.value
        elif field_name == "accessibility_description" and node["kind"] in {
            "paragraph",
            "heading",
            "list",
            "table",
            "callout",
        }:
            node["accessibility"]["description"] = edit.value
        elif field_name == "list_item_text" and node["kind"] == "list":
            items = node["display"]["items"]
            if edit.item_index is None or edit.item_index >= len(items):
                raise HTTPException(status_code=422, detail="Review edit target is invalid")
            items[edit.item_index] = edit.value
        elif field_name == "table_cell_text" and node["kind"] == "table":
            rows = node["display"]["rows"]
            if (
                edit.row_index is None
                or edit.column_index is None
                or edit.row_index >= len(rows)
                or edit.column_index >= len(rows[edit.row_index])
            ):
                raise HTTPException(status_code=422, detail="Review edit target is invalid")
            rows[edit.row_index][edit.column_index] = edit.value
        else:
            raise HTTPException(status_code=422, detail="Review edit field is not allowed for target")

    payload["revision"] = current.revision + 1
    payload.pop("content_hash", None)
    try:
        revised = build_shared_lesson_document(payload)
    except (TypeError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail="Review draft revision is invalid") from exc
    try:
        prove_review_draft_revision(current, revised)
    except ReviewRevisionValidationError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=422, detail="Review draft revision contains a forbidden change"
        ) from exc
    try:
        await save_shared_lesson_document(
            session,
            path_lesson_id=path_lesson_id,
            document=revised,
        )
        await session.commit()
    except (SharedLessonDocumentRepositoryError, TypeError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Review draft revision could not be saved") from exc

    return await get_shared_document_review_draft(
        run_id, current_user=current_user, session=session
    )


class ReviewDraftSubmitRequest(BaseModel):
    """Closed optimistic-concurrency request to requalify the latest draft."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_revision: int = Field(ge=1)
    expected_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/runs/{run_id}/review-draft/submit", status_code=202)
async def post_shared_document_review_draft_submit(
    run_id: str,
    body: ReviewDraftSubmitRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Revalidate the latest saved draft and admit it for requalification.

    This never calls the semantic QA provider inline. It proves the saved
    edits are allowlisted text-only corrections, recomputes deterministic QA,
    and admits a linked document QA replacement in the same transaction. An
    edit that touched a figure-containing section also regenerates that
    section's figure media as linked replacement WorkItems in the same
    transaction, since the figure's media binding is keyed to the section's
    output hash and would otherwise go stale. The existing post-section
    pipeline then waits for that regenerated media, executes semantic QA
    against this exact edited revision, and finalizes it on PASS.
    """
    try:
        async with session.begin():
            outcome = await submit_review_draft_for_requalification(
                session,
                run_id=run_id,
                owner_user_id=current_user.id,
                expected_revision=body.expected_revision,
                expected_hash=body.expected_hash,
            )
    except ReviewSubmitNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ReviewSubmitConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ReviewSubmitInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Review draft submission failed") from exc

    run = await get_run_status(session, run_id=run_id, owner_user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="SharedDocument Run not found")
    status = _run_status(run)
    return {
        **status,
        "run_id": run_id,
        "document_id": outcome.document_id,
        "document_revision": outcome.document_revision,
        "work_item_id": outcome.work_item_id,
    }


__all__ = [
    "ReviewDraftSubmitRequest",
    "SharedDocumentAdmissionRequest",
    "get_shared_document_preview",
    "get_shared_document_review_draft",
    "post_shared_document_review_draft_revision",
    "post_shared_document_review_draft_submit",
    "post_shared_document_generation",
    "router",
]
