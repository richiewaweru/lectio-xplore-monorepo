"""Admit and execute Learn from an immutable approved Teaching Plan."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import (
    RealizationPayloadConflictError,
    to_identity,
)
from core.database.models import (
    EditableLessonModel,
    GenerationModel,
    LessonProvenanceModel,
    NativeRealizationModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)
from curriculum.teaching_plan.consumers import (
    TeachingRevisionContentError,
    TeachingRevisionNotApprovedError,
    TeachingRevisionUnavailableError,
    accept_approved_teaching_revision,
)
from infra.authoring import AuthoringProvider
from learn.generation.fencing import LEARN_EXECUTION_KEY, empty_learn_execution_meta
from learn.generation.native_execution import produce_learn_from_approved_teaching
from learn.generation.native_production import teaching_plan_content_hash
from print.generation.whole_lesson.repository import PageDocumentRepository
from curriculum.planning.persistence import load_chunked_state


async def _load_preparation_for_update(
    session: AsyncSession, *, preparation_generation_id: str, user_id: str
) -> GenerationModel:
    result = await session.execute(
        select(GenerationModel)
        .where(GenerationModel.id == preparation_generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    generation = result.scalar_one_or_none()
    if generation is None or generation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Preparation generation not found")
    return generation


async def _resolve_path_lesson(
    session: AsyncSession,
    *,
    preparation_generation_id: str,
    user_id: str,
    path_lesson_id: str | None,
) -> PathLessonModel:
    lesson_id = path_lesson_id
    if not lesson_id:
        provenance = await session.get(LessonProvenanceModel, preparation_generation_id)
        if provenance is not None and provenance.path_lesson_id:
            lesson_id = provenance.path_lesson_id
        else:
            lesson = await session.scalar(
                select(PathLessonModel).where(
                    PathLessonModel.pack_id == preparation_generation_id
                )
            )
            lesson_id = lesson.id if lesson is not None else None
    if not lesson_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "LEARN_PATH_LESSON_REQUIRED",
                "message": "Learn generation requires an owning Unit lesson.",
                "recovery_action": "open_unit_lesson",
            },
        )

    result = await session.execute(
        select(PathLessonModel)
        .join(PathVersionModel, PathVersionModel.id == PathLessonModel.path_version_id)
        .join(UnitModel, UnitModel.id == PathVersionModel.unit_id)
        .where(PathLessonModel.id == lesson_id, UnitModel.owner_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    lesson = result.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Unit lesson not found")
    provenance = await session.get(LessonProvenanceModel, preparation_generation_id)
    if lesson.pack_id != preparation_generation_id and not (
        provenance is not None and provenance.path_lesson_id == lesson.id
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "LEARN_PREPARATION_PATH_MISMATCH",
                "message": "The preparation is not linked to this Unit lesson.",
                "recovery_action": "reprepare",
            },
        )
    return lesson


async def _load_page_state(
    session: AsyncSession, generation: GenerationModel
) -> dict[str, Any]:
    try:
        return await PageDocumentRepository(session, generation.id).load_page_generation_state()
    except (KeyError, ValueError):
        try:
            return await load_chunked_state(generation.id, session)
        except ValueError:
            return dict(generation.chunked_state_json or {})


def _verified_plan(
    state: dict[str, Any], *, revision: int | None = None
):
    try:
        plan = accept_approved_teaching_revision(
            state, consumer="learn", revision=revision
        )
    except TeachingRevisionNotApprovedError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEACHING_REVISION_NOT_APPROVED",
                "message": "Approve the Teaching Plan before generating Learn.",
                "recovery_action": "review_teaching_plan",
            },
        ) from exc
    except TeachingRevisionUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEACHING_REVISION_UNAVAILABLE",
                "message": str(exc),
                "recovery_action": "reprepare",
            },
        ) from exc
    except TeachingRevisionContentError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc), "recovery_action": "reprepare"},
        ) from exc
    return plan


async def _ensure_queued_output(
    session: AsyncSession,
    *,
    realization: NativeRealizationModel,
    user_id: str,
    subject: str,
    title: str,
) -> GenerationModel:
    output_id = str(realization.output_id or "")
    if not output_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "LEARN_OUTPUT_ID_MISSING",
                "message": "The Learn realization has no output identity.",
                "recovery_action": "reprepare",
            },
        )
    output = await session.get(GenerationModel, output_id)
    if output is not None:
        if output.user_id != user_id:
            raise HTTPException(status_code=409, detail={"code": "LEARN_OUTPUT_OWNER_MISMATCH"})
        state = output.chunked_state_json if isinstance(output.chunked_state_json, dict) else {}
        if not (
            state.get("native_learn") is True
            and state.get("preparation_generation_id") == realization.preparation_generation_id
            and state.get("teaching_plan_id") == realization.teaching_plan_id
            and int(state.get("teaching_plan_revision") or 0)
            == int(realization.teaching_plan_revision)
            and state.get("teaching_plan_hash") == realization.teaching_plan_hash
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "LEARN_OUTPUT_IDENTITY_MISMATCH",
                    "message": "The Learn output does not match its pinned realization.",
                    "recovery_action": "reprepare",
                },
            )
        return output
    output = GenerationModel(
        id=output_id,
        user_id=user_id,
        subject=subject,
        context=title or "Learn native output",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        pack_id=None,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={
            "native_learn": True,
            "learn_document": True,
            "preparation_generation_id": realization.preparation_generation_id,
            "teaching_plan_id": realization.teaching_plan_id,
            "teaching_plan_revision": realization.teaching_plan_revision,
            "teaching_plan_hash": realization.teaching_plan_hash,
            LEARN_EXECUTION_KEY: empty_learn_execution_meta(),
        },
    )
    try:
        async with session.begin_nested():
            session.add(output)
            await session.flush()
    except IntegrityError:
        output = await session.get(GenerationModel, output_id)
        if output is None or output.user_id != user_id:
            raise HTTPException(
                status_code=409,
                detail={"code": "LEARN_OUTPUT_ADMISSION_CONFLICT"},
            ) from None
        state = output.chunked_state_json if isinstance(output.chunked_state_json, dict) else {}
        if not (
            state.get("native_learn") is True
            and state.get("preparation_generation_id") == realization.preparation_generation_id
            and state.get("teaching_plan_id") == realization.teaching_plan_id
            and int(state.get("teaching_plan_revision") or 0)
            == int(realization.teaching_plan_revision)
            and state.get("teaching_plan_hash") == realization.teaching_plan_hash
        ):
            raise HTTPException(
                status_code=409,
                detail={"code": "LEARN_OUTPUT_IDENTITY_MISMATCH"},
            ) from None
    return output


def _result_for(
    realization: NativeRealizationModel,
    *,
    replayed: bool,
    editable_lesson_id: str | None = None,
    workspace_href: str | None = None,
) -> dict[str, Any]:
    identity = to_identity(realization)
    return {
        "status": identity.status,
        "path": "learn",
        "output_id": identity.output_id,
        "editable_lesson_id": editable_lesson_id,
        "realization_id": realization.id,
        "realization_revision": realization.realization_revision,
        "teaching_plan_id": realization.teaching_plan_id,
        "teaching_plan_hash": realization.teaching_plan_hash,
        "teaching_plan_revision": realization.teaching_plan_revision,
        "open_href": identity.open_href,
        "workspace_href": workspace_href,
        "error_summary": realization.error_summary,
        "replayed": replayed,
    }


async def realize_learn_from_preparation(
    session: AsyncSession,
    *,
    preparation_generation_id: str,
    user_id: str,
    path_lesson_id: str | None = None,
    admission_request_key: str | None = None,
) -> dict[str, Any]:
    """Atomically admit a durable queued Learn run and return without provider work."""
    generation = await _load_preparation_for_update(
        session, preparation_generation_id=preparation_generation_id, user_id=user_id
    )
    lesson = await _resolve_path_lesson(
        session,
        preparation_generation_id=preparation_generation_id,
        user_id=user_id,
        path_lesson_id=path_lesson_id,
    )
    unit_id = await session.scalar(
        select(UnitModel.id)
        .join(PathVersionModel, PathVersionModel.unit_id == UnitModel.id)
        .where(PathVersionModel.id == lesson.path_version_id)
    )
    workspace_href = (
        f"/units/{unit_id}/lessons/{lesson.id}/learn" if unit_id else None
    )
    state = await _load_page_state(session, generation)
    plan = _verified_plan(state)
    plan_hash = teaching_plan_content_hash(plan)
    from application.unit_lesson.realizations import admit_realization

    try:
        realization, created = await admit_realization(
            session,
            path_lesson_id=lesson.id,
            path="learn",
            teaching_plan_id=str(plan.teaching_plan_id or ""),
            teaching_plan_revision=int(plan.revision or 1),
            teaching_plan_hash=plan_hash,
            preparation_generation_id=preparation_generation_id,
            pack_id=None,
            output_id=f"learn-out-{uuid.uuid4().hex[:16]}",
            admission_request_key=admission_request_key,
            admission_payload_hash=plan_hash,
        )
    except RealizationPayloadConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "REALIZATION_PAYLOAD_CONFLICT", "message": str(exc)},
        ) from exc

    if realization.preparation_generation_id != preparation_generation_id:
        raise HTTPException(
            status_code=409,
            detail={"code": "LEARN_PREPARATION_IDENTITY_MISMATCH"},
        )
    if realization.teaching_plan_hash != plan_hash:
        raise HTTPException(
            status_code=409,
            detail={"code": "LEARN_APPROVED_HASH_MISMATCH", "recovery_action": "reprepare"},
        )
    if realization.status in {"stale", "read_only", "failed_terminal"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "LEARN_REALIZATION_NOT_ADMISSIBLE",
                "message": realization.error_summary or "This Learn run needs re-preparation.",
                "recovery_action": "reprepare",
            },
        )
    output = await _ensure_queued_output(
        session,
        realization=realization,
        user_id=user_id,
        subject=str(generation.subject or "science"),
        title=str(plan.arc or "Learn lesson"),
    )
    if realization.status == "ready":
        editable_id = await session.scalar(
            select(EditableLessonModel.id)
            .where(
                EditableLessonModel.source_generation_id == output.id,
                EditableLessonModel.user_id == user_id,
            )
            .order_by(EditableLessonModel.created_at.desc())
        )
        if not isinstance(output.document_json, dict) or not editable_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "LEARN_READY_OUTPUT_INCOMPLETE",
                    "message": "The saved Learn output is incomplete and must be re-prepared.",
                    "recovery_action": "reprepare",
                },
            )
        return _result_for(
            realization,
            replayed=True,
            editable_lesson_id=editable_id,
            workspace_href=workspace_href,
        )
    if realization.status in {"failed", "failed_recoverable"}:
        return _result_for(realization, replayed=True, workspace_href=workspace_href)
    return _result_for(
        realization, replayed=not created, workspace_href=workspace_href
    )


async def execute_learn_realization(
    session: AsyncSession,
    *,
    realization: NativeRealizationModel,
    worker_id: str,
    provider: AuthoringProvider | None = None,
) -> dict[str, Any]:
    """Run one already-admitted queued Learn realization under its output lease."""
    generation_id = str(realization.preparation_generation_id or "")
    source_before_lock = await session.get(GenerationModel, generation_id)
    if source_before_lock is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "LEARN_PREPARATION_MISSING", "recovery_action": "reprepare"},
        )
    source = await _load_preparation_for_update(
        session,
        preparation_generation_id=generation_id,
        user_id=str(source_before_lock.user_id),
    )
    await _resolve_path_lesson(
        session,
        preparation_generation_id=generation_id,
        user_id=str(source.user_id),
        path_lesson_id=realization.path_lesson_id,
    )
    claim_result = await session.execute(
        update(NativeRealizationModel)
        .where(
            NativeRealizationModel.id == realization.id,
            NativeRealizationModel.path == "learn",
            NativeRealizationModel.status == "queued",
        )
        .values(status="running")
        .execution_options(synchronize_session=False)
    )
    if claim_result.rowcount != 1:
        return {"status": "already_claimed"}
    # Keep the compare-and-set uncommitted until the output lease is installed.
    # A process crash before then rolls it back and leaves the durable row queued.
    realization_result = await session.execute(
        select(NativeRealizationModel)
        .where(NativeRealizationModel.id == realization.id)
        .execution_options(populate_existing=True)
    )
    realization = realization_result.scalar_one_or_none()
    if realization is None:
        raise HTTPException(status_code=404, detail="Learn realization not found")
    source_state = await _load_page_state(session, source)
    plan = _verified_plan(source_state, revision=int(realization.teaching_plan_revision))
    plan_hash = teaching_plan_content_hash(plan)
    if (
        plan_hash != realization.teaching_plan_hash
        or str(plan.teaching_plan_id or "") != realization.teaching_plan_id
    ):
        raise HTTPException(
            status_code=409,
            detail={"code": "LEARN_APPROVED_IDENTITY_MISMATCH", "recovery_action": "reprepare"},
        )
    output = await session.get(GenerationModel, str(realization.output_id or ""))
    if output is None or output.user_id != source.user_id:
        raise HTTPException(status_code=409, detail={"code": "LEARN_OUTPUT_OWNER_MISMATCH"})
    output_state = dict(output.chunked_state_json or {})
    pinned = (
        output_state.get("native_learn") is True
        and output_state.get("preparation_generation_id") == generation_id
        and output_state.get("teaching_plan_id") == realization.teaching_plan_id
        and int(output_state.get("teaching_plan_revision") or 0)
        == int(realization.teaching_plan_revision)
        and output_state.get("teaching_plan_hash") == realization.teaching_plan_hash
    )
    if not pinned:
        raise HTTPException(
            status_code=409,
            detail={"code": "LEARN_OUTPUT_IDENTITY_MISMATCH", "recovery_action": "reprepare"},
        )
    return await produce_learn_from_approved_teaching(
        session,
        teaching_plan=plan,
        user_id=str(source.user_id),
        path_lesson_id=realization.path_lesson_id,
        preparation_generation_id=generation_id,
        pack_id=None,
        title=str(plan.arc or "Learn lesson"),
        subject=str(source.subject or "science"),
        worker_id=worker_id,
        provider=provider,
        admitted_realization=realization,
    )


async def retry_learn_realization(
    session: AsyncSession, *, realization_id: str, user_id: str
) -> dict[str, Any]:
    """Reserve one new Learn output for an owned recoverable failure."""
    candidate = await session.get(NativeRealizationModel, realization_id)
    if candidate is None or candidate.path != "learn":
        raise HTTPException(status_code=404, detail="Learn realization not found")
    preparation_id = str(candidate.preparation_generation_id or "")
    source_before_lock = await session.get(GenerationModel, preparation_id)
    if source_before_lock is None or source_before_lock.user_id != user_id:
        raise HTTPException(status_code=404, detail="Learn realization not found")
    source = await _load_preparation_for_update(
        session,
        preparation_generation_id=preparation_id,
        user_id=user_id,
    )
    lesson = await _resolve_path_lesson(
        session,
        preparation_generation_id=preparation_id,
        user_id=user_id,
        path_lesson_id=candidate.path_lesson_id,
    )
    unit_id = await session.scalar(
        select(UnitModel.id)
        .join(PathVersionModel, PathVersionModel.unit_id == UnitModel.id)
        .where(PathVersionModel.id == lesson.path_version_id)
    )
    workspace_href = (
        f"/units/{unit_id}/lessons/{lesson.id}/learn" if unit_id else None
    )
    row_result = await session.execute(
        select(NativeRealizationModel)
        .where(
            NativeRealizationModel.id == realization_id,
            NativeRealizationModel.path == "learn",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    row = row_result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Learn realization not found")
    if lesson.id != row.path_lesson_id or row.preparation_generation_id != preparation_id:
        raise HTTPException(status_code=404, detail="Learn realization not found")
    if row.status in {"queued", "running"}:
        return _result_for(row, replayed=True, workspace_href=workspace_href)
    if row.status != "failed_recoverable":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "LEARN_RETRY_NOT_ALLOWED",
                "message": row.error_summary or "This Learn realization cannot be retried.",
                "recovery_action": "reprepare" if row.status in {"stale", "read_only"} else None,
            },
        )
    state = await _load_page_state(session, source)
    plan = _verified_plan(state, revision=int(row.teaching_plan_revision))
    plan_hash = teaching_plan_content_hash(plan)
    if plan_hash != row.teaching_plan_hash or str(plan.teaching_plan_id or "") != row.teaching_plan_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "LEARN_APPROVED_IDENTITY_MISMATCH",
                "message": "The pinned approved Teaching Plan no longer verifies.",
                "recovery_action": "reprepare",
            },
        )

    output_id = f"learn-out-{uuid.uuid4().hex[:16]}"
    try:
        reserved = await session.execute(
            update(NativeRealizationModel)
            .where(
                NativeRealizationModel.id == realization_id,
                NativeRealizationModel.path == "learn",
                NativeRealizationModel.preparation_generation_id == preparation_id,
                NativeRealizationModel.status == "failed_recoverable",
                NativeRealizationModel.output_id == row.output_id,
                NativeRealizationModel.realization_revision == row.realization_revision,
                NativeRealizationModel.teaching_plan_id == row.teaching_plan_id,
                NativeRealizationModel.teaching_plan_revision == row.teaching_plan_revision,
                NativeRealizationModel.teaching_plan_hash == row.teaching_plan_hash,
            )
            .values(
                realization_revision=NativeRealizationModel.realization_revision + 1,
                output_id=output_id,
                status="queued",
                error_summary=None,
            )
        )
    except OperationalError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "LEARN_RETRY_ALREADY_CLAIMED",
                "message": "This Learn retry was already accepted. Reload the lesson status.",
            },
        ) from exc
    if int(reserved.rowcount or 0) != 1:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "LEARN_RETRY_ALREADY_CLAIMED",
                "message": "This Learn retry was already accepted. Reload the lesson status.",
            },
        )
    row_result = await session.execute(
        select(NativeRealizationModel)
        .where(NativeRealizationModel.id == realization_id)
        .execution_options(populate_existing=True)
    )
    row = row_result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Learn realization not found")
    output = GenerationModel(
        id=output_id,
        user_id=user_id,
        subject=str(source.subject or "science"),
        context=str(plan.arc or "Learn lesson"),
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        pack_id=None,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={
            "native_learn": True,
            "learn_document": True,
            "preparation_generation_id": source.id,
            "teaching_plan_id": row.teaching_plan_id,
            "teaching_plan_revision": row.teaching_plan_revision,
            "teaching_plan_hash": row.teaching_plan_hash,
            LEARN_EXECUTION_KEY: empty_learn_execution_meta(),
        },
    )
    session.add(output)
    await session.flush()
    return _result_for(row, replayed=False, workspace_href=workspace_href)


__all__ = [
    "execute_learn_realization",
    "realize_learn_from_preparation",
    "retry_learn_realization",
]
