"""Typed failure classification for native writer retries."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from planning.whole_lesson.states import LeaseLostError
from planning.whole_lesson.teaching_errors import TeachingPlanOutputInvalidError

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

try:
    from pydantic import ValidationError as PydanticValidationError
except ImportError:  # pragma: no cover
    PydanticValidationError = None  # type: ignore[misc, assignment]

try:
    from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
except ImportError:  # pragma: no cover
    ModelAPIError = None  # type: ignore[misc, assignment]
    ModelHTTPError = None  # type: ignore[misc, assignment]


@dataclass(frozen=True)
class FailureClassification:
    code: str
    retryable: bool
    repairable: bool


def classify_failure(exc: BaseException) -> FailureClassification:
    # ContentValidationError: repair already consumed inside dispatch_writer_async.
    # Surface VALIDATION as retryable (failed_recoverable) but not executor-repairable.
    try:
        from generation.page_objects import ContentValidationError
    except ImportError:  # pragma: no cover
        ContentValidationError = None  # type: ignore[misc, assignment]

    if ContentValidationError is not None and isinstance(exc, ContentValidationError):
        return FailureClassification(code="VALIDATION", retryable=True, repairable=False)
    if isinstance(exc, TeachingPlanOutputInvalidError):
        return FailureClassification(
            code="MODEL_OUTPUT_INVALID", retryable=True, repairable=False
        )
    if isinstance(exc, LeaseLostError):
        return FailureClassification(code="LEASE_LOST", retryable=False, repairable=False)
    if isinstance(exc, asyncio.CancelledError):
        return FailureClassification(code="CANCELLED", retryable=False, repairable=False)
    if isinstance(exc, (TypeError, AttributeError, NameError, SyntaxError)):
        return FailureClassification(code="PROGRAMMING", retryable=False, repairable=False)
    if PydanticValidationError is not None and isinstance(exc, PydanticValidationError):
        return FailureClassification(code="VALIDATION", retryable=False, repairable=True)
    if isinstance(exc, (ValueError, KeyError)) and "contract" in str(exc).lower():
        return FailureClassification(code="CONTRACT", retryable=False, repairable=True)
    if isinstance(exc, ValueError) and any(
        token in str(exc).lower() for token in ("validat", "schema", "intent", "object")
    ):
        return FailureClassification(code="VALIDATION", retryable=False, repairable=True)

    if isinstance(exc, asyncio.TimeoutError):
        return FailureClassification(code="TIMEOUT", retryable=True, repairable=False)
    if httpx is not None:
        if isinstance(exc, httpx.TimeoutException):
            return FailureClassification(code="TIMEOUT", retryable=True, repairable=False)
        if isinstance(exc, httpx.HTTPStatusError):
            status = int(getattr(exc.response, "status_code", 0) or 0)
            if status == 429:
                return FailureClassification(code="RATE_LIMIT", retryable=True, repairable=False)
            if status >= 500:
                return FailureClassification(code="TRANSPORT", retryable=True, repairable=False)
            return FailureClassification(code="UNKNOWN", retryable=False, repairable=False)
        if isinstance(exc, (httpx.TransportError, httpx.NetworkError, httpx.RemoteProtocolError)):
            return FailureClassification(code="TRANSPORT", retryable=True, repairable=False)
        if isinstance(exc, httpx.HTTPError):
            return FailureClassification(code="TRANSPORT", retryable=True, repairable=False)

    # Pydantic AI wraps provider network failures in ModelAPIError. HTTP failures
    # retain their status in the narrower ModelHTTPError subtype.
    if ModelHTTPError is not None and isinstance(exc, ModelHTTPError):
        status = int(getattr(exc, "status_code", 0) or 0)
        if status == 429:
            return FailureClassification(code="RATE_LIMIT", retryable=True, repairable=False)
        if status >= 500:
            return FailureClassification(code="TRANSPORT", retryable=True, repairable=False)
        return FailureClassification(code="UNKNOWN", retryable=False, repairable=False)
    if ModelAPIError is not None and isinstance(exc, ModelAPIError):
        return FailureClassification(code="TRANSPORT", retryable=True, repairable=False)

    # Connection-family OS errors (still typed, not message-primary).
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return FailureClassification(code="TRANSPORT", retryable=True, repairable=False)

    return FailureClassification(code="UNKNOWN", retryable=False, repairable=False)


def structured_error_from_exc(
    *,
    exc: BaseException,
    stage: str,
    section_id: str = "",
    block_id: str = "",
    key: str = "",
    attempt: int = 1,
) -> dict[str, Any]:
    import time

    classification = classify_failure(exc)
    message = str(exc).strip()[:500] or type(exc).__name__
    return {
        "type": type(exc).__name__,
        "code": classification.code,
        "message": message,
        "stage": stage,
        "section_id": section_id,
        "block_id": block_id,
        "execution_key": key,
        "attempt": attempt,
        "retryable": classification.retryable,
        "repairable": classification.repairable,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
