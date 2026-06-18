from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
import uuid
from typing import Any

import core.events as core_events
from langchain_core.runnables.config import RunnableConfig
from core.config import Settings
from pipeline.events import PipelineEvent, RuntimePolicyEvent, RuntimeProgressEvent
from core.llm import RetryPolicy
from pipeline.runtime_policy import (
    RuntimePolicyBundle,
    TimeoutPolicy,
    resolve_runtime_policy_bundle,
)
from pipeline.runtime_progress import RuntimeProgressSnapshot, RuntimeProgressTracker
from pipeline.types.requests import PipelineRequest


@dataclass
class PipelineLimiters:
    section: asyncio.Semaphore
    media: asyncio.Semaphore
    qc: asyncio.Semaphore


@dataclass
class PipelineRuntimeContext:
    id: str
    generation_id: str
    request: PipelineRequest
    policy: RuntimePolicyBundle
    generation_timeout_seconds: float
    limiters: PipelineLimiters
    progress: RuntimeProgressTracker
    emit_event_callback: Any = None

    async def emit_event(self, event: PipelineEvent) -> None:
        if self.emit_event_callback is None:
            return
        maybe_awaitable = self.emit_event_callback(event)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable


_CONTEXTS_BY_ID: dict[str, PipelineRuntimeContext] = {}
_CONTEXT_IDS_BY_GENERATION: dict[str, str] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _publish_runtime_progress(
    generation_id: str,
    snapshot: RuntimeProgressSnapshot,
) -> None:
    core_events.event_bus.publish(
        generation_id,
        RuntimeProgressEvent(
            generation_id=generation_id,
            snapshot=snapshot,
        ),
    )


def build_runtime_context(
    *,
    request: PipelineRequest,
    settings: Settings,
    emit_event_callback: Any = None,
) -> PipelineRuntimeContext:
    policy = resolve_runtime_policy_bundle(settings, request.mode)
    generation_id = request.generation_id or ""
    context_id = str(uuid.uuid4())
    progress = RuntimeProgressTracker(
        mode=request.mode,
        sections_total=request.section_count,
        emit_snapshot=lambda snapshot: _publish_runtime_progress(generation_id, snapshot),
    )
    context = PipelineRuntimeContext(
        id=context_id,
        generation_id=generation_id,
        request=request,
        policy=policy,
        generation_timeout_seconds=policy.generation_timeout_seconds(request.section_count),
        limiters=PipelineLimiters(
            section=asyncio.Semaphore(policy.concurrency.max_section_concurrency),
            media=asyncio.Semaphore(policy.concurrency.max_media_concurrency),
            qc=asyncio.Semaphore(policy.concurrency.max_qc_concurrency),
        ),
        progress=progress,
        emit_event_callback=emit_event_callback,
    )
    return context


def register_runtime_context(context: PipelineRuntimeContext) -> None:
    _CONTEXTS_BY_ID[context.id] = context
    if context.generation_id:
        _CONTEXT_IDS_BY_GENERATION[context.generation_id] = context.id


def unregister_runtime_context(context_id: str) -> None:
    context = _CONTEXTS_BY_ID.pop(context_id, None)
    if context is None:
        return
    if context.generation_id:
        current = _CONTEXT_IDS_BY_GENERATION.get(context.generation_id)
        if current == context_id:
            del _CONTEXT_IDS_BY_GENERATION[context.generation_id]


def runtime_config_for_context(context: PipelineRuntimeContext) -> dict[str, Any]:
    return {"runtime_context_id": context.id}


def get_runtime_context(config: RunnableConfig | None) -> PipelineRuntimeContext | None:
    if config is None:
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    context_id = configurable.get("runtime_context_id")
    if not isinstance(context_id, str):
        return None
    return _CONTEXTS_BY_ID.get(context_id)


def get_runtime_context_by_generation(generation_id: str) -> PipelineRuntimeContext | None:
    context_id = _CONTEXT_IDS_BY_GENERATION.get(generation_id)
    if context_id is None:
        return None
    return _CONTEXTS_BY_ID.get(context_id)


def retry_policy_for_node(
    config: RunnableConfig | None,
    node: str,
) -> RetryPolicy | None:
    context = get_runtime_context(config)
    if context is None:
        return None
    return context.policy.retries.for_node(node)


def timeout_policy_from_config(config: RunnableConfig | None) -> TimeoutPolicy | None:
    context = get_runtime_context(config)
    if context is None:
        return None
    return context.policy.timeouts


def build_runtime_policy_event(context: PipelineRuntimeContext) -> RuntimePolicyEvent:
    return RuntimePolicyEvent(
        generation_id=context.generation_id,
        mode=context.request.mode,
        generation_timeout_seconds=context.generation_timeout_seconds,
        max_section_rerenders=context.policy.max_section_rerenders,
        generation_max_concurrent_per_user=context.policy.generation_max_concurrent_per_user,
        concurrency={
            "max_section_concurrency": context.policy.concurrency.max_section_concurrency,
            "max_media_concurrency": context.policy.concurrency.max_media_concurrency,
            "max_qc_concurrency": context.policy.concurrency.max_qc_concurrency,
        },
        timeouts={
            "curriculum_planner_timeout_seconds": context.policy.timeouts.curriculum_planner_timeout_seconds,
            "content_core_timeout_seconds": context.policy.timeouts.content_core_timeout_seconds,
            "content_practice_timeout_seconds": context.policy.timeouts.content_practice_timeout_seconds,
            "content_enrichment_timeout_seconds": context.policy.timeouts.content_enrichment_timeout_seconds,
            "content_repair_timeout_seconds": context.policy.timeouts.content_repair_timeout_seconds,
            "field_regenerator_timeout_seconds": context.policy.timeouts.field_regenerator_timeout_seconds,
            "qc_timeout_seconds": context.policy.timeouts.qc_timeout_seconds,
            "media_inner_timeout_seconds": context.policy.timeouts.diagram_inner_timeout_seconds,
            "media_node_budget_seconds": context.policy.timeouts.diagram_node_budget_seconds,
            "generation_timeout_base_seconds": context.policy.timeouts.generation_timeout_base_seconds,
            "generation_timeout_per_section_seconds": context.policy.timeouts.generation_timeout_per_section_seconds,
            "generation_timeout_cap_seconds": context.policy.timeouts.generation_timeout_cap_seconds,
        },
        retries=context.policy.retries.to_public_dict(),
        emitted_at=_now_iso(),
    )
