"""Safe provider error classification (no raw provider text leaks)."""

from __future__ import annotations

import pytest

from media.generation.provider_errors import (
    classify_provider_exception,
    is_auth_provider_code,
    is_non_retryable_provider_code,
    safe_summary_for_code,
)


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _HttpxLike(Exception):
    def __init__(self, status: int) -> None:
        super().__init__("secret prompt text and key=abc")
        self.response = _Response(status)


class _GenaiLike(Exception):
    code = 403


class _ConnectTimeout(Exception):
    pass


def test_classifies_http_statuses_from_response_and_code() -> None:
    assert classify_provider_exception(_HttpxLike(429)) == "provider_http_429"
    assert classify_provider_exception(_GenaiLike("denied")) == "provider_http_403"


def test_classifies_timeout_no_image_and_unknown() -> None:
    assert classify_provider_exception(TimeoutError()) == "provider_timeout"
    assert classify_provider_exception(_ConnectTimeout()) == "provider_timeout"
    assert (
        classify_provider_exception(RuntimeError("Gemini returned no image data in response"))
        == "provider_no_image"
    )
    assert classify_provider_exception(RuntimeError("boom")) == "provider_error"
    assert classify_provider_exception(None) == "provider_error"


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_non_retryable_in_executor(status: int) -> None:
    assert is_non_retryable_provider_code(f"provider_http_{status}")


def test_server_errors_stay_retryable_and_auth_is_not_auto_retried() -> None:
    assert not is_non_retryable_provider_code("provider_http_503")
    assert not is_non_retryable_provider_code("provider_timeout")
    assert is_auth_provider_code("provider_http_403")
    assert is_auth_provider_code("provider_http_400")  # Gemini invalid API key
    assert not is_auth_provider_code("provider_http_429")


def test_safe_summary_never_includes_raw_text() -> None:
    summary = safe_summary_for_code("provider_http_403")
    assert summary == (
        "Figure generation failed: the image provider rejected the request (HTTP 403)."
    )
    assert "secret" not in safe_summary_for_code("provider_error")
