"""Durable DB-polled worker for queued Learn realizations."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realize_learn_handoff import execute_learn_realization
from core.database.models import (
    GenerationModel,
    NativeRealizationModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)
from core.database.session import async_session_factory
from infra.authoring import AuthoringProvider
from learn.generation.fencing import (
    LearnCancelledError,
    LearnFenceError,
    assert_learn_commit_allowed,
    learn_execution_from_generation,
    write_learn_execution,
)

logger = logging.getLogger(__name__)


class LearnRealizationWorker:
    def __init__(
        self,
        *,
        worker_id: str | None = None,
        poll_seconds: float = 0.5,
        provider: AuthoringProvider | None = None,
    ) -> None:
        self.worker_id = worker_id or f"learn-{uuid.uuid4().hex[:12]}"
        self.poll_seconds = poll_seconds
        self.provider = provider
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(
            self._loop(), name=f"learn-worker-{self.worker_id}"
        )
        logger.info("Learn realization worker started worker_id=%s", self.worker_id)

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

    async def run_one(self, session: AsyncSession) -> bool:
        result = await session.execute(
            select(NativeRealizationModel)
            .where(
                NativeRealizationModel.path == "learn",
                NativeRealizationModel.status == "queued",
                NativeRealizationModel.output_id.is_not(None),
            )
            .order_by(NativeRealizationModel.created_at.asc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        realization = result.scalar_one_or_none()
        if realization is None:
            return False
        realization_id = str(realization.id)
        output_id = str(realization.output_id or "")
        try:
            result = await execute_learn_realization(
                session,
                realization=realization,
                worker_id=self.worker_id,
                provider=self.provider,
            )
            # The lifespan worker owns a short-lived session for each job.
            # execute_learn_realization flushes the completed document, output,
            # editable lesson, and realization; commit before that session
            # closes or the context manager will roll the success back.
            await session.commit()
            logger.info(
                "Learn realization result committed realization_id=%s output_id=%s status=%s",
                realization_id,
                output_id,
                result.get("status"),
            )
        except LearnCancelledError:
            # Another worker already claimed the output lease, or the teacher
            # cancelled the run. Neither condition is a failed execution.
            await session.rollback()
        except HTTPException as exc:
            await self._persist_preflight_failure(
                session, realization=realization, exc=exc
            )
        except Exception as exc:
            # The producer persists its own recoverable failure. This catch
            # isolates one run so it cannot stop polling other Learn jobs.
            logger.exception(
                "Learn realization failed realization_id=%s output_id=%s",
                realization_id,
                output_id,
            )
            await session.rollback()
            refreshed = await session.get(NativeRealizationModel, realization_id)
            if refreshed is not None and refreshed.status == "queued":
                await self._persist_preflight_failure(
                    session,
                    realization=refreshed,
                    exc=HTTPException(
                        status_code=500,
                        detail={
                            "code": "LEARN_WORKER_SETUP_FAILED",
                            "message": str(exc)[:500]
                            or "Learn worker could not start this run.",
                            "recovery_action": "reprepare",
                        },
                    ),
                )
            elif refreshed is not None and refreshed.status == "running":
                await self._persist_execution_failure(
                    session,
                    realization=refreshed,
                    worker_id=self.worker_id,
                    exc=exc,
                )
        return True

    async def _persist_execution_failure(
        self,
        session: AsyncSession,
        *,
        realization: NativeRealizationModel,
        worker_id: str,
        exc: Exception,
    ) -> None:
        """Park an escaped post-admission failure while this worker still owns its lease."""
        detail_message = str(exc).strip()[:500] or "Learn output finalization failed."
        result = await session.execute(
            select(NativeRealizationModel)
            .where(
                NativeRealizationModel.id == realization.id,
                NativeRealizationModel.path == "learn",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        if row is None or row.status != "running" or row.output_id != realization.output_id:
            return

        output_result = await session.execute(
            select(GenerationModel)
            .where(GenerationModel.id == str(row.output_id or ""))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        output = output_result.scalar_one_or_none()
        source = await session.get(
            GenerationModel, str(row.preparation_generation_id or "")
        )
        owner_id = await session.scalar(
            select(UnitModel.owner_id)
            .select_from(PathLessonModel)
            .join(PathVersionModel, PathVersionModel.id == PathLessonModel.path_version_id)
            .join(UnitModel, UnitModel.id == PathVersionModel.unit_id)
            .where(PathLessonModel.id == row.path_lesson_id)
        )
        output_state = (
            output.chunked_state_json
            if output is not None and isinstance(output.chunked_state_json, dict)
            else {}
        )
        pinned_output = bool(
            output is not None
            and source is not None
            and output.status == "running"
            and owner_id == source.user_id == output.user_id
            and output_state.get("native_learn") is True
            and output_state.get("preparation_generation_id")
            == row.preparation_generation_id
            and output_state.get("teaching_plan_id") == row.teaching_plan_id
            and int(output_state.get("teaching_plan_revision") or 0)
            == int(row.teaching_plan_revision)
            and output_state.get("teaching_plan_hash") == row.teaching_plan_hash
        )
        if not pinned_output or output is None:
            row.status = "failed_terminal"
            row.error_summary = (
                "Learn execution failed and its output ownership or pinned identity "
                "could not be verified. Reprepare before creating another output."
            )
            await session.commit()
            logger.error(
                "Learn escaped failure parked terminal realization_id=%s output_id=%s",
                row.id,
                row.output_id,
            )
            return

        execution = learn_execution_from_generation(output)
        lease_token = int(execution.get("lease_token") or 0)
        try:
            assert_learn_commit_allowed(
                execution,
                worker_id=worker_id,
                lease_token=lease_token,
            )
        except (LearnFenceError, LearnCancelledError) as fence_error:
            # A stale worker must not write failure or ready state. Startup
            # reconciliation owns expired leases; another worker owns a newer
            # token if this lease was replaced.
            logger.warning(
                "Learn escaped failure not persisted after lease loss realization_id=%s output_id=%s reason=%s",
                row.id,
                row.output_id,
                str(fence_error)[:200],
            )
            return

        detail = {
            "code": "LEARN_EXECUTION_FINALIZATION_FAILED",
            "error_type": type(exc).__name__,
            "failure_class": "learn_finalization",
            "message": detail_message,
            "retryable": True,
            "stage": "finalization",
            "work_item_id": None,
            "attempt": int(row.realization_revision or 1),
            "recovery_action": "retry",
        }
        execution.update(
            {"status": "failed", "worker_id": None, "heartbeat_at": None}
        )
        write_learn_execution(output, execution)
        output_state = dict(output.chunked_state_json or {})
        output_state["error_detail"] = detail
        output.chunked_state_json = output_state
        output.status = "failed"
        output.error = detail_message
        output.error_code = detail["code"]
        output.error_type = type(exc).__name__
        row.status = "failed_recoverable"
        row.error_summary = detail_message
        await session.commit()
        logger.error(
            "Learn finalization failure parked recoverable realization_id=%s output_id=%s",
            row.id,
            row.output_id,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

    async def _persist_preflight_failure(
        self,
        session: AsyncSession,
        *,
        realization: NativeRealizationModel,
        exc: HTTPException,
    ) -> None:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = str(detail.get("code") or "LEARN_RUN_INTEGRITY_FAILURE")
        message = str(detail.get("message") or exc.detail or "Learn run identity is invalid.")
        realization.status = "failed_terminal"
        realization.error_summary = message[:500]
        output = await session.get(GenerationModel, str(realization.output_id or ""))
        source = await session.get(
            GenerationModel, str(realization.preparation_generation_id or "")
        )
        owner_id = await session.scalar(
            select(UnitModel.owner_id)
            .select_from(PathLessonModel)
            .join(PathVersionModel, PathVersionModel.id == PathLessonModel.path_version_id)
            .join(UnitModel, UnitModel.id == PathVersionModel.unit_id)
            .where(PathLessonModel.id == realization.path_lesson_id)
        )
        output_state = (
            output.chunked_state_json
            if output is not None and isinstance(output.chunked_state_json, dict)
            else {}
        )
        output_is_owned_and_pinned = bool(
            output is not None
            and source is not None
            and owner_id == source.user_id == output.user_id
            and output_state.get("native_learn") is True
            and output_state.get("preparation_generation_id")
            == realization.preparation_generation_id
            and output_state.get("teaching_plan_id") == realization.teaching_plan_id
            and int(output_state.get("teaching_plan_revision") or 0)
            == int(realization.teaching_plan_revision)
            and output_state.get("teaching_plan_hash") == realization.teaching_plan_hash
        )
        if output_is_owned_and_pinned and output is not None:
            state = dict(output.chunked_state_json or {})
            state["error_detail"] = {
                "code": code,
                "error_type": "learn_run_integrity",
                "failure_class": "state_integrity",
                "message": message[:500],
                "retryable": False,
                "stage": "admission",
                "work_item_id": None,
                "attempt": int(realization.realization_revision or 1),
                "recovery_action": detail.get("recovery_action") or "reprepare",
            }
            output.chunked_state_json = state
            output.status = "failed"
        elif output is None or output_is_owned_and_pinned is False:
            realization.error_summary = (
                f"{message[:350]} Output ownership or pinned identity could not be verified."
            )
        await session.commit()

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                async with async_session_factory() as session:
                    claimed = await self.run_one(session)
            except Exception:
                logger.exception("Learn worker poll failed worker_id=%s", self.worker_id)
                claimed = False
            if not claimed:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
                except TimeoutError:
                    pass


_WORKER: LearnRealizationWorker | None = None


def get_learn_worker() -> LearnRealizationWorker | None:
    return _WORKER


async def start_learn_worker(**kwargs: Any) -> LearnRealizationWorker:
    global _WORKER
    if _WORKER is None:
        _WORKER = LearnRealizationWorker(**kwargs)
    await _WORKER.start()
    return _WORKER


async def stop_learn_worker(*, drain_seconds: float = 5.0) -> None:
    global _WORKER
    if _WORKER is None:
        return
    await _WORKER.stop(drain_seconds=drain_seconds)
    _WORKER = None


__all__ = [
    "LearnRealizationWorker",
    "get_learn_worker",
    "start_learn_worker",
    "stop_learn_worker",
]
