from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from core.database.models import GenerationModel
from core.database.session import async_session_factory
from core.events import event_bus
from telemetry.repositories.sql_llm_call_repo import SqlLLMCallRepository

logger = logging.getLogger(__name__)


@dataclass
class _TraceRegistration:
    user_id: str
    source: str


class _TraceRegistry:
    def __init__(self) -> None:
        self._items: dict[str, _TraceRegistration] = {}

    def register(self, trace_id: str, user_id: str, source: str) -> None:
        self._items[trace_id] = _TraceRegistration(user_id=user_id, source=source)

    def close(self, trace_id: str) -> None:
        self._items.pop(trace_id, None)

    def user_id_for(self, trace_id: str) -> str | None:
        candidate = trace_id
        while candidate:
            registration = self._items.get(candidate)
            if registration is not None:
                return registration.user_id
            candidate, separator, _child = candidate.rpartition(":")
            if not separator:
                break
        return None


class TelemetryMonitor:
    def __init__(self) -> None:
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None
        self._registry = _TraceRegistry()
        self._default_llm_calls = SqlLLMCallRepository(async_session_factory)
        self._llm_call_repository_factory: Any | None = None

    def configure(self, *, llm_call_repository_factory=None) -> None:
        self._llm_call_repository_factory = llm_call_repository_factory

    async def start(self) -> None:
        if self._task is not None:
            return
        self._queue = event_bus.subscribe_all()
        self._task = asyncio.create_task(self._run(), name="telemetry-monitor")

    async def stop(self) -> None:
        if self._task is None:
            return
        if self._queue is not None:
            try:
                await asyncio.wait_for(self._queue.join(), timeout=5.0)
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning("Telemetry monitor shutdown timed out while draining events")
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            if self._queue is not None:
                event_bus.unsubscribe_all(self._queue)
            self._queue = None
            self._task = None

    async def _run(self) -> None:
        assert self._queue is not None
        while True:
            payload = await self._queue.get()
            try:
                await self._handle_event(dict(payload))
            except Exception:
                logger.exception("Telemetry monitor failed while processing event=%s", payload)
            finally:
                self._queue.task_done()

    async def _handle_event(self, payload: dict) -> None:
        event_type = payload.get("type")
        trace_id = payload.get("trace_id") or payload.get("generation_id")
        generation_id = payload.get("generation_id")

        if event_type == "trace_registered":
            self._registry.register(payload["trace_id"], payload["user_id"], payload["source"])
            return
        if event_type == "trace_closed":
            self._registry.close(payload["trace_id"])
            return

        if event_type in {"llm_call_succeeded", "llm_call_failed"} and trace_id:
            user_id = self._registry.user_id_for(trace_id)
            if user_id is None and generation_id:
                user_id = await self._user_id_for_generation(generation_id)
            if user_id is None:
                logger.warning(
                    "Skipping llm_call persistence without user_id trace_id=%s generation_id=%s event_type=%s",
                    trace_id,
                    generation_id,
                    event_type,
                )
                return
            try:
                llm_calls = await self._get_llm_call_repository()
                await llm_calls.save_call(
                    trace_id=trace_id,
                    generation_id=generation_id,
                    user_id=user_id,
                    caller=payload.get("caller") or "unknown",
                    slot=payload.get("slot", "unknown"),
                    family=payload.get("family"),
                    model_name=payload.get("model_name"),
                    endpoint_host=payload.get("endpoint_host"),
                    attempt=payload.get("attempt", 1),
                    section_id=payload.get("section_id"),
                    status="succeeded" if event_type == "llm_call_succeeded" else "failed",
                    retryable=payload.get("retryable"),
                    latency_ms=payload.get("latency_ms"),
                    tokens_in=payload.get("tokens_in"),
                    tokens_out=payload.get("tokens_out"),
                    thinking_tokens=payload.get("thinking_tokens"),
                    cost_usd=payload.get("cost_usd"),
                    error=(
                        f"[{payload['error_class']}] {payload.get('error') or ''}".rstrip()
                        if payload.get("error_class")
                        else payload.get("error")
                    ),
                    node=payload.get("node"),
                )
            except Exception:
                logger.exception(
                    "Telemetry monitor failed to persist llm_call trace_id=%s generation_id=%s",
                    trace_id,
                    generation_id,
                )

    async def initialise_v3_recorder(
        self,
        *,
        generation_id: str,
        user_id: str,
        blueprint_title: str,
        subject: str,
        template_id: str,
    ) -> None:
        _ = (blueprint_title, subject, template_id)
        self._registry.register(generation_id, user_id, "v3")

    async def _user_id_for_generation(self, generation_id: str) -> str | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(GenerationModel.user_id).where(GenerationModel.id == generation_id)
            )
            row = result.first()
            return row[0] if row is not None else None

    async def _get_llm_call_repository(self):
        if self._llm_call_repository_factory is not None:
            repository = await self._llm_call_repository_factory()
            if repository is not None:
                return repository
        return self._default_llm_calls


telemetry_monitor = TelemetryMonitor()
