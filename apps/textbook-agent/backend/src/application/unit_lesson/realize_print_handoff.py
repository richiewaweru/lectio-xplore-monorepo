"""Shared Print realization from an approved Teaching Plan on a preparation generation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import (
    RealizationPayloadConflictError,
    admit_realization,
    get_realization,
)
from core.database.models import (
    GenerationModel,
    LessonProvenanceModel,
    NativeRealizationModel,
    PathLessonModel,
)
from curriculum.teaching_plan.consumers import (
    TeachingRevisionContentError,
    TeachingRevisionNotApprovedError,
    TeachingRevisionUnavailableError,
    accept_approved_teaching_revision,
)
from print.generation.native_production import teaching_plan_content_hash
from print.generation.whole_lesson.events import make_event
from print.generation.whole_lesson.repository import (
    PAGE_DOCUMENT_KEY,
    PageDocumentRepository,
    empty_execution_meta,
    empty_page_document_state,
)


async def realize_print_from_preparation(
    session: AsyncSession,
    *,
    preparation_generation_id: str,
    user_id: str,
    path_lesson_id: str | None = None,
    admission_request_key: str | None = None,
    allow_standalone: bool = False,
) -> dict[str, Any]:
    """Queue native Print from approved teaching. Does not re-approve the plan."""
    generation = await session.scalar(
        select(GenerationModel)
        .where(GenerationModel.id == preparation_generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if generation is None or generation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Preparation generation not found")

    lesson_id = path_lesson_id
    if not lesson_id:
        provenance = await session.get(LessonProvenanceModel, preparation_generation_id)
        if provenance is not None and provenance.path_lesson_id:
            lesson_id = provenance.path_lesson_id
        else:
            lesson = await session.scalar(
                select(PathLessonModel).where(PathLessonModel.pack_id == preparation_generation_id)
            )
            if lesson is not None:
                lesson_id = lesson.id
    standalone = not lesson_id
    source_chunked = (
        generation.chunked_state_json
        if isinstance(generation.chunked_state_json, dict)
        else {}
    )
    source_context = source_chunked.get("context")
    source_page = source_chunked.get(PAGE_DOCUMENT_KEY)
    lesson_packet = source_page.get("lesson_packet") if isinstance(source_page, dict) else None
    packet_lesson = lesson_packet.get("lesson") if isinstance(lesson_packet, dict) else None
    is_shared_path_preparation = bool(
        source_chunked.get("shared_preparation")
        or source_chunked.get("path_prepared")
        or (
            isinstance(source_context, dict)
            and (
                source_context.get("shared_preparation")
                or source_context.get("path_prepared")
                or source_context.get("path_lesson_id")
            )
        )
        or (isinstance(packet_lesson, dict) and packet_lesson.get("path_lesson_id"))
    )
    is_explicit_studio_generation = bool(
        source_chunked.get("native_whole_lesson")
        or (isinstance(source_context, dict) and source_context.get("native_whole_lesson"))
    )
    if standalone and is_shared_path_preparation:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRINT_PATH_PROVENANCE_MISSING",
                "message": "The Unit lesson link is missing. Restore its path provenance before creating Print.",
                "recovery_action": "reload_lesson",
            },
        )
    if standalone and not allow_standalone:
        raise HTTPException(
            status_code=409,
            detail="Cannot resolve path lesson for this preparation",
        )
    if standalone and not is_explicit_studio_generation:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRINT_STUDIO_ORIGIN_UNVERIFIED",
                "message": "This preparation has no verified Unit or Studio origin. Reload the lesson before creating Print.",
                "recovery_action": "reload_lesson",
            },
        )

    # Only the nested page document owns approval truth. A legacy outer wrapper
    # or stage string is not sufficient evidence to execute a new Print run.
    state = await PageDocumentRepository(
        session, preparation_generation_id
    ).load_page_generation_state()

    review = dict(state.get("teaching_review") or {})
    try:
        current_revision = int(review.get("revision") or 1)
        approved_revision = (
            int(review["approved_revision"])
            if review.get("approved_revision") is not None
            else None
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEACHING_REVIEW_IDENTITY_INVALID",
                "message": "Reload the Teaching Plan review before creating Print.",
            },
        ) from exc
    if (
        str(review.get("status") or "").lower() == "pending"
        and approved_revision is not None
        and current_revision > approved_revision
    ):
        # The user asked to create an output from the currently reviewed plan.
        # Do not let this consumer path silently approve a newer, unseen draft.
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEACHING_REVISION_PENDING_REVIEW",
                "message": "Review and approve the current Teaching Plan before creating Print.",
                "revision": current_revision,
                "approved_revision": approved_revision,
            },
        )

    try:
        teaching_plan = accept_approved_teaching_revision(state, consumer="print")
    except TeachingRevisionNotApprovedError as exc:
        raise HTTPException(
            status_code=409,
            detail="Approve the Teaching Plan before generating Print",
        ) from exc
    except TeachingRevisionUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TeachingRevisionContentError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc), "recovery_action": "reprepare"},
        ) from exc

    plan_hash = teaching_plan_content_hash(teaching_plan)

    if standalone:
        output_id = str(
            uuid5(
                NAMESPACE_URL,
                "lectio-print:{}:{}:{}:{}".format(
                    preparation_generation_id,
                    str(teaching_plan.teaching_plan_id or ""),
                    int(teaching_plan.revision or 1),
                    plan_hash,
                ),
            )
        )
        existing_output = await session.get(GenerationModel, output_id)
        if existing_output is None:
            await _create_print_output_generation(
                session,
                source=generation,
                source_state=state,
                realization=None,
                teaching_plan=teaching_plan.model_dump(mode="json"),
                teaching_plan_hash=plan_hash,
                output_id=output_id,
            )
            result_status = "queued"
            created = True
        else:
            metadata = (existing_output.chunked_state_json or {}).get("print_realization") or {}
            if (
                existing_output.user_id != user_id
                or metadata.get("realization_id") is not None
                or metadata.get("preparation_generation_id") != preparation_generation_id
                or metadata.get("teaching_plan_id") != str(teaching_plan.teaching_plan_id or "")
                or int(metadata.get("teaching_plan_revision") or 0)
                != int(teaching_plan.revision or 1)
                or metadata.get("teaching_plan_hash") != plan_hash
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "PRINT_OUTPUT_IDENTITY_CONFLICT",
                        "message": "An existing Studio output has a different pinned identity.",
                    },
                )
            result_status = str(existing_output.status or "queued")
            created = False
        return {
            "status": result_status,
            "path": "print",
            "preparation_generation_id": preparation_generation_id,
            "output_id": output_id,
            "realization_id": None,
            "realization_created": created,
            "teaching_plan_hash": plan_hash,
            "teaching_plan_revision": int(teaching_plan.revision or 1),
            "teaching_plan_id": str(teaching_plan.teaching_plan_id or ""),
            "open_href": f"/studio/print/{output_id}",
        }

    try:
        row, created = await admit_realization(
            session,
            path_lesson_id=lesson_id,
            path="print",
            teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
            teaching_plan_revision=int(teaching_plan.revision or 1),
            teaching_plan_hash=plan_hash,
            preparation_generation_id=preparation_generation_id,
            pack_id=None,
            output_id=None,
            admission_request_key=admission_request_key,
            admission_payload_hash=plan_hash,
        )
    except RealizationPayloadConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    output_id = str(row.output_id or "").strip()
    if output_id == preparation_generation_id:
        # Historical rows keep their old document links. Never requeue the
        # shared preparation as a new Print worker job.
        if str(row.status) in {"ready", "completed", "published"}:
            return _print_result(row, output_id=output_id, plan_hash=plan_hash)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRINT_LEGACY_OUTPUT_READ_ONLY",
                "message": "This legacy Print record is still linked to preparation. Reprepare to create a detached Print output.",
                "recovery_action": "reprepare",
            },
        )
    if output_id:
        existing_output = await session.get(GenerationModel, output_id)
        if existing_output is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PRINT_OUTPUT_MISSING",
                    "message": "The Print realization points to a missing output. Reprepare to recover.",
                    "recovery_action": "reprepare",
                },
            )
        metadata = (existing_output.chunked_state_json or {}).get("print_realization") or {}
        expected_output_identity = {
            "realization_id": row.id,
            "preparation_generation_id": preparation_generation_id,
            "teaching_plan_id": str(teaching_plan.teaching_plan_id or ""),
            "teaching_plan_revision": int(teaching_plan.revision or 1),
            "teaching_plan_hash": plan_hash,
        }
        if existing_output.user_id != user_id or any(
            metadata.get(key) != value for key, value in expected_output_identity.items()
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PRINT_OUTPUT_IDENTITY_CONFLICT",
                    "message": "The Print realization points to an output with a different owner or pinned identity.",
                    "recovery_action": "reprepare",
                },
            )
    else:
        output_id = await _create_print_output_generation(
            session,
            source=generation,
            source_state=state,
            realization=row,
            teaching_plan=teaching_plan.model_dump(mode="json"),
            teaching_plan_hash=plan_hash,
        )
        row.output_id = output_id
        row.pack_id = None
        row.status = "queued"
        row.error_summary = None
        await session.flush()

    return {
        "status": str(row.status or "queued"),
        "path": "print",
        "preparation_generation_id": preparation_generation_id,
        "output_id": output_id,
        "realization_id": row.id,
        "realization_created": created,
        "teaching_plan_hash": plan_hash,
        "teaching_plan_revision": int(teaching_plan.revision or 1),
        "teaching_plan_id": str(teaching_plan.teaching_plan_id or ""),
        "open_href": f"/studio/print/{output_id}",
    }


def _print_result(
    row: NativeRealizationModel, *, output_id: str, plan_hash: str
) -> dict[str, Any]:
    return {
        "status": str(row.status or "ready"),
        "path": "print",
        "preparation_generation_id": row.preparation_generation_id,
        "output_id": output_id,
        "realization_id": row.id,
        "realization_created": False,
        "teaching_plan_hash": plan_hash,
        "teaching_plan_revision": int(row.teaching_plan_revision),
        "teaching_plan_id": row.teaching_plan_id,
        "open_href": f"/studio/print/{output_id}",
    }


async def _create_print_output_generation(
    session: AsyncSession,
    *,
    source: GenerationModel,
    source_state: dict[str, Any],
    realization: NativeRealizationModel | None,
    teaching_plan: dict[str, Any],
    teaching_plan_hash: str,
    output_id: str | None = None,
) -> str:
    """Create a worker-owned Print checkpoint without changing its preparation."""
    output_id = output_id or str(uuid4())
    page_state = empty_page_document_state()
    for key in (
        "lesson_packet",
        "lesson_legality",
        "catalogue",
        "teaching_validation",
        "teaching_qc",
        "teaching_plan_id",
    ):
        if key in source_state:
            page_state[key] = deepcopy(source_state[key])
    # Pin the consumer-verified immutable snapshot. Empty state construction
    # deliberately excludes old form plans, writer checkpoints, visual state,
    # documents, errors, and leases from a legacy Print preparation.
    page_state["teaching_plan"] = deepcopy(teaching_plan)
    pinned_revision = int(
        realization.teaching_plan_revision
        if realization is not None
        else teaching_plan.get("revision") or 1
    )
    revision_rows = source_state.get("teaching_revisions")
    pinned_record = next(
        (
            deepcopy(record)
            for record in revision_rows or []
            if isinstance(record, dict)
            and int(record.get("revision") or 0) == pinned_revision
        ),
        None,
    )
    if pinned_record is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRINT_APPROVED_SNAPSHOT_MISSING",
                "message": "The pinned approved Teaching Plan snapshot is unavailable. Reprepare to recover.",
                "recovery_action": "reprepare",
            },
        )
    # A retry may pin an older, hash-verified revision that the source ledger
    # now calls superseded. The new output carries an immutable approved
    # snapshot of that exact revision; the source ledger itself stays intact.
    pinned_record["status"] = "approved"
    page_state["teaching_revisions"] = [pinned_record]
    page_state["teaching_review"] = {
        "status": "approved",
        "revision": pinned_revision,
        "approved_revision": pinned_revision,
        "reviewed_by": pinned_record.get("reviewed_by"),
        "reviewed_at": pinned_record.get("approved_at"),
        "teacher_note": pinned_record.get("teacher_note"),
    }
    page_state["execution"] = empty_execution_meta()
    page_state["events"] = [
        {
            **make_event(
                "print_realization_queued",
                generation_id=output_id,
                status="queued",
            ),
            "preparation_generation_id": source.id,
            "realization_id": realization.id if realization is not None else None,
            "teaching_plan_revision": pinned_revision,
            "teaching_plan_hash": teaching_plan_hash,
        }
    ]
    page_state["document_revision"] = 0

    source_chunked = source.chunked_state_json if isinstance(source.chunked_state_json, dict) else {}
    # Copy only immutable inputs or shared semantic artifacts. Never inherit
    # preparation execution leases, statuses, output documents, or checkpoints.
    output_chunked: dict[str, Any] = {
        "stage": "queued",
        "native_whole_lesson": True,
        "requested_realization_path": "print",
        "print_realization": {
            "realization_id": realization.id if realization is not None else None,
            "realization_revision": int(realization.realization_revision) if realization is not None else 1,
            "preparation_generation_id": source.id,
            "teaching_plan_id": (
                realization.teaching_plan_id
                if realization is not None
                else str(teaching_plan.get("teaching_plan_id") or "")
            ),
            "teaching_plan_revision": pinned_revision,
            "teaching_plan_hash": teaching_plan_hash,
        },
        PAGE_DOCUMENT_KEY: page_state,
    }
    for key in ("context", "structural_plan", "smart_lesson"):
        value = source_chunked.get(key)
        if value is not None:
            copied = deepcopy(value)
            if key == "context" and isinstance(copied, dict):
                copied.pop("shared_preparation", None)
                copied.pop("path_prepared", None)
                copied["native_whole_lesson"] = True
                copied["requested_realization_path"] = "print"
                copied["preparation_generation_id"] = source.id
            output_chunked[key] = copied

    output = GenerationModel(
        id=output_id,
        user_id=source.user_id,
        subject=source.subject,
        context=source.context,
        mode=source.mode,
        status="queued",
        document_json=None,
        error=None,
        error_type=None,
        error_code=None,
        requested_template_id=source.requested_template_id,
        resolved_template_id=source.resolved_template_id,
        requested_preset_id=source.requested_preset_id,
        resolved_preset_id=source.resolved_preset_id,
        section_count=None,
        quality_passed=None,
        generation_time_seconds=None,
        planning_spec_json=source.planning_spec_json,
        chunked_state_json=output_chunked,
        report_json={"native_stage": "queued", "process_status": "running"},
        pack_id=None,
        pack_resource_id=None,
        pack_resource_label=None,
        variant_label=None,
        variant_spec=None,
    )
    session.add(output)
    await session.flush()
    return output_id


async def retry_print_realization(
    session: AsyncSession,
    *,
    realization_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Retry one failed Print identity on a fresh output generation."""
    row = await get_realization(session, realization_id)
    if row is None or row.path != "print":
        raise HTTPException(status_code=404, detail="Print realization not found")
    preparation_id = str(row.preparation_generation_id or "").strip()
    source = (
        await session.scalar(
            select(GenerationModel)
            .where(GenerationModel.id == preparation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if preparation_id
        else None
    )
    if source is None or source.user_id != user_id:
        raise HTTPException(status_code=404, detail="Print preparation not found")

    # Re-read the realization under the same transaction after the source lock.
    # The source lock serializes retries with preparation edits; the realization
    # lock and conditional update make duplicate retries single-winner.
    row = await session.scalar(
        select(NativeRealizationModel)
        .where(NativeRealizationModel.id == realization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        row is None
        or row.path != "print"
        or str(row.preparation_generation_id or "") != preparation_id
    ):
        raise HTTPException(status_code=404, detail="Print realization not found")
    if str(row.status) not in {"failed_recoverable", "failed_terminal", "failed"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRINT_RETRY_NOT_FAILED",
                "message": "Only a failed Print realization can be retried.",
            },
        )
    state = await PageDocumentRepository(session, preparation_id).load_page_generation_state()
    try:
        plan = accept_approved_teaching_revision(
            state,
            consumer="print",
            revision=int(row.teaching_plan_revision),
        )
    except TeachingRevisionUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "PRINT_APPROVED_SNAPSHOT_MISSING", "message": str(exc)},
        ) from exc
    except TeachingRevisionNotApprovedError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "PRINT_APPROVED_SNAPSHOT_INVALID", "message": str(exc)},
        ) from exc
    except TeachingRevisionContentError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc), "recovery_action": "reprepare"},
        ) from exc
    plan_hash = teaching_plan_content_hash(plan)
    if (
        str(plan.teaching_plan_id or "") != str(row.teaching_plan_id)
        or plan_hash != str(row.teaching_plan_hash)
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRINT_PINNED_IDENTITY_MISMATCH",
                "message": "The failed Print run does not match the stored approved snapshot.",
                "recovery_action": "reprepare",
            },
        )

    new_output_id = str(uuid4())
    try:
        reserved = await session.execute(
            update(NativeRealizationModel)
            .where(
                NativeRealizationModel.id == realization_id,
                NativeRealizationModel.path == "print",
                NativeRealizationModel.preparation_generation_id == preparation_id,
                NativeRealizationModel.status.in_(
                    {"failed_recoverable", "failed_terminal", "failed"}
                ),
                NativeRealizationModel.teaching_plan_id == row.teaching_plan_id,
                NativeRealizationModel.teaching_plan_revision == row.teaching_plan_revision,
                NativeRealizationModel.teaching_plan_hash == row.teaching_plan_hash,
            )
            .values(
                realization_revision=NativeRealizationModel.realization_revision + 1,
                output_id=new_output_id,
                status="queued",
                error_summary=None,
            )
        )
    except OperationalError as exc:
        # SQLite does not implement SELECT FOR UPDATE; competing test/runtime
        # connections can surface its writer lock instead of waiting like
        # PostgreSQL. End the losing transaction and return the same typed
        # conflict that the conditional update returns after a wait.
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRINT_RETRY_ALREADY_CLAIMED",
                "message": "This Print retry was already accepted. Reload the realization status.",
            },
        ) from exc
    if int(reserved.rowcount or 0) != 1:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRINT_RETRY_ALREADY_CLAIMED",
                "message": "This Print retry was already accepted. Reload the realization status.",
            },
        )
    await session.flush()
    row = await session.scalar(
        select(NativeRealizationModel)
        .where(NativeRealizationModel.id == realization_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Print realization not found")
    await _create_print_output_generation(
        session,
        source=source,
        source_state=state,
        realization=row,
        teaching_plan=plan.model_dump(mode="json"),
        teaching_plan_hash=plan_hash,
        output_id=new_output_id,
    )
    return {
        "status": "queued",
        "path": "print",
        "preparation_generation_id": preparation_id,
        "output_id": new_output_id,
        "realization_id": row.id,
        "realization_revision": int(row.realization_revision),
        "teaching_plan_revision": int(row.teaching_plan_revision),
        "teaching_plan_hash": plan_hash,
        "open_href": f"/studio/print/{new_output_id}",
    }


__all__ = ["realize_print_from_preparation"]
