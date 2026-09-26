"""Owner-scoped admission of a SharedDocument Build, Run, and sourcebook item."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import UserModel
from document.shared_lesson.approved_source import (
    load_approved_item_snapshot,
    load_current_approved_teaching_plan_source,
)
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source
from document.shared_lesson.semantic_inputs import admit_sourcebook_work_item
from infra.database.models import (
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)
from infra.generation_runtime import (
    AdmissionResult,
    BuildAdmission,
    RunAdmission,
    RunAdmissionConflict,
    RunNotFound,
    RunType,
    SourceIdentity,
    admit_run,
    create_build,
)


class SharedRunAdmissionError(ValueError):
    """The owner-scoped SharedDocument admission request is invalid."""


@dataclass(frozen=True)
class SharedRunAdmissionResult:
    """Uncommitted Build/Run/sourcebook admission results."""

    run: GenerationRunModel
    sourcebook_work_item: GenerationWorkItemModel
    run_admission: AdmissionResult
    sourcebook_admission: AdmissionResult


async def _lock_owner(session: AsyncSession, owner_user_id: str) -> UserModel:
    if session.get_bind().dialect.name == "sqlite":
        # SQLite ignores FOR UPDATE.  Make this the first statement in the
        # transaction so concurrent callers do not both open read snapshots
        # before attempting to upgrade to the writer lock.
        result = await session.execute(
            update(UserModel)
            .where(UserModel.id == owner_user_id)
            .values(created_at=UserModel.created_at)
        )
        if result.rowcount != 1:
            raise RunNotFound("generation owner is unavailable")
        owner = await session.scalar(
            select(UserModel)
            .where(UserModel.id == owner_user_id)
            .execution_options(populate_existing=True)
        )
    else:
        owner = await session.scalar(
            select(UserModel)
            .where(UserModel.id == owner_user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if owner is None:
        raise RunNotFound("generation owner is unavailable")
    return owner


def _source_identity(source: TeachingPlanSource) -> SourceIdentity:
    return verify_teaching_plan_source(source)


def _run_matches(
    run: GenerationRunModel,
    *,
    build_id: str,
    owner_user_id: str,
    source: SourceIdentity,
) -> bool:
    return (
        run.build_id == build_id
        and run.owner_user_id == owner_user_id
        and run.run_type == RunType.SHARED_DOCUMENT.value
        and run.source_artifact_type == source.source_artifact_type
        and run.source_artifact_id == source.source_artifact_id
        and run.source_revision == source.source_revision
        and run.source_hash == source.source_hash
    )


async def _existing_run(
    session: AsyncSession,
    *,
    owner_user_id: str,
    path_lesson_id: str,
    request_key: str,
    source: SourceIdentity,
) -> AdmissionResult | None:
    run = await session.scalar(
        select(GenerationRunModel)
        .where(
            GenerationRunModel.owner_user_id == owner_user_id,
            GenerationRunModel.request_key == request_key,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        return None
    build = await session.scalar(
        select(GenerationBuildModel)
        .where(GenerationBuildModel.id == run.build_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if build is None or build.owner_user_id != owner_user_id:
        raise RunAdmissionConflict("request key is bound to an unavailable Build")
    if build.path_lesson_id != path_lesson_id:
        raise RunAdmissionConflict("request key is bound to a different path lesson")
    if not _run_matches(
        run,
        build_id=build.id,
        owner_user_id=owner_user_id,
        source=source,
    ):
        raise RunAdmissionConflict("request key is already bound to a different run identity")
    return AdmissionResult(run, created=False)


async def admit_shared_document_run(
    session: AsyncSession,
    *,
    owner_user_id: str,
    path_lesson_id: str,
    preparation_generation_id: str,
    request_key: str,
) -> SharedRunAdmissionResult:
    """Admit or reuse one SharedDocument Run and its sourcebook WorkItem.

    The returned rows are intentionally uncommitted.  The caller commits the
    Build, Run, and sourcebook WorkItem together, so a failure cannot leave an
    orphan Build or partially admitted Run.
    """

    if not owner_user_id.strip() or not path_lesson_id.strip():
        raise ValueError("owner_user_id and path_lesson_id must be non-empty")
    if not preparation_generation_id.strip() or not request_key.strip():
        raise ValueError("preparation_generation_id and request_key must be non-empty")

    # Keep this transaction open through the entire admission.  The owner lock
    # is acquired before reading preparation state so SQLite and PostgreSQL
    # use the same lock order for duplicate requests.
    await _lock_owner(session, owner_user_id)
    source = await load_current_approved_teaching_plan_source(
        session=session,
        owner_user_id=owner_user_id,
        path_lesson_id=path_lesson_id,
        preparation_generation_id=preparation_generation_id,
    )
    identity = _source_identity(source)
    # Verify the immutable assessment snapshot before any Build/Run mutation.
    await load_approved_item_snapshot(
        session=session,
        owner_user_id=owner_user_id,
        path_lesson_id=path_lesson_id,
        preparation_generation_id=preparation_generation_id,
        requested=identity,
    )

    existing = await _existing_run(
        session,
        owner_user_id=owner_user_id,
        path_lesson_id=path_lesson_id,
        request_key=request_key,
        source=identity,
    )
    if existing is None:
        build = await create_build(
            session,
            BuildAdmission(owner_user_id=owner_user_id, path_lesson_id=path_lesson_id),
        )
        run_admission = await admit_run(
            session,
            RunAdmission(
                build_id=build.id,
                owner_user_id=owner_user_id,
                run_type=RunType.SHARED_DOCUMENT,
                request_key=request_key,
                stage="sourcebook_generation",
                source_artifact_type=identity.source_artifact_type,
                source_artifact_id=identity.source_artifact_id,
                source_revision=identity.source_revision,
                source_hash=identity.source_hash,
            ),
        )
    else:
        run_admission = existing

    sourcebook_admission = await admit_sourcebook_work_item(
        session,
        run_id=run_admission.record.id,
        owner_user_id=owner_user_id,
        source=source,
    )
    return SharedRunAdmissionResult(
        run=run_admission.record,
        sourcebook_work_item=sourcebook_admission.record,
        run_admission=run_admission,
        sourcebook_admission=sourcebook_admission,
    )


__all__ = ["SharedRunAdmissionError", "SharedRunAdmissionResult", "admit_shared_document_run"]
