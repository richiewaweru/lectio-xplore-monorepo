from __future__ import annotations

import asyncio
import json
import logging
import sys

import core.events as core_events

from pipeline.console_diagnostics import force_console_log
from pipeline.events import DiagramOutcomeEvent, ImageOutcomeEvent
from pipeline.media.providers.image_client import ImageSize
from pipeline.providers.image_client import ImageGenerationResult
from pipeline.runtime_diagnostics import publish_runtime_event
from pipeline.state import TextbookPipelineState

logger = logging.getLogger(__name__)

_IMAGE_TIMEOUT_SECONDS = 45.0
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = (1.0, 2.0)


def diag(tag: str, **fields) -> None:
    sys.stderr.write(f"DIAG::{tag}::{json.dumps(fields, default=str)}\n")
    sys.stderr.flush()


diag("BUILD_MARKER", file="image_generator", version="diag_v1")


def _imggen_diag(event: str, **fields) -> None:
    force_console_log("IMGGEN_AI", event, **fields)


def _publish_image_outcome(
    generation_id: str,
    section_id: str | None,
    outcome: str,
    *,
    provider: str | None = None,
    attempts: int = 1,
    error_message: str | None = None,
    duration_ms: float | None = None,
) -> None:
    if not generation_id or not section_id:
        return
    core_events.event_bus.publish(
        generation_id,
        ImageOutcomeEvent(
            generation_id=generation_id,
            section_id=section_id,
            outcome=outcome,
            provider=provider,
            attempts=attempts,
            error_message=error_message,
            duration_ms=duration_ms,
        ),
    )


def _log_image_event(level: int, event: str, **payload) -> None:
    logger.log(
        level,
        "IMG::%s::%s",
        event,
        json.dumps(payload, sort_keys=True, default=str),
    )


def _publish_diagram_outcome(
    generation_id: str,
    section_id: str | None,
    outcome: str,
) -> None:
    if not generation_id or not section_id:
        return
    publish_runtime_event(
        generation_id,
        DiagramOutcomeEvent(
            generation_id=generation_id,
            section_id=section_id,
            outcome=outcome,
        ),
    )


def _with_outcome(state: TextbookPipelineState, section_id: str | None, outcome: str) -> dict:
    if section_id is None:
        return {}

    outcomes = dict(state.diagram_outcomes)
    outcomes[section_id] = outcome
    _publish_diagram_outcome(state.request.generation_id or "", section_id, outcome)
    return {"diagram_outcomes": outcomes}


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        keyword in msg
        for keyword in ("timeout", "connection", "unavailable", "rate", "503", "502", "500")
    )


async def _generate_with_retry(
    client,
    prompt: str,
    timeout: float,
    size: ImageSize = "1024x1024",
) -> tuple[ImageGenerationResult, int]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            _imggen_diag(
                "ATTEMPT",
                attempt=attempt,
                max_attempts=_MAX_ATTEMPTS,
                prompt_length=len(prompt),
                timeout_seconds=timeout,
            )
            result = await asyncio.wait_for(
                client.generate_image(prompt=prompt, size=size, format="png"),
                timeout=timeout,
            )
            return result, attempt
        except Exception as exc:
            is_timeout = isinstance(exc, asyncio.TimeoutError)
            retryable = is_timeout or _is_retryable(exc)
            if not retryable or attempt == _MAX_ATTEMPTS:
                setattr(exc, "image_attempts", attempt)
                raise

            backoff = _RETRY_BACKOFF[attempt - 1]
            logger.warning(
                "image_generator: attempt %d/%d failed (%s), retrying in %.1fs",
                attempt,
                _MAX_ATTEMPTS,
                "timeout" if is_timeout else exc,
                backoff,
            )
            _imggen_diag(
                "RETRY",
                attempt=attempt,
                max_attempts=_MAX_ATTEMPTS,
                retryable=retryable,
                is_timeout=is_timeout,
                backoff_seconds=backoff,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            await asyncio.sleep(backoff)
    raise RuntimeError("image generation retry loop exited unexpectedly")


async def _request_image_bytes(
    *,
    client,
    prompt: str,
    section_id: str,
    variant: str,
    api_key_present: bool,
    size: ImageSize = "1024x1024",
    prompt_details: dict | None = None,
) -> tuple[ImageGenerationResult, int]:
    payload = {
        "section_id": section_id,
        "variant": variant,
        "client_class": type(client).__name__,
        "api_key_present": api_key_present,
        "prompt_chars": len(prompt),
    }
    if prompt_details:
        payload.update(prompt_details)

    _log_image_event(logging.INFO, "API_REQUEST", **payload)
    try:
        image_result, attempts = await _generate_with_retry(client, prompt, _IMAGE_TIMEOUT_SECONDS, size=size)
    except Exception as exc:
        _log_image_event(
            logging.ERROR,
            "API_FAILURE",
            section_id=section_id,
            variant=variant,
            error_type=type(exc).__name__,
            error_message=str(exc)[:500],
        )
        raise

    _log_image_event(
        logging.INFO,
        "API_SUCCESS",
        section_id=section_id,
        variant=variant,
        bytes=len(image_result.bytes),
        attempts=attempts,
        format=image_result.format,
        mime_type=image_result.mime_type,
    )
    return image_result, attempts


async def _store_image_with_logging(
    store,
    *,
    image_bytes: bytes,
    generation_id: str,
    section_id: str,
    filename: str,
    format: str,
    variant: str,
) -> str:
    try:
        image_url = await store.store_image(
            image_bytes,
            generation_id=generation_id,
            section_id=section_id,
            filename=filename,
            format=format,
        )
    except Exception as exc:
        _log_image_event(
            logging.ERROR,
            "STORE_WRITE_FAILURE",
            section_id=section_id,
            variant=variant,
            error_type=type(exc).__name__,
            error_message=str(exc)[:500],
        )
        raise RuntimeError(
            f"Image storage failed for {variant}: {type(exc).__name__}: {exc}"
        ) from exc

    _log_image_event(
        logging.INFO,
        "STORE_SUCCESS",
        section_id=section_id,
        variant=variant,
        asset_url_present=bool(image_url),
        format=format,
    )
    return image_url


def _filename_for_variant(stem: str, image_result: ImageGenerationResult) -> str:
    return f"{stem}.{image_result.format}"


async def image_generator(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    _store=None,
    _client=None,
) -> dict:
    from pipeline.media.executors.image_generator import image_generator as execute_image_generator

    return await execute_image_generator(
        state,
        model_overrides=model_overrides,
        _store=_store,
        _client=_client,
    )
