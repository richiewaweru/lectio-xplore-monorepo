from __future__ import annotations

import asyncio
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import logging
import random
import time
from typing import Any, Mapping

from pydantic import ValidationError
from pydantic_ai.exceptions import ModelHTTPError, UserError

import core.events as core_events
from core.llm.cost import compute_cost_usd, extract_thinking_tokens, extract_usage
from core.llm.transport import effective_text_spec, endpoint_host
from core.llm.types import ModelFamily, ModelSlot, ModelSpec

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    call_timeout_seconds: float = 120.0
    max_rate_limit_delay_seconds: float = 8.0


def _should_publish_events(trace_id: str) -> bool:
    return bool(trace_id and trace_id.strip())


def _publish_llm_event(trace_id: str, event: Any) -> None:
    if _should_publish_events(trace_id):
        core_events.event_bus.publish(trace_id, event)


def _coerce_retry_after_seconds(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(stripped)
            except (TypeError, ValueError, IndexError):
                return None
            return max(parsed.timestamp() - time.time(), 0.0)
    return None


def _retry_after_seconds(exc: ModelHTTPError) -> float | None:
    header_candidates = []

    headers = getattr(exc, "headers", None)
    if isinstance(headers, Mapping):
        header_candidates.append(headers)

    if isinstance(exc.body, Mapping):
        header_candidates.append(exc.body)
        nested_headers = exc.body.get("headers")
        if isinstance(nested_headers, Mapping):
            header_candidates.append(nested_headers)
        nested_error = exc.body.get("error")
        if isinstance(nested_error, Mapping):
            header_candidates.append(nested_error)

    for candidate in header_candidates:
        for key in ("retry-after", "Retry-After", "retry_after", "retryAfter"):
            seconds = _coerce_retry_after_seconds(candidate.get(key))
            if seconds is not None:
                return seconds

    return None


def _retry_delay_seconds(
    *,
    exc: BaseException,
    attempt: int,
    retry_policy: RetryPolicy,
) -> float:
    if isinstance(exc, ModelHTTPError) and exc.status_code == 429:
        retry_after = _retry_after_seconds(exc)
        if retry_after is not None:
            base_delay = min(retry_after, retry_policy.max_rate_limit_delay_seconds)
        else:
            base_delay = min(
                2.0 * (2 ** max(attempt - 1, 0)),
                retry_policy.max_rate_limit_delay_seconds,
            )
        jitter = random.uniform(0.0, min(base_delay * 0.25, 0.5))
        return base_delay + jitter
    return retry_policy.base_delay_seconds * attempt


async def _run_agent_with_limits(
    *,
    agent: Any,
    user_prompt: str,
    retry_policy: RetryPolicy,
    model_settings: dict | None = None,
) -> Any:
    run_kwargs: dict[str, Any] = {"user_prompt": user_prompt}
    if model_settings:
        run_kwargs["model_settings"] = model_settings

    return await asyncio.wait_for(
        agent.run(**run_kwargs),
        timeout=retry_policy.call_timeout_seconds,
    )


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (UserError, ValidationError)):
        return False
    if isinstance(exc, ModelHTTPError):
        return exc.status_code in {408, 429, 500, 502, 503, 504}
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    try:
        import httpx

        return isinstance(
            exc,
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
            ),
        )
    except ImportError:
        return False


