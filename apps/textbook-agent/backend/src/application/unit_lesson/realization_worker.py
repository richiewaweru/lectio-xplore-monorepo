"""Shared-runtime worker for Learn/Print realization Runs (Option D, item 4A).

A realization (``native_realizations``) is a product record: the teacher asked
for a Learn or Print output pinned to an approved Teaching Plan.  This worker
turns that request into a generation Run on the shared runtime:

* **dispatch** - a bounded scan of realizations that have no Run yet.  While
  the SharedLessonDocument Run is not READY the worker only *projects* status
  (never takes a lease, never busy-loops).  Once READY it admits a ``learn`` /
  ``print`` Run on the document Run's build, sourced from the document Run's
  exact output identity, plus one ``{path}:realize`` work item.
* **execute** - claims that item on the runtime lease and calls the existing
  deterministic adapters (which no longer own any lease or state machine),
  then completes the item, finalizes the Run with a source verifier and an
  artifact loader, and projects ``native_realizations.status``.
* **failure** - typed ``WorkItemFailure`` through ``fail_work_item``.

Realization status is written from run state in exactly one place:
``application.unit_lesson.realization_projection.project_realization_status``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from application.unit_lesson.realization_projection import project_realization_status
from core.database.models import (
    NativeRealizationModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)
from document.shared_lesson.realization_source import (
    RealizationSourceError,
    RealizationSourceResult,
    StaleRealizationSource,
    load_realization_source,
)
from infra.database.models import (
    GenerationModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)
from infra.execution.checkpoints import content_hash
from infra.execution.leases import LeaseLostError
from infra.generation_runtime import (
    ErrorClass,
    RecoveryAction,
    RunAdmission,
    RunAdmissionConflict,
    RunFinalization,
    RunType,
    SourceIdentity,
    VerifiedArtifact,
    WorkItemAdmission,
    WorkItemConflict,
    WorkItemFailure,
    add_work_item,
    admit_run,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    finalize_run,
)
from infra.generation_runtime.repository import (
    ArtifactVerificationError,
    InvalidRunTransition,
    WorkItemNotFound,
    WorkItemUnavailable,
)

LOGGER = logging.getLogger(__name__)

REALIZATION_STAGE = "realization"
REALIZE_ITEM_STAGE = "realize"
REALIZATION_DEFINITION_VERSION = "realization-v1"
OUTPUT_ARTIFACT_TYPES = {"learn": "learn_output", "print": "print_output"}
_PATHS = ("learn", "print")
_ITEM_KEYS = {f"{path}:realize": path for path in _PATHS}
_DEFAULT_SCAN_LIMIT = 20

_TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (
    sqlalchemy_exc.OperationalError,
    sqlalchemy_exc.InterfaceError,
    TimeoutError,
    ConnectionError,
)


class _SourceConflict(RuntimeError):
    """The document or realization no longer matches the admitted Run source."""


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is not None:
        return current.astimezone(UTC).replace(tzinfo=None)
    return current


def realization_request_key(*, path: str, realization_id: str, realization_revision: int) -> str:
    return f"{path}-realization:{realization_id}:{int(realization_revision)}"


def _run_source(run: GenerationRunModel) -> SourceIdentity:
    return SourceIdentity(
        source_artifact_type=run.source_artifact_type,
        source_artifact_id=run.source_artifact_id,
        source_revision=run.source_revision,
        source_hash=run.source_hash,
    )


def _doc_run_identity(doc_run: GenerationRunModel) -> SourceIdentity:
    if (
        doc_run.output_artifact_type != "shared_lesson_document"
        or not doc_run.output_artifact_id
        or doc_run.output_revision is None
        or not doc_run.output_hash
    ):
        raise _SourceConflict("the SharedLessonDocument Run has no complete output identity")
    return SourceIdentity(
        source_artifact_type=str(doc_run.output_artifact_type),
        source_artifact_id=str(doc_run.output_artifact_id),
        source_revision=int(doc_run.output_revision),
        source_hash=str(doc_run.output_hash),
    )


def classify_failure(exc: BaseException) -> WorkItemFailure:
    """Closed, safe failure classification for one realize attempt."""
    if isinstance(exc, _TRANSIENT_ERRORS):
        return WorkItemFailure(
            error_code="realization_transient_error",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="A temporary storage error interrupted this output. Retry it.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, _SourceConflict):
        return WorkItemFailure(
            error_code="realization_source_conflict",
            error_class=ErrorClass.SOURCE_CONFLICT,
            safe_summary="The lesson document changed while this output was being created.",
            recovery_action=RecoveryAction.REGENERATE,
        )
    # Adapter contract / validation errors are deterministic: retrying the same
    # immutable input cannot succeed, so they are terminal (regenerate).
    name = type(exc).__name__
    if isinstance(exc, RealizationSourceError) or "Mapping" in name or "Assembly" in name or (
        name in {"ValidationError", "ValueError", "PublishValidationError"}
    ):
        return WorkItemFailure(
            error_code="realization_contract_violation",
            error_class=ErrorClass.VALIDATION,
            safe_summary=(
                "The lesson document could not be converted into this output: "
                f"{str(exc).strip()[:300] or name}"
            ),
            recovery_action=RecoveryAction.REGENERATE,
        )
    return WorkItemFailure(
        error_code="realization_internal_error",
        error_class=ErrorClass.INTERNAL_PROGRAMMING,
        safe_summary="An unexpected error stopped this output. Regenerate it.",
        recovery_action=RecoveryAction.REGENERATE,
    )


class RealizationWorker:
    """Poll dispatch + execute for Learn/Print realization Runs.

    ``session_factory`` is injected exactly like ``SharedDocumentWorker``.
    """

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        worker_id: str | None = None,
        lease_seconds: int = 120,
        poll_interval_seconds: float = 0.5,
        scan_limit: int = _DEFAULT_SCAN_LIMIT,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if scan_limit <= 0:
            raise ValueError("scan_limit must be positive")
        self.session_factory = session_factory
        self.worker_id = worker_id or f"realization-{uuid.uuid4()}"
        self.lease_seconds = lease_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.scan_limit = scan_limit
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name=self.worker_id)

    async def stop(self, *, drain_seconds: float = 5.0) -> None:
        self._stop.set()
        task = self._task
        if task is None:
            return
        try:
            await asyncio.wait_for(task, timeout=max(drain_seconds, 0.1))
        except TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            progressed = False
            try:
                async with self.session_factory() as session:
                    progressed = await self.run_one(session)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Realization worker iteration failed")
            if progressed:
                continue
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_seconds)
            except TimeoutError:
                pass

    async def run_one(self, session: Any, *, now: datetime | None = None) -> bool:
        """One tick: dispatch/project, reproject open Runs, execute one item.

        Returns True only when something advanced, so an idle or waiting
        realization never spins the loop.
        """
        current = _now(now)
        progressed = await self._dispatch(session, current)
        progressed = await self._reproject_open_runs(session) or progressed
        progressed = await self._execute_one(session, current) or progressed
        return progressed

    # ------------------------------------------------------------------ dispatch

    async def _dispatch(self, session: Any, now: datetime) -> bool:
        ids = list(
            (
                await session.scalars(
                    select(NativeRealizationModel.id)
                    .where(
                        NativeRealizationModel.generation_run_id.is_(None),
                        NativeRealizationModel.path.in_(_PATHS),
                        or_(
                            NativeRealizationModel.status.in_(("queued", "needs_shared_review")),
                            # Failed on retryable shared-document leaves: keep
                            # following the Run so an auto/manual retry flips
                            # the realization back to queued.
                            and_(
                                NativeRealizationModel.status == "failed_recoverable",
                                NativeRealizationModel.shared_document_state == "recoverable",
                            ),
                        ),
                        NativeRealizationModel.output_id.is_not(None),
                    )
                    .order_by(NativeRealizationModel.created_at.asc())
                    .limit(self.scan_limit)
                )
            ).all()
        )
        progressed = False
        for realization_id in ids:
            try:
                progressed = await self._dispatch_one(session, str(realization_id)) or progressed
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Realization dispatch failed realization_id=%s", realization_id)
                await session.rollback()
        return progressed

    async def _owner_id(self, session: Any, path_lesson_id: str) -> str | None:
        return await session.scalar(
            select(UnitModel.owner_id)
            .select_from(PathLessonModel)
            .join(PathVersionModel, PathVersionModel.id == PathLessonModel.path_version_id)
            .join(UnitModel, UnitModel.id == PathVersionModel.unit_id)
            .where(PathLessonModel.id == path_lesson_id)
        )

    async def _dispatch_one(self, session: Any, realization_id: str) -> bool:
        row = await session.get(NativeRealizationModel, realization_id, populate_existing=True)
        if (
            row is None
            or row.generation_run_id
            or not (
                row.status in {"queued", "needs_shared_review"}
                or (
                    row.status == "failed_recoverable"
                    and row.shared_document_state == "recoverable"
                )
            )
        ):
            return False
        owner_id = await self._owner_id(session, str(row.path_lesson_id))
        if owner_id is None:
            return False
        before = (row.status, row.error_summary, row.shared_document_state)
        try:
            result = await load_realization_source(
                session, owner_user_id=owner_id, path_lesson_id=str(row.path_lesson_id)
            )
        except RealizationSourceError as exc:
            LOGGER.warning("Realization source unavailable realization_id=%s: %s", row.id, exc)
            await session.rollback()
            return False

        if result.state != "ready":
            project_realization_status(row, doc_source=result)
            changed = (row.status, row.error_summary, row.shared_document_state) != before
            await session.commit()
            return changed

        ready = result.ready
        assert ready is not None
        if (
            ready.plan_id != row.teaching_plan_id
            or int(ready.plan_revision) != int(row.teaching_plan_revision)
            or ready.plan_hash != row.teaching_plan_hash
        ):
            self._project_stale(
                row,
                run_id=ready.run_id,
                reason="the lesson document was built from a different approved plan",
            )
            await session.commit()
            return True

        doc_run = await session.get(GenerationRunModel, ready.run_id, populate_existing=True)
        try:
            identity = _doc_run_identity(doc_run) if doc_run is not None else None
            if identity is None:
                raise _SourceConflict("the SharedLessonDocument Run is unavailable")
            path = str(row.path)
            admission = await admit_run(
                session,
                RunAdmission(
                    build_id=doc_run.build_id,
                    owner_user_id=owner_id,
                    run_type=RunType(path),
                    request_key=realization_request_key(
                        path=path,
                        realization_id=str(row.id),
                        realization_revision=int(row.realization_revision),
                    ),
                    stage=REALIZATION_STAGE,
                    source_artifact_type=identity.source_artifact_type,
                    source_artifact_id=identity.source_artifact_id,
                    source_revision=identity.source_revision,
                    source_hash=identity.source_hash,
                ),
            )
            run = admission.record
            assert isinstance(run, GenerationRunModel)
            await add_work_item(
                session,
                WorkItemAdmission(
                    run_id=run.id,
                    item_key=f"{path}:realize",
                    stage=REALIZE_ITEM_STAGE,
                    input_hash=content_hash(
                        {
                            "path": path,
                            "source": identity.model_dump(mode="json"),
                            "realization_id": str(row.id),
                            "realization_revision": int(row.realization_revision),
                        }
                    ),
                    definition_hash=content_hash(
                        {"definition": f"{path}-realization", "version": REALIZATION_DEFINITION_VERSION}
                    ),
                ),
            )
        except (_SourceConflict, RunAdmissionConflict, WorkItemConflict, InvalidRunTransition) as exc:
            await session.rollback()
            row = await session.get(NativeRealizationModel, realization_id, populate_existing=True)
            if row is None:
                return False
            self._project_stale(row, run_id=ready.run_id, reason=str(exc)[:300])
            await session.commit()
            return True

        row.generation_run_id = run.id
        row.shared_document_run_id = ready.run_id
        loaded = await self._load_run(session, run.id)
        project_realization_status(row, run=loaded)
        row.shared_document_state = "ready"
        await session.commit()
        return True

    @staticmethod
    def _project_stale(row: NativeRealizationModel, *, run_id: str, reason: str) -> None:
        project_realization_status(
            row,
            doc_source=RealizationSourceResult(
                state="stale", stale=StaleRealizationSource(run_id=run_id, reason=reason)
            ),
        )

    async def _load_run(self, session: Any, run_id: str) -> GenerationRunModel | None:
        return await session.scalar(
            select(GenerationRunModel)
            .options(selectinload(GenerationRunModel.work_items))
            .where(GenerationRunModel.id == run_id)
            .execution_options(populate_existing=True)
        )

    async def _reproject_open_runs(self, session: Any) -> bool:
        """Follow Run state (incl. HTTP retries) for realizations that have a Run."""
        rows = list(
            (
                await session.scalars(
                    select(NativeRealizationModel)
                    .join(
                        GenerationRunModel,
                        GenerationRunModel.id == NativeRealizationModel.generation_run_id,
                    )
                    .where(
                        NativeRealizationModel.status.in_(
                            ("queued", "running", "failed_recoverable")
                        ),
                        # Only rows whose projection is out of sync, so parked
                        # failures can never starve the bounded scan.
                        NativeRealizationModel.status != GenerationRunModel.status,
                    )
                    .order_by(NativeRealizationModel.updated_at.asc())
                    .limit(self.scan_limit)
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        changed = False
        for row in rows:
            run = await self._load_run(session, str(row.generation_run_id))
            if run is None:
                continue
            before = (row.status, row.error_summary)
            project_realization_status(row, run=run)
            changed = changed or (row.status, row.error_summary) != before
        await session.commit()
        return changed

    # ------------------------------------------------------------------- execute

    async def _execute_one(self, session: Any, now: datetime) -> bool:
        candidates = list(
            (
                await session.execute(
                    select(GenerationWorkItemModel.id, GenerationRunModel.id)
                    .join(GenerationRunModel, GenerationRunModel.id == GenerationWorkItemModel.run_id)
                    .where(
                        GenerationRunModel.run_type.in_(_PATHS),
                        GenerationRunModel.status.in_(("queued", "running")),
                        GenerationWorkItemModel.item_key.in_(tuple(_ITEM_KEYS)),
                        or_(
                            GenerationWorkItemModel.status == "queued",
                            (
                                (GenerationWorkItemModel.status == "running")
                                & (GenerationWorkItemModel.lease_expires_at <= now)
                            ),
                        ),
                    )
                    .order_by(GenerationWorkItemModel.created_at.asc())
                    .limit(self.scan_limit)
                )
            ).all()
        )
        for item_id, run_id in candidates:
            run = await session.get(GenerationRunModel, run_id, populate_existing=True)
            if run is None:
                continue
            try:
                item = await claim_work_item(
                    session,
                    work_item_id=str(item_id),
                    worker_id=self.worker_id,
                    source=_run_source(run),
                    lease_seconds=self.lease_seconds,
                    now=now,
                )
                await session.commit()
            except (WorkItemUnavailable, WorkItemNotFound):
                await session.rollback()
                continue
            except sqlalchemy_exc.OperationalError:
                await session.rollback()
                continue
            if item.status != "running":
                # An expired, attempt-exhausted item was reconciled by the claim.
                await self._project_run(session, str(run_id))
                return True
            await self._execute_claimed(
                session,
                item_id=str(item.id),
                lease_token=int(item.lease_token or 0),
                run_id=str(run_id),
                now=now,
            )
            return True
        return False

    async def _project_run(self, session: Any, run_id: str) -> None:
        run = await self._load_run(session, run_id)
        row = await session.scalar(
            select(NativeRealizationModel)
            .where(NativeRealizationModel.generation_run_id == run_id)
            .execution_options(populate_existing=True)
        )
        if run is not None and row is not None:
            project_realization_status(row, run=run)
        await session.commit()

    async def _execute_claimed(
        self,
        session: Any,
        *,
        item_id: str,
        lease_token: int,
        run_id: str,
        now: datetime,
    ) -> None:
        try:
            await self._materialize_and_finalize(
                session, item_id=item_id, lease_token=lease_token, run_id=run_id, now=now
            )
        except LeaseLostError:
            await session.rollback()
            LOGGER.info("Realization lease lost work_item_id=%s", item_id)
        except asyncio.CancelledError:
            await session.rollback()
            raise
        except Exception as exc:
            await session.rollback()
            LOGGER.warning(
                "Realization work item failed work_item_id=%s error=%s: %s",
                item_id,
                type(exc).__name__,
                str(exc)[:500],
                exc_info=not isinstance(exc, _TRANSIENT_ERRORS),
            )
            await self._record_failure(
                session,
                item_id=item_id,
                lease_token=lease_token,
                run_id=run_id,
                exc=exc,
                now=now,
            )

    async def _record_failure(
        self,
        session: Any,
        *,
        item_id: str,
        lease_token: int,
        run_id: str,
        exc: BaseException,
        now: datetime,
    ) -> None:
        try:
            await fail_work_item(
                session,
                work_item_id=item_id,
                worker_id=self.worker_id,
                lease_token=lease_token,
                failure=classify_failure(exc),
                now=now,
            )
            await session.commit()
        except LeaseLostError:
            await session.rollback()
            return
        except Exception:
            LOGGER.exception("Could not persist realization failure work_item_id=%s", item_id)
            await session.rollback()
            return
        await self._project_run(session, run_id)

    async def _materialize_and_finalize(
        self,
        session: Any,
        *,
        item_id: str,
        lease_token: int,
        run_id: str,
        now: datetime,
    ) -> None:
        run = await session.get(GenerationRunModel, run_id, populate_existing=True)
        if run is None:
            raise _SourceConflict("the realization Run is unavailable")
        owner_id = str(run.owner_user_id)
        path = str(run.run_type)
        source = _run_source(run)

        realization = await session.scalar(
            select(NativeRealizationModel)
            .where(NativeRealizationModel.generation_run_id == run_id)
            .execution_options(populate_existing=True)
        )
        if realization is None or realization.status in {"stale", "read_only"}:
            raise _SourceConflict("the realization no longer owns this Run")
        if realization_request_key(
            path=path,
            realization_id=str(realization.id),
            realization_revision=int(realization.realization_revision),
        ) != run.request_key:
            raise _SourceConflict("the realization moved to a newer revision")

        # Re-verify under the lease: the document must still be the READY one
        # this Run was admitted on.
        result = await load_realization_source(
            session, owner_user_id=owner_id, path_lesson_id=str(realization.path_lesson_id)
        )
        if result.state != "ready" or result.ready is None:
            raise _SourceConflict("the lesson document is no longer ready")
        ready = result.ready
        doc_run = await session.get(GenerationRunModel, ready.run_id, populate_existing=True)
        if doc_run is None or _doc_run_identity(doc_run) != source:
            raise _SourceConflict("the lesson document identity changed")
        if (
            ready.plan_id != realization.teaching_plan_id
            or int(ready.plan_revision) != int(realization.teaching_plan_revision)
            or ready.plan_hash != realization.teaching_plan_hash
        ):
            raise _SourceConflict("the approved plan identity changed")

        output_id = str(realization.output_id or "")
        subject = await self._subject(session, realization)
        if path == "learn":
            from learn.generation.shared_document_execution import (
                materialize_learn_output_from_shared_document,
            )

            await materialize_learn_output_from_shared_document(
                session,
                realization=realization,
                ready=ready,
                owner_user_id=owner_id,
                subject=subject,
            )
        else:
            from print.generation.shared_document_execution import (
                materialize_print_output_from_shared_document,
            )

            await materialize_print_output_from_shared_document(
                session, realization=realization, ready=ready
            )

        output = await session.get(GenerationModel, output_id, populate_existing=True)
        if output is None or not isinstance(output.document_json, dict):
            raise _SourceConflict("the realized output was not written")
        output_hash = content_hash(output.document_json)
        item_output = {"output_id": output_id, "document_hash": output_hash}
        await complete_work_item(
            session,
            work_item_id=item_id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            output_json=item_output,
            output_hash=content_hash(item_output),
            now=now,
        )

        realization_revision = int(realization.realization_revision)
        artifact_type = OUTPUT_ARTIFACT_TYPES[path]
        lesson_id = str(realization.path_lesson_id)

        async def source_verifier(
            verify_session: Any, requested: SourceIdentity
        ) -> SourceIdentity:
            current = await load_realization_source(
                verify_session, owner_user_id=owner_id, path_lesson_id=lesson_id
            )
            if current.state != "ready" or current.ready is None:
                raise _SourceConflict("the lesson document is no longer ready")
            current_doc_run = await verify_session.get(
                GenerationRunModel, current.ready.run_id, populate_existing=True
            )
            if current_doc_run is None:
                raise _SourceConflict("the SharedLessonDocument Run is unavailable")
            return _doc_run_identity(current_doc_run)

        async def artifact_loader(
            load_session: Any, artifact_type_: str, artifact_id: str, revision: int
        ) -> VerifiedArtifact:
            if artifact_type_ != artifact_type:
                raise ArtifactVerificationError("unexpected realization artifact type")
            owned = await load_session.scalar(
                select(NativeRealizationModel.id).where(
                    NativeRealizationModel.output_id == artifact_id,
                    NativeRealizationModel.realization_revision == revision,
                    NativeRealizationModel.generation_run_id == run_id,
                )
            )
            generation = await load_session.get(GenerationModel, artifact_id, populate_existing=True)
            if owned is None or generation is None or not isinstance(generation.document_json, dict):
                raise ArtifactVerificationError("realization output row is unavailable")
            return VerifiedArtifact(
                artifact_type=artifact_type_,
                artifact_id=artifact_id,
                revision=revision,
                output_json=generation.document_json,
                output_hash=content_hash(generation.document_json),
            )

        finalized = await finalize_run(
            session,
            run_id=run_id,
            owner_user_id=owner_id,
            finalization=RunFinalization(
                source=source,
                output_artifact_type=artifact_type,
                output_artifact_id=output_id,
                output_revision=realization_revision,
            ),
            source_verifier=source_verifier,
            artifact_loader=artifact_loader,
            now=now,
        )
        loaded = await self._load_run(session, str(finalized.id))
        project_realization_status(realization, run=loaded)
        await session.commit()

    async def _subject(self, session: Any, realization: NativeRealizationModel) -> str:
        source = await session.get(GenerationModel, str(realization.preparation_generation_id or ""))
        return str(getattr(source, "subject", None) or "science")


__all__ = [
    "OUTPUT_ARTIFACT_TYPES",
    "REALIZATION_STAGE",
    "RealizationWorker",
    "classify_failure",
    "realization_request_key",
]
