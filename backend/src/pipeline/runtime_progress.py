from __future__ import annotations

import asyncio
from collections.abc import Callable

from pydantic import BaseModel

from pipeline.types.requests import GenerationMode

RuntimeResource = str


class RuntimeProgressSnapshot(BaseModel):
    mode: GenerationMode
    sections_total: int
    sections_completed: int = 0
    sections_running: int = 0
    sections_queued: int = 0
    media_running: int = 0
    media_queued: int = 0
    qc_running: int = 0
    qc_queued: int = 0
    retry_running: int = 0
    retry_queued: int = 0


class RuntimeProgressTracker:
    def __init__(
        self,
        *,
        mode: GenerationMode,
        sections_total: int,
        emit_snapshot: Callable[[RuntimeProgressSnapshot], None],
    ) -> None:
        self._mode = mode
        self._sections_total = max(sections_total, 0)
        self._emit_snapshot = emit_snapshot
        self._lock = asyncio.Lock()

        self._completed_sections: set[str] = set()
        self._sections_running: set[str] = set()
        self._sections_queued: set[str] = set()
        self._media_running: set[str] = set()
        self._media_queued: set[str] = set()
        self._qc_running: set[str] = set()
        self._qc_queued: set[str] = set()
        self._retry_running: set[str] = set()
        self._retry_queued: set[str] = set()
        self._last_emitted_snapshot: RuntimeProgressSnapshot | None = None

    async def queue_section(self, section_id: str) -> None:
        async with self._lock:
            if section_id not in self._sections_running:
                self._sections_queued.add(section_id)
            self._emit_locked()

    async def start_section(self, section_id: str) -> None:
        async with self._lock:
            self._sections_queued.discard(section_id)
            self._sections_running.add(section_id)
            self._emit_locked()

    async def finish_section(self, section_id: str) -> None:
        async with self._lock:
            self._sections_running.discard(section_id)
            self._sections_queued.discard(section_id)
            self._emit_locked()

    async def queue_node(self, resource: RuntimeResource, section_id: str) -> None:
        async with self._lock:
            self._queued_set_for(resource).add(section_id)
            self._emit_locked()

    async def start_node(self, resource: RuntimeResource, section_id: str) -> None:
        async with self._lock:
            self._queued_set_for(resource).discard(section_id)
            self._running_set_for(resource).add(section_id)
            self._emit_locked()

    async def finish_node(self, resource: RuntimeResource, section_id: str) -> None:
        async with self._lock:
            self._running_set_for(resource).discard(section_id)
            self._queued_set_for(resource).discard(section_id)
            self._emit_locked()

    async def queue_retry(self, section_id: str) -> None:
        async with self._lock:
            if section_id not in self._retry_running:
                self._retry_queued.add(section_id)
            self._emit_locked()

    async def start_retry(self, section_id: str) -> None:
        async with self._lock:
            self._retry_queued.discard(section_id)
            self._retry_running.add(section_id)
            self._emit_locked()

    async def finish_retry(self, section_id: str) -> None:
        async with self._lock:
            self._retry_running.discard(section_id)
            self._retry_queued.discard(section_id)
            self._emit_locked()

    async def mark_section_ready(self, section_id: str) -> None:
        async with self._lock:
            self._completed_sections.add(section_id)
            self._emit_locked()

    async def snapshot(self) -> RuntimeProgressSnapshot:
        async with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> RuntimeProgressSnapshot:
        return RuntimeProgressSnapshot(
            mode=self._mode,
            sections_total=self._sections_total,
            sections_completed=len(self._completed_sections),
            sections_running=len(self._sections_running),
            sections_queued=len(self._sections_queued),
            media_running=len(self._media_running),
            media_queued=len(self._media_queued),
            qc_running=len(self._qc_running),
            qc_queued=len(self._qc_queued),
            retry_running=len(self._retry_running),
            retry_queued=len(self._retry_queued),
        )

    def _emit_locked(self) -> None:
        snapshot = self._snapshot_locked()
        if self._last_emitted_snapshot is not None and (
            snapshot.model_dump(mode="json")
            == self._last_emitted_snapshot.model_dump(mode="json")
        ):
            return
        self._emit_snapshot(snapshot)
        self._last_emitted_snapshot = snapshot

    def _queued_set_for(self, resource: RuntimeResource) -> set[str]:
        if resource == "media":
            return self._media_queued
        if resource == "qc":
            return self._qc_queued
        raise ValueError(f"Unsupported queued resource: {resource}")

    def _running_set_for(self, resource: RuntimeResource) -> set[str]:
        if resource == "media":
            return self._media_running
        if resource == "qc":
            return self._qc_running
        raise ValueError(f"Unsupported running resource: {resource}")
