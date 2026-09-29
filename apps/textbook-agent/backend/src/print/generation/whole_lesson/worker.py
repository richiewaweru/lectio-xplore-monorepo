"""In-process DB-leased worker for preparation pre-worker retries.

Option D (4A): Print output realization runs on the shared-runtime
RealizationWorker.  This minimal worker remains only because
``native_retry.py`` (preparation pre-worker retry) claims through
``claim_next_native_job`` until preparation moves onto Runs (package 3A).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from core.database.session import async_session_factory
from print.generation.whole_lesson.repository import PageDocumentRepository, claim_next_native_job
from print.generation.whole_lesson.states import (
    DEFAULT_LEASE_SECONDS,
    DEFAULT_WORKER_POLL_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    PRE_WORKER_WORK_KINDS,
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
        except TimeoutError:
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
            except Exception:
                logger.exception("native worker claim failed worker_id=%s", self.worker_id)
                claimed = None
            if claimed is None:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
                except TimeoutError:
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
            except Exception:
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
            except Exception:
                logger.warning(
                    "native worker heartbeat failed generation_id=%s worker_id=%s",
                    lease.generation_id,
                    self.worker_id,
                    exc_info=True,
                )
    async def _run_job(self, lease: ExecutionLease) -> None:
        from print.generation.whole_lesson.native_retry import run_pre_worker_retry
        from print.generation.whole_lesson.repository import empty_execution_meta

        heartbeat = asyncio.create_task(
            self._heartbeat_loop(lease),
            name=f"native-hb-{lease.generation_id[:8]}",
        )
        try:
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, lease.generation_id)
                state = await repo.load_page_generation_state()
                work_kind = (state.get("execution") or empty_execution_meta()).get(
                    "work_kind"
                )
                if work_kind not in PRE_WORKER_WORK_KINDS:
                    # Option D (4A): Print output execution moved to the
                    # shared-runtime RealizationWorker. Only preparation
                    # pre-worker retries are claimed here (until package 3A).
                    logger.warning(
                        "native worker released non-pre-worker job generation_id=%s",
                        lease.generation_id,
                    )
                    await repo.release_execution(
                        worker_id=lease.worker_id, lease_token=lease.lease_token
                    )
                    return
            try:
                await run_pre_worker_retry(lease=lease)
            except LeaseLostError:
                raise
            except Exception:
                # Failure already persisted inside run_pre_worker_retry.
                logger.exception(
                    "pre-worker retry failed generation_id=%s worker_id=%s",
                    lease.generation_id,
                    self.worker_id,
                )
        finally:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass


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
