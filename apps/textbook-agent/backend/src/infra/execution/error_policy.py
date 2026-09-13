"""Provider error classification for bounded repair (P03 G12)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

ErrorClass = Literal[
    "retryable_transport",
    "retryable_rate_limit",
    "retryable_overload",
    "permanent_auth",
    "permanent_invalid_request",
    "permanent_quota",
    "permanent_schema",
    "unknown",
]


@dataclass(frozen=True)
class ClassifiedProviderError:
    error_class: ErrorClass
    retryable: bool
    message: str
    retry_after_seconds: float | None = None
    deadline_exceeded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_class": self.error_class,
            "retryable": self.retryable,
            "message": self.message,
            "retry_after_seconds": self.retry_after_seconds,
            "deadline_exceeded": self.deadline_exceeded,
        }


_RETRY_AFTER_RE = re.compile(r"retry[- ]after[:\s]+(\d+(?:\.\d+)?)", re.IGNORECASE)


def _parse_retry_after(message: str, headers: dict[str, str] | None) -> float | None:
    if headers:
        for key, value in headers.items():
            if key.lower() == "retry-after":
                try:
                    return float(value)
                except ValueError:
                    continue
    match = _RETRY_AFTER_RE.search(message)
    if match:
        return float(match.group(1))
    return None


def classify_provider_error(
    exc: BaseException,
    *,
    status_code: int | None = None,
    headers: dict[str, str] | None = None,
    deadline_at: datetime | None = None,
    now: datetime | None = None,
) -> ClassifiedProviderError:
    """Distinguish retryable provider failures from permanent ones."""
    message = str(exc)
    lower = message.lower()
    current = now or datetime.now(UTC)
    deadline_exceeded = False
    if deadline_at is not None:
        deadline = deadline_at if deadline_at.tzinfo else deadline_at.replace(tzinfo=UTC)
        if current >= deadline:
            deadline_exceeded = True

    retry_after = _parse_retry_after(message, headers)

    if deadline_exceeded:
        return ClassifiedProviderError(
            error_class="retryable_transport",
            retryable=False,
            message=message,
            retry_after_seconds=retry_after,
            deadline_exceeded=True,
        )

    if status_code == 401 or status_code == 403 or "invalid api key" in lower:
        return ClassifiedProviderError("permanent_auth", False, message, retry_after)
    if status_code == 400 or "invalid_request" in lower or "invalid parameter" in lower:
        return ClassifiedProviderError(
            "permanent_invalid_request", False, message, retry_after
        )
    if status_code == 402 or "quota" in lower or "billing" in lower:
        return ClassifiedProviderError("permanent_quota", False, message, retry_after)
    if "schema" in lower and ("incompatible" in lower or "validation" in lower):
        return ClassifiedProviderError("permanent_schema", False, message, retry_after)

    if status_code == 429 or "rate limit" in lower or "too many requests" in lower:
        return ClassifiedProviderError(
            "retryable_rate_limit", True, message, retry_after or 1.0
        )
    if status_code in {500, 502, 503, 504} or "overload" in lower or "unavailable" in lower:
        return ClassifiedProviderError(
            "retryable_overload", True, message, retry_after
        )
    if (
        status_code is None
        and (
            "timeout" in lower
            or "connection" in lower
            or "temporarily" in lower
            or isinstance(exc, (TimeoutError, ConnectionError))
        )
    ):
        return ClassifiedProviderError("retryable_transport", True, message, retry_after)

    # Streaming failure after HTTP 200 still surfaces as transport/content error.
    if "stream" in lower and ("closed" in lower or "interrupted" in lower or "truncated" in lower):
        return ClassifiedProviderError("retryable_transport", True, message, retry_after)

    return ClassifiedProviderError("unknown", False, message, retry_after)


def honor_retry_after(
    classified: ClassifiedProviderError,
    *,
    deadline_at: datetime | None = None,
    now: datetime | None = None,
) -> float | None:
    """Return sleep seconds if retry is allowed before the deadline; else None."""
    if not classified.retryable or classified.deadline_exceeded:
        return None
    delay = float(classified.retry_after_seconds or 0.0)
    if deadline_at is None:
        return delay
    current = now or datetime.now(UTC)
    deadline = deadline_at if deadline_at.tzinfo else deadline_at.replace(tzinfo=UTC)
    if current + timedelta(seconds=delay) >= deadline:
        return None
    return delay


__all__ = [
    "ClassifiedProviderError",
    "ErrorClass",
    "classify_provider_error",
    "honor_retry_after",
]
