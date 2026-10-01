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
from document.shared_lesson.qa_runtime import load_run_quality_flags
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
from infra.database.models import (
    EditableLessonModel,
    GenerationBuildModel,
    GenerationModel,
    GenerationRunModel,
)
from infra.database.session import get_async_session
from infra.execution.checkpoints import content_hash
from infra.generation_runtime.http import _run_status
from infra.generation_runtime.repository import (
    InvalidRunTransition,
    RunAdmissionConflict,
    RunNotFound,
    cancel_run,
    get_run_status,
)

router = APIRouter(prefix="/api/v1/shared-documents", tags=["shared-documents"])


class SharedDocumentAdmissionRequest(BaseModel):
    """Closed owner-scoped request for a shadow SharedDocument generation."""

    model_config = ConfigDict(extra="forbid")

    path_lesson_id: str = Field(min_length=1)
    preparation_generation_id: str = Field(min_length=1)
    request_key: str = Field(min_length=1)


class ReviewDraftTextEdit(BaseModel):
    """One allowlisted text-only edit targeting an existing node.

    ``task_*`` fields target the SharedTaskSpec behind a ``task_anchor`` node
    (``node_id`` is the anchor). Only wording may change: the prompt, the text
    of an id-keyed choice option (``option_id``), or one feedback message
    (``feedback_key``: ``correct``/``incorrect``/``partial`` or
    ``by_option.<option id>``). The answer key is never editable.
    """

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
        "task_prompt",
        "task_option_text",
        "task_feedback_text",
    ]
    value: str = Field(min_length=1)
    item_index: int | None = Field(default=None, ge=0)
    row_index: int | None = Field(default=None, ge=0)
    column_index: int | None = Field(default=None, ge=0)
    option_id: str | None = Field(default=None, min_length=1)
    feedback_key: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_indices(self) -> ReviewDraftTextEdit:
        if (self.option_id is not None) != (self.field == "task_option_text"):
            raise ValueError("option_id is required for, and only valid with, task_option_text")
        if (self.feedback_key is not None) != (self.field == "task_feedback_text"):
            raise ValueError(
                "feedback_key is required for, and only valid with, task_feedback_text"
            )
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


def _apply_task_text_edit(task: dict[str, Any], edit: ReviewDraftTextEdit) -> bool:
    """Apply one wording edit to a task payload; False when the target is absent.

    Whether the edit is *allowed* (answer key and structure untouched) is
    proven afterwards by ``prove_review_draft_revision``.
    """
    if edit.field == "task_prompt":
        task["prompt"] = edit.value
        return True
    if edit.field == "task_option_text":
        options = (task.get("response") or {}).get("options")
        if not isinstance(options, list):
            return False
        for option in options:
            if isinstance(option, dict) and option.get("id") == edit.option_id and "text" in option:
                option["text"] = edit.value
                return True
        return False
    if edit.field == "task_feedback_text":
        feedback = task.get("feedback")
        if not isinstance(feedback, dict) or edit.feedback_key is None:
            return False
        parts = edit.feedback_key.split(".")
        target: Any = feedback
        for part in parts[:-1]:
            target = target.get(part) if isinstance(target, dict) else None
        if not isinstance(target, dict) or not isinstance(target.get(parts[-1]), str):
            return False
        target[parts[-1]] = edit.value
        return True
    return False


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


@router.get("/quality-flags")
async def get_shared_document_quality_flags(
    editable_lesson_id: str | None = None,
    generation_id: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Non-blocking quality notes for a Learn lesson or Print output.

    Owner-scoped. Resolves the SharedDocument Run behind the given Learn
    editable lesson or Print/Learn output and returns the advisory flags
    recorded on its document QA WorkItem (empty when none, or when the item
    predates the shared document pipeline).
    """
    if bool(editable_lesson_id) == bool(generation_id):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of editable_lesson_id or generation_id.",
        )
    run_id: str | None
    if editable_lesson_id:
        run_id = await session.scalar(
            select(EditableLessonModel.shared_document_run_id).where(
                EditableLessonModel.id == editable_lesson_id,
                EditableLessonModel.user_id == current_user.id,
            )
        )
    else:
        run_id = await session.scalar(
            select(GenerationModel.shared_document_run_id).where(
                GenerationModel.id == generation_id,
                GenerationModel.user_id == current_user.id,
            )
        )
    flags = (
        await load_run_quality_flags(session, run_id=run_id, owner_user_id=current_user.id)
        if run_id
        else ()
    )
    return {
        "run_id": run_id,
        "flags": [flag.model_dump(mode="json") for flag in flags],
    }


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
    tasks_by_id = {task["id"]: task for task in payload.get("tasks") or []}
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
        elif field_name.startswith("task_") and node["kind"] == "task_anchor":
            task = tasks_by_id.get(node.get("task_spec_id"))
            if task is None or not _apply_task_text_edit(task, edit):
                raise HTTPException(status_code=422, detail="Review edit target is invalid")
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



_REGENERATABLE_RUN_STATUSES = frozenset({"failed_recoverable", "failed_terminal", "cancelled"})


@router.post("/runs/{run_id}/regenerate", status_code=202)
async def post_shared_document_regenerate(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Replace a flagged or failed SharedDocument Run with a fresh bounded attempt.

    For defects a reviewer cannot fix by editing wording (e.g. a task whose
    answer key itself is wrong). The current Run is cancelled if still
    recoverable, then the next attempt is admitted through the same
    deterministic, bounded ``ensure_shared_document_run`` keys that Learn and
    Print use, so every consumer converges on the new Run. READY and active
    Runs are never replaced here.
    """
    from document.shared_lesson.realization_source import (
        RealizationAttemptsExhausted,
        RealizationSourceNotFound,
        ensure_shared_document_run,
    )

    row = (
        await session.execute(
            select(GenerationRunModel, GenerationBuildModel.path_lesson_id)
            .join(GenerationBuildModel, GenerationBuildModel.id == GenerationRunModel.build_id)
            .where(
                GenerationRunModel.id == run_id,
                GenerationRunModel.owner_user_id == current_user.id,
                GenerationRunModel.run_type == "shared_document",
            )
        )
    ).first()
    if row is None:
        raise _not_found()
    run, path_lesson_id = row
    if run.status not in _REGENERATABLE_RUN_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SHARED_DOCUMENT_NOT_REGENERATABLE",
                "message": "Only a flagged or failed lesson document can be regenerated.",
            },
        )
    try:
        if run.status == "failed_recoverable":
            await cancel_run(session, run_id=run.id, owner_user_id=current_user.id)
        replacement = await ensure_shared_document_run(
            session, owner_user_id=current_user.id, path_lesson_id=path_lesson_id
        )
        await session.commit()
    except RealizationAttemptsExhausted as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SHARED_DOCUMENT_ATTEMPTS_EXHAUSTED",
                "message": "This lesson's document attempts are used up; regenerate the plan instead.",
            },
        ) from exc
    except (RealizationSourceNotFound, InvalidRunTransition, RunNotFound) as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Lesson document cannot be regenerated") from exc
    return {
        "status": replacement.status,
        "replaced_run_id": run.id,
        "run_id": replacement.id,
        "path_lesson_id": path_lesson_id,
    }


__all__ = [
    "ReviewDraftSubmitRequest",
    "SharedDocumentAdmissionRequest",
    "get_shared_document_preview",
    "get_shared_document_review_draft",
    "post_shared_document_review_draft_revision",
    "post_shared_document_review_draft_submit",
    "post_shared_document_generation",
    "post_shared_document_regenerate",
    "router",
]