async def run_llm(
    *,
    caller: str,
    trace_id: str,
    generation_id: str | None = None,
    agent: Any,
    user_prompt: str,
    model: Any | None = None,
    slot: ModelSlot | None = None,
    section_id: str | None = None,
    retry_policy: RetryPolicy | None = None,
    spec: ModelSpec | None = None,
    model_settings: dict | None = None,
    node: str | None = None,
) -> Any:
    retry_policy = retry_policy or RetryPolicy()
    slot = slot or ModelSlot.FAST
    generation_id = generation_id or trace_id
    event_node = node if node is not None else caller

    catalog_spec = spec or ModelSpec(family=ModelFamily.TEST, model_name="unknown")
    effective_spec = effective_text_spec(catalog_spec=catalog_spec, model=model)
    effective_endpoint_host = (
        endpoint_host(effective_spec.base_url)
        if effective_spec.family == ModelFamily.OPENAI_COMPATIBLE
        else None
    )

    effective_settings: dict | None = None
    if effective_spec.family == ModelFamily.ANTHROPIC:
        effective_settings = dict(model_settings or {})
        effective_settings.setdefault("anthropic_cache_instructions", True)
        effective_settings.setdefault("anthropic_cache_tool_definitions", True)
    elif model_settings:
        effective_settings = model_settings

    publish = _should_publish_events(trace_id)
    if not publish:
        logger.debug(
            "run_llm skipping event_bus (empty trace_id)",
            extra={
                "caller": caller,
                "slot": slot.value,
                "trace_id": trace_id,
            },
        )

    attempt = 0
    while attempt < retry_policy.max_attempts:
        attempt += 1
        started_at = time.perf_counter()

        _publish_llm_event(
            trace_id,
            core_events.LLMCallStartedEvent(
                trace_id=trace_id,
                generation_id=generation_id,
                caller=caller,
                node=event_node,
                slot=slot.value,
                family=effective_spec.family.value,
                model_name=effective_spec.model_name,
                endpoint_host=effective_endpoint_host,
                attempt=attempt,
                section_id=section_id,
            ),
        )

        try:
            result = await _run_agent_with_limits(
                agent=agent,
                user_prompt=user_prompt,
                retry_policy=retry_policy,
                model_settings=effective_settings,
            )
            latency_ms = (time.perf_counter() - started_at) * 1000.0

            usage = extract_usage(result)
            thinking_tokens = extract_thinking_tokens(result)
            cost_usd = compute_cost_usd(
                effective_spec,
                usage.tokens_in,
                usage.tokens_out,
            )

            _publish_llm_event(
                trace_id,
                core_events.LLMCallSucceededEvent(
                    trace_id=trace_id,
                    generation_id=generation_id,
                    caller=caller,
                    node=event_node,
                    slot=slot.value,
                    family=effective_spec.family.value,
                    model_name=effective_spec.model_name,
                    endpoint_host=effective_endpoint_host,
                    attempt=attempt,
                    section_id=section_id,
                    latency_ms=latency_ms,
                    tokens_in=usage.tokens_in,
                    tokens_out=usage.tokens_out,
                    prompt_cache_hit_tokens=usage.prompt_cache_hit_tokens,
                    prompt_cache_miss_tokens=usage.prompt_cache_miss_tokens,
                    thinking_tokens=thinking_tokens,
                    cost_usd=cost_usd,
                ),
            )
            return result
        except ValidationError as exc:
            latency_ms = (time.perf_counter() - started_at) * 1000.0
            _publish_llm_event(
                trace_id,
                core_events.LLMCallFailedEvent(
                    trace_id=trace_id,
                    generation_id=generation_id,
                    caller=caller,
                    node=event_node,
                    slot=slot.value,
                    family=effective_spec.family.value,
                    model_name=effective_spec.model_name,
                    endpoint_host=effective_endpoint_host,
                    attempt=attempt,
                    section_id=section_id,
                    latency_ms=latency_ms,
                    retryable=False,
                    error=str(exc),
                ),
            )
            raise
        except Exception as exc:
            latency_ms = (time.perf_counter() - started_at) * 1000.0
            can_retry = _is_retryable(exc) and attempt < retry_policy.max_attempts
            _publish_llm_event(
                trace_id,
                core_events.LLMCallFailedEvent(
                    trace_id=trace_id,
                    generation_id=generation_id,
                    caller=caller,
                    node=event_node,
                    slot=slot.value,
                    family=effective_spec.family.value,
                    model_name=effective_spec.model_name,
                    endpoint_host=effective_endpoint_host,
                    attempt=attempt,
                    section_id=section_id,
                    latency_ms=latency_ms,
                    retryable=can_retry,
                    error=str(exc),
                ),
            )
            if not can_retry:
                raise
            await asyncio.sleep(
                _retry_delay_seconds(
                    exc=exc,
                    attempt=attempt,
                    retry_policy=retry_policy,
                )
            )

    raise RuntimeError("run_llm exhausted retries unexpectedly")
