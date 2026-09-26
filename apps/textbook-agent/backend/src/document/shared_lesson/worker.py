"""Restart-safe dispatcher for the first SharedDocument semantic stages.

This worker deliberately owns only orchestration.  Durable claims, checkpoints,
fences, bounded provider repair, and failure classification remain in the
sourcebook and shared-task runtimes.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from core.database.models import PathLessonModel
from document.shared_lesson.approved_source import (
    ApprovedSourceVerificationError,
    load_approved_item_snapshot,
    load_current_approved_teaching_plan_source,
    make_approved_source_verifier,
)
from document.shared_lesson.runtime import TeachingPlanSource
from document.shared_lesson.semantic_inputs import (
    SOURCEBOOK_ITEM_KEY,
    TASK_ITEM_KEY,
    SemanticInputError,
    admit_shared_task_work_item,
    load_verified_sourcebook_input,
)
from document.shared_lesson.sourcebook_runtime import (
    SourcebookWorkItemJob,
    execute_sourcebook_work_item,
)
from document.shared_lesson.task_runtime import (
    SharedTaskWorkItemJob,
    execute_shared_task_work_item,
)
from infra.authoring import AuthoringEngine, AuthoringProvider
from infra.database.models import (
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)
from infra.execution.leases import LeaseLostError
from infra.generation_runtime import (
    ErrorClass,
    InvalidRunTransition,
    RecoveryAction,
    RunFailure,
    RunNotFound,
    SourceIdentity,
    WorkItemFailure,
    WorkItemUnavailable,
    active_work_items,
    claim_work_item,
    fail_run_terminal,
    fail_work_item,
)

LOGGER = logging.getLogger(__name__)


class SharedDocumentWorkerError(RuntimeError):
    """The worker cannot reconstruct the admitted source context."""


@dataclass(frozen=True)
class _Candidate:
    run: GenerationRunModel
    item: GenerationWorkItemModel | None
    path_lesson_id: str
    preparation_generation_id: str
    admit_tasks: bool = False


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is not None:
        return current.astimezone(UTC).replace(tzinfo=None)
    return current


def _expired(item: GenerationWorkItemModel, now: datetime) -> bool:
    expiry = item.lease_expires_at
    if expiry is None:
        return False
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)
    return expiry <= now


def _eligible(item: GenerationWorkItemModel, now: datetime) -> bool:
    return item.status == "queued" or (item.status == "running" and _expired(item, now))


def _source_identity(run: GenerationRunModel) -> SourceIdentity:
    return SourceIdentity(
        source_artifact_type=run.source_artifact_type,
        source_artifact_id=run.source_artifact_id,
        source_revision=run.source_revision,
        source_hash=run.source_hash,
    )


class SharedDocumentWorker:
    """Poll and advance one active SharedDocument Run at a time.

    ``session_factory`` is injected so the application can use its normal
    async session maker and tests can provide an isolated database.  Every
    provider call is made by an existing stage executor after it commits its
    claim and checkpoint.
    """

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        worker_id: str | None = None,
        provider: AuthoringProvider | None = None,
        engine: AuthoringEngine | None = None,
        lease_seconds: int = 300,
        poll_interval_seconds: float = 0.25,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        self.session_factory = session_factory
        self.worker_id = worker_id or f"shared-document-{uuid.uuid4()}"
        self.provider = provider
        self.engine = engine
        self.lease_seconds = lease_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name=self.worker_id)

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        if task is not None:
            await task
        self._task = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                async with self.session_factory() as session:
                    await self.run_one(session)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("SharedDocument worker iteration failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_seconds)
            except TimeoutError:
                pass

    async def run_one(
        self,
        session: Any,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Advance one WorkItem or admit the dependent task WorkItem."""
        current = _now(now)
        candidate = await self._find_candidate(session, current)
        if candidate is None:
            return False

        try:
            source, verifier, snapshot_loader = await self._source_context(session, candidate)
        except (ApprovedSourceVerificationError, SharedDocumentWorkerError) as exc:
            if candidate.item is None:
                await self._fail_admission_run(
                    session,
                    candidate,
                    error_code="shared_document_source_conflict",
                    error_class=ErrorClass.SOURCE_CONFLICT,
                    safe_summary=(
                        "The approved Teaching Plan source is unavailable or no longer valid."
                    ),
                    now=current,
                )
                LOGGER.warning(
                    "SharedDocument Run %s failed before task admission: %s",
                    candidate.run.id,
                    exc,
                )
                return True
            await self._fail_source_context(session, candidate, current)
            return True

        if candidate.admit_tasks:
            try:
                verified = await load_verified_sourcebook_input(
                    session,
                    run_id=candidate.run.id,
                    owner_user_id=candidate.run.owner_user_id,
                    source=source,
                )
                await admit_shared_task_work_item(
                    session,
                    run_id=candidate.run.id,
                    owner_user_id=candidate.run.owner_user_id,
                    source=source,
                    sourcebook_output_hash=verified.sourcebook_output_hash,
                )
            except SemanticInputError as exc:
                await self._fail_admission_run(
                    session,
                    candidate,
                    error_code="shared_document_dependency_contract",
                    error_class=ErrorClass.UNSUPPORTED_CONTRACT,
                    safe_summary=(
                        "The approved dependency snapshot or ready sourcebook no longer "
                        "matches the SharedDocument contract."
                    ),
                    now=current,
                )
                LOGGER.warning(
                    "SharedDocument Run %s failed while admitting task work: %s",
                    candidate.run.id,
                    exc,
                )
                return True
            candidate.run.stage = "shared_task_generation"
            await session.commit()
            return True

        if candidate.item is None:
            return False
        status = "queued"
        if candidate.item.item_key == SOURCEBOOK_ITEM_KEY:
            await execute_sourcebook_work_item(
                SourcebookWorkItemJob(
                    session=session,
                    work_item_id=candidate.item.id,
                    worker_id=self.worker_id,
                    source=source,
                    provider=self.provider,
                    engine=self.engine,
                    source_verifier=verifier,
                    owner_user_id=candidate.run.owner_user_id,
                    status=status,
                    lease_seconds=self.lease_seconds,
                ),
                source_verifier=verifier,
                now=current,
            )
        elif candidate.item.item_key == TASK_ITEM_KEY:
            await execute_shared_task_work_item(
                SharedTaskWorkItemJob(
                    session=session,
                    work_item_id=candidate.item.id,
                    worker_id=self.worker_id,
                    source=source,
                    owner_user_id=candidate.run.owner_user_id,
                    approved_item_snapshot_loader=snapshot_loader,
                    provider=self.provider,
                    engine=self.engine,
                    source_verifier=verifier,
                    status=status,
                    lease_seconds=self.lease_seconds,
                ),
                source_verifier=verifier,
                now=current,
            )
        else:
            return False
        await session.commit()
        return True

    async def _find_candidate(self, session: Any, now: datetime) -> _Candidate | None:
        runs = list(
            (
                await session.scalars(
                    select(GenerationRunModel)
                    .where(
                        GenerationRunModel.run_type == "shared_document",
                        GenerationRunModel.status.in_({"queued", "running"}),
                    )
                    .order_by(GenerationRunModel.created_at, GenerationRunModel.id)
                )
            ).all()
        )
        for run in runs:
            items = list(
                (
                    await session.scalars(
                        select(GenerationWorkItemModel)
                        .where(GenerationWorkItemModel.run_id == run.id)
                        .order_by(GenerationWorkItemModel.created_at, GenerationWorkItemModel.id)
                    )
                ).all()
            )
            active = active_work_items(items)
            sourcebook = next((i for i in active if i.item_key == SOURCEBOOK_ITEM_KEY), None)
            task = next((i for i in active if i.item_key == TASK_ITEM_KEY), None)
            build = await session.scalar(
                select(GenerationBuildModel).where(GenerationBuildModel.id == run.build_id)
            )
            path_lesson_id = build.path_lesson_id if build is not None else ""
            preparation_generation_id = ""
            if path_lesson_id:
                lesson = await session.get(PathLessonModel, path_lesson_id)
                preparation_generation_id = (
                    lesson.pack_id if lesson is not None and lesson.pack_id else ""
                )

            if sourcebook is not None and _eligible(sourcebook, now):
                return _Candidate(
                    run=run,
                    item=sourcebook,
                    path_lesson_id=path_lesson_id,
                    preparation_generation_id=preparation_generation_id,
                )
            if sourcebook is not None and sourcebook.status == "ready":
                has_active_item = any(item.status in {"queued", "running"} for item in active)
                if task is None and not has_active_item:
                    return _Candidate(
                        run=run,
                        item=None,
                        path_lesson_id=path_lesson_id,
                        preparation_generation_id=preparation_generation_id,
                        admit_tasks=True,
                    )
                if _eligible(task, now):
                    return _Candidate(
                        run=run,
                        item=task,
                        path_lesson_id=path_lesson_id,
                        preparation_generation_id=preparation_generation_id,
                    )
        return None

    async def _fail_admission_run(
        self,
        session: Any,
        candidate: _Candidate,
        *,
        error_code: str,
        error_class: ErrorClass,
        safe_summary: str,
        now: datetime,
    ) -> None:
        try:
            await fail_run_terminal(
                session,
                run_id=candidate.run.id,
                owner_user_id=candidate.run.owner_user_id,
                failure=RunFailure(
                    error_code=error_code,
                    error_class=error_class,
                    safe_summary=safe_summary,
                ),
                now=now,
            )
        except (InvalidRunTransition, RunNotFound):
            # A concurrent worker or user action already moved the Run.
            await session.rollback()
            return
        await session.commit()

    async def _source_context(
        self,
        session: Any,
        candidate: _Candidate,
    ) -> tuple[TeachingPlanSource, Any, Callable[..., Any]]:
        if not candidate.path_lesson_id or not candidate.preparation_generation_id:
            raise SharedDocumentWorkerError("Build/PathLesson source context is unavailable")
        source = await load_current_approved_teaching_plan_source(
            session=session,
            owner_user_id=candidate.run.owner_user_id,
            path_lesson_id=candidate.path_lesson_id,
            preparation_generation_id=candidate.preparation_generation_id,
        )
        verifier = make_approved_source_verifier(
            owner_user_id=candidate.run.owner_user_id,
            path_lesson_id=candidate.path_lesson_id,
            preparation_generation_id=candidate.preparation_generation_id,
        )

        async def snapshot_loader(
            snapshot_session: Any,
            owner_user_id: str,
            requested_source: TeachingPlanSource,
            requested_identity: SourceIdentity,
        ) -> Any:
            return await load_approved_item_snapshot(
                session=snapshot_session,
                owner_user_id=owner_user_id,
                path_lesson_id=candidate.path_lesson_id,
                preparation_generation_id=candidate.preparation_generation_id,
                requested=requested_identity,
            )

        return source, verifier, snapshot_loader

    async def _fail_source_context(
        self,
        session: Any,
        candidate: _Candidate,
        now: datetime,
    ) -> None:
        if candidate.item is None:
            return
        try:
            claimed = await claim_work_item(
                session,
                work_item_id=candidate.item.id,
                worker_id=self.worker_id,
                source=_source_identity(candidate.run),
                lease_seconds=self.lease_seconds,
                now=now,
            )
            await fail_work_item(
                session,
                work_item_id=claimed.id,
                worker_id=self.worker_id,
                lease_token=claimed.lease_token or 0,
                failure=WorkItemFailure(
                    error_code="shared_document_source_conflict",
                    error_class=ErrorClass.SOURCE_CONFLICT,
                    safe_summary="The persisted approved Teaching Plan source is unavailable or stale.",
                    recovery_action=RecoveryAction.NONE,
                ),
                now=now,
            )
            await session.commit()
        except (LeaseLostError, WorkItemUnavailable):
            await session.rollback()


__all__ = ["SharedDocumentWorker", "SharedDocumentWorkerError"]
