"""In-process DB-leased worker for native whole-lesson execution."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from core.database.models import GenerationModel
from core.database.session import async_session_factory
from planning.whole_lesson.failure_policy import classify_failure, structured_error_from_exc
from planning.whole_lesson.repository import PageDocumentRepository, claim_next_native_job
from planning.whole_lesson.states import (
    DEFAULT_LEASE_SECONDS,
    DEFAULT_WORKER_POLL_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    ExecutionLease,
    LeaseLostError,
)

logger = logging.getLogger(__name__)


class NativeExecutionWorker:
    def __init__(
        self,
        *,
        worker_id: str | None = None,
        poll_seconds: float = DEFAULT_WORKER_POLL_SECONDS,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        heartbeat_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self.worker_id = worker_id or f"native-{uuid.uuid4().hex[:12]}"
        self.poll_seconds = poll_seconds
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._busy = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name=f"native-worker-{self.worker_id}")
        logger.info("Native execution worker started worker_id=%s", self.worker_id)

    async def stop(self, *, drain_seconds: float = 5.0) -> None:
        self._stop.set()
        task = self._task
        if task is None:
            return
        try:
            await asyncio.wait_for(task, timeout=max(drain_seconds, 0.1))
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Native execution worker stopped worker_id=%s", self.worker_id)

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                claimed = await self._claim_one()
            except Exception:  # noqa: BLE001
                logger.exception("native worker claim failed worker_id=%s", self.worker_id)
                claimed = None
            if claimed is None:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
                except asyncio.TimeoutError:
                    pass
                continue
            self._busy = True
            try:
                await self._run_job(claimed)
            except LeaseLostError:
                logger.info(
                    "native worker lost lease generation_id=%s worker_id=%s",
                    claimed.generation_id,
                    self.worker_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "native worker job failed generation_id=%s worker_id=%s",
                    claimed.generation_id,
                    self.worker_id,
                )
            finally:
                self._busy = False

    async def _claim_one(self) -> ExecutionLease | None:
        async with async_session_factory() as session:
            return await claim_next_native_job(
                session,
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )

    async def _heartbeat_loop(self, lease: ExecutionLease) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self.heartbeat_seconds)
            try:
                async with async_session_factory() as session:
                    repo = PageDocumentRepository(session, lease.generation_id)
                    await repo.heartbeat(
                        worker_id=lease.worker_id,
                        lease_token=lease.lease_token,
                    )
            except LeaseLostError:
                logger.info(
                    "heartbeat stopped: lease lost generation_id=%s",
                    lease.generation_id,
                )
                return
            except Exception:  # noqa: BLE001
                logger.warning(
                    "native worker heartbeat failed generation_id=%s worker_id=%s",
                    lease.generation_id,
                    self.worker_id,
                    exc_info=True,
                )

    async def _run_job(self, lease: ExecutionLease) -> None:
        from planning.whole_lesson.executor import execute_after_teaching_approval

        heartbeat = asyncio.create_task(
            self._heartbeat_loop(lease),
            name=f"native-hb-{lease.generation_id[:8]}",
        )
        try:
            async with async_session_factory() as session:
                await execute_after_teaching_approval(
                    session=session,
                    generation_id=lease.generation_id,
                    worker_id=lease.worker_id,
                    lease=lease,
                )
        except LeaseLostError:
            raise
        except Exception as exc:  # noqa: BLE001
            await self._persist_failure(lease, exc)
            raise
        finally:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass

    async def _persist_failure(self, lease: ExecutionLease, exc: BaseException) -> None:
        classification = classify_failure(exc)
        if classification.code == "LEASE_LOST":
            return
        error = structured_error_from_exc(
            exc=exc,
            stage="writing_blocks",
            attempt=1,
        )
        try:
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, lease.generation_id)
                generation = await session.get(GenerationModel, lease.generation_id)
                current = str(generation.status if generation else "")
                if current in {"planning_forms", "writing_blocks", "assembling"}:
                    await repo.transition(
                        expected={current},
                        target="failed_recoverable",
                        event="worker_failure",
                        error=error,
                        worker_id=lease.worker_id,
                        lease_token=lease.lease_token,
                    )
                await repo.release_execution(
                    worker_id=lease.worker_id,
                    lease_token=lease.lease_token,
                )
        except LeaseLostError:
            return
        except Exception:  # noqa: BLE001
            logger.exception(
                "failed to persist worker failure generation_id=%s",
                lease.generation_id,
            )


_WORKER: NativeExecutionWorker | None = None


def get_native_worker() -> NativeExecutionWorker | None:
    return _WORKER


async def start_native_worker(**kwargs: Any) -> NativeExecutionWorker:
    global _WORKER
    if _WORKER is None:
        _WORKER = NativeExecutionWorker(**kwargs)
    await _WORKER.start()
    return _WORKER


async def stop_native_worker(*, drain_seconds: float = 5.0) -> None:
    global _WORKER
    if _WORKER is None:
        return
    await _WORKER.stop(drain_seconds=drain_seconds)
    _WORKER = None
