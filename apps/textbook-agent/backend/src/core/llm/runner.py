from __future__ import annotations

import asyncio
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import logging
import random
import time
from typing import Any, Mapping

from pydantic import ValidationError
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UserError

import core.events as core_events
from core.llm.cost import compute_cost_usd, extract_thinking_tokens, extract_usage
from core.llm.transport import effective_text_spec, endpoint_host
from core.llm.types import ModelFamily, ModelSlot, ModelSpec

logger = logging.getLogger(__name__)


class TruncatedCompletionError(RuntimeError):
    def __init__(self, *, node: str | None, finish_reason: str | None, detail: str) -> None:
        self.node = node
        self.finish_reason = finish_reason
        self.detail = detail
        message = detail
        if finish_reason:
            message = f"{detail} (finish_reason={finish_reason})"
        if node:
            message = f"{node}: {message}"
        super().__init__(message)


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
    try:
        import httpx

        network_error = isinstance(
            exc,
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.WriteError,
                httpx.RemoteProtocolError,
            ),
        )
    except ImportError:
        network_error = False
    if network_error:
        base_delay = retry_policy.base_delay_seconds * (2 ** max(attempt - 1, 0))
        return base_delay + random.uniform(0.0, min(base_delay * 0.25, 0.5))
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


def _extract_finish_reason(result: Any) -> str | None:
    direct = getattr(result, "finish_reason", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    candidates = [
        getattr(result, "response", None),
        getattr(result, "raw_response", None),
        getattr(result, "_raw_response", None),
        getattr(result, "model_response", None),
    ]
    for candidate in candidates:
        finish_reason = _extract_finish_reason_from_candidate(candidate)
        if finish_reason:
            return finish_reason
    return None


def _extract_finish_reason_from_candidate(candidate: Any) -> str | None:
    if candidate is None:
        return None
    if isinstance(candidate, Mapping):
        direct = candidate.get("finish_reason") or candidate.get("finishReason")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        return _extract_finish_reason_from_choices(candidate.get("choices"))

    direct = getattr(candidate, "finish_reason", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    return _extract_finish_reason_from_choices(getattr(candidate, "choices", None))


def _extract_finish_reason_from_choices(choices: Any) -> str | None:
    if not isinstance(choices, list) or not choices:
        return None
    choice = choices[0]
    if isinstance(choice, Mapping):
        direct = choice.get("finish_reason") or choice.get("finishReason")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        message = choice.get("message")
        if isinstance(message, Mapping):
            nested = message.get("finish_reason") or message.get("finishReason")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
        return None

    direct = getattr(choice, "finish_reason", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    message = getattr(choice, "message", None)
    nested = getattr(message, "finish_reason", None)
    if isinstance(nested, str) and nested.strip():
        return nested.strip()
    return None


def _is_empty_output(result: Any) -> bool:
    output = getattr(result, "output", None)
    if output is None:
        return True
    if isinstance(output, str):
        return not output.strip()
    if isinstance(output, (list, tuple, dict, set)):
        return len(output) == 0
    return False


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, UserError):
        return False
    if isinstance(exc, ModelHTTPError):
        return exc.status_code in {408, 429} or exc.status_code >= 500
    # ModelHTTPError is a ModelAPIError subclass, so the status-sensitive
    # branch must stay above this provider connection-error classification.
    if isinstance(exc, ModelAPIError):
        return True
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
                httpx.WriteError,
                httpx.RemoteProtocolError,
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
    attempt_start: int = 1,
    repair_attempts: int = 0,
) -> Any:
    retry_policy = retry_policy or RetryPolicy()
    slot = slot or ModelSlot.FAST
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

    if attempt_start < 1:
        raise ValueError("attempt_start must be at least 1")

    current_prompt = user_prompt
    remaining_repairs = max(0, repair_attempts)
    repair_in_progress = False
    local_attempt = 0
    while local_attempt < retry_policy.max_attempts or remaining_repairs > 0:
        local_attempt += 1
        event_attempt = attempt_start + local_attempt - 1
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
                attempt=event_attempt,
                section_id=section_id,
            ),
        )

        try:
            result = await _run_agent_with_limits(
                agent=agent,
                user_prompt=current_prompt,
                retry_policy=retry_policy,
                model_settings=effective_settings,
            )
            latency_ms = (time.perf_counter() - started_at) * 1000.0

            finish_reason = _extract_finish_reason(result)
            if finish_reason == "length":
                raise TruncatedCompletionError(
                    node=event_node,
                    finish_reason=finish_reason,
                    detail="Model completion was truncated before a complete response was produced",
                )
            if _is_empty_output(result):
                raise TruncatedCompletionError(
                    node=event_node,
                    finish_reason=finish_reason,
                    detail="Model completion returned empty output",
                )

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
                    attempt=event_attempt,
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
            if repair_in_progress:
                _publish_llm_event(
                    trace_id,
                    {
                        "type": "repair_succeeded",
                        "trace_id": trace_id,
                        "generation_id": generation_id,
                        "node": event_node,
                        "attempt": event_attempt,
                        "section_id": section_id,
                    },
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
                    attempt=event_attempt,
                    section_id=section_id,
                    latency_ms=latency_ms,
                    retryable=remaining_repairs > 0,
                    error=str(exc),
                    error_class=type(exc).__name__,
                ),
            )
            if remaining_repairs > 0:
                remaining_repairs -= 1
                repair_in_progress = True
                current_prompt = (
                    f"{user_prompt}\n\n"
                    "Your previous response failed schema validation with these errors:\n"
                    f"{exc}\n\n"
                    "Return a corrected response that satisfies the schema exactly. "
                    "Output only the JSON object, with no preamble or markdown fences."
                )
                _publish_llm_event(
                    trace_id,
                    {
                        "type": "repair_attempted",
                        "trace_id": trace_id,
                        "generation_id": generation_id,
                        "node": event_node,
                        "attempt": event_attempt,
                        "section_id": section_id,
                    },
                )
                local_attempt -= 1
                continue
            raise
        except Exception as exc:
            latency_ms = (time.perf_counter() - started_at) * 1000.0
            retryable = _is_retryable(exc)
            can_retry = retryable and local_attempt < retry_policy.max_attempts
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
                    attempt=event_attempt,
                    section_id=section_id,
                    latency_ms=latency_ms,
                    retryable=retryable,
                    error=str(exc),
                    error_class=type(exc).__name__,
                ),
            )
            if not can_retry:
                raise
            if isinstance(exc, TruncatedCompletionError):
                effective_settings = dict(effective_settings or {})
                current_max_tokens = int(effective_settings.get("max_tokens", 32000))
                effective_settings["max_tokens"] = min(
                    max(current_max_tokens + 1, int(current_max_tokens * 1.5)),
                    32000,
                )
            await asyncio.sleep(
                _retry_delay_seconds(
                    exc=exc,
                    attempt=local_attempt,
                    retry_policy=retry_policy,
                )
            )

    raise RuntimeError("run_llm exhausted retries unexpectedly")
