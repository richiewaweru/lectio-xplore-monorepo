"""Safe, teacher-facing classification of image-provider failures.

Raw provider messages can carry prompts, URLs and keys, so they stay in logs
only. Everything that reaches the status API is one of the codes below.

Codes: ``provider_http_<status>`` (an HTTP status was discoverable),
``provider_timeout``, ``provider_no_image`` and ``provider_error``.
"""

from __future__ import annotations

import re

PROVIDER_TIMEOUT = "provider_timeout"
PROVIDER_NO_IMAGE = "provider_no_image"
PROVIDER_ERROR = "provider_error"

# Retrying these inside the executor only hammers the provider; the work item
# stays retryable so a key fix followed by Retry works.
NON_RETRYABLE_HTTP_STATUSES = frozenset({400, 401, 403, 404})
# Auto-retry never helps without an operator/key change. A 400 is a request or
# key problem (Gemini reports an invalid API key as 400); resending cannot help.
AUTH_HTTP_STATUSES = frozenset({400, 401, 403, 404})

_HTTP_CODE_RE = re.compile(r"^provider_http_(\d{3})$")


def _http_status(exc: BaseException) -> int | None:
    candidates: list[object] = []
    response = getattr(exc, "response", None)
    candidates.append(getattr(response, "status_code", None))
    candidates.append(getattr(exc, "status_code", None))
    # google-genai APIError exposes the HTTP status as ``code``.
    candidates.append(getattr(exc, "code", None))
    for value in candidates:
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if 100 <= value <= 599:
            return value
    return None


def classify_provider_exception(exc: BaseException | None) -> str:
    """Map a provider exception to a safe error code (never includes raw text)."""
    if exc is None:
        return PROVIDER_ERROR
    status = _http_status(exc)
    if status is not None:
        return f"provider_http_{status}"
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.casefold():
        return PROVIDER_TIMEOUT
    if "returned no image data" in str(exc):
        return PROVIDER_NO_IMAGE
    return PROVIDER_ERROR


def http_status_from_code(code: str | None) -> int | None:
    match = _HTTP_CODE_RE.match(code or "")
    return int(match.group(1)) if match else None


def is_non_retryable_provider_code(code: str | None) -> bool:
    return http_status_from_code(code) in NON_RETRYABLE_HTTP_STATUSES


def is_auth_provider_code(code: str | None) -> bool:
    return http_status_from_code(code) in AUTH_HTTP_STATUSES


def safe_summary_for_code(code: str | None) -> str:
    """Teacher-safe sentence for a provider error code."""
    status = http_status_from_code(code)
    if status is not None:
        if status in {401, 403}:
            return (
                "Figure generation failed: the image provider rejected the request "
                f"(HTTP {status})."
            )
        if status == 429:
            return "Figure generation failed: the image provider is rate limiting requests (HTTP 429)."
        if status >= 500:
            return (
                "Figure generation failed: the image provider had a temporary problem "
                f"(HTTP {status})."
            )
        return f"Figure generation failed: the image provider returned an error (HTTP {status})."
    if code == PROVIDER_TIMEOUT:
        return "Figure generation failed: the image provider timed out."
    if code == PROVIDER_NO_IMAGE:
        return "Figure generation failed: the image provider returned no image."
    # Code-rendered figures (media.render) fail without any image provider.
    if code == "render_spec_invalid":
        return "Figure drawing failed: the figure description could not be made consistent."
    if code == "render_layout_failed":
        return "Figure drawing failed: the labels could not be fitted legibly."
    return "Figure generation failed: the image provider reported an error."


__all__ = [
    "classify_provider_exception",
    "http_status_from_code",
    "is_auth_provider_code",
    "is_non_retryable_provider_code",
    "safe_summary_for_code",
]
