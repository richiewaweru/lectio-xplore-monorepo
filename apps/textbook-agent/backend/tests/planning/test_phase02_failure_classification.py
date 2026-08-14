"""Phase 02.1: typed failure classification policy."""

from __future__ import annotations

import asyncio

import httpx
from pydantic import BaseModel, ValidationError
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError

from planning.whole_lesson.failure_policy import classify_failure, structured_error_from_exc
from planning.whole_lesson.states import LeaseLostError, ResumeDecision, decide_resume
from planning.whole_lesson.teaching_errors import TeachingPlanOutputInvalidError


def test_transport_timeout_rate_limit_retryable() -> None:
    assert classify_failure(httpx.ConnectError("boom")).code == "TRANSPORT"
    assert classify_failure(httpx.ConnectError("boom")).retryable is True
    assert classify_failure(asyncio.TimeoutError()).code == "TIMEOUT"
    req = httpx.Request("GET", "https://example.test")
    resp = httpx.Response(429, request=req)
    assert classify_failure(httpx.HTTPStatusError("rl", request=req, response=resp)).code == (
        "RATE_LIMIT"
    )


def test_pydantic_ai_provider_failures_are_typed() -> None:
    connection = classify_failure(
        ModelAPIError(model_name="deepseek-v4", message="Connection error.")
    )
    assert connection.code == "TRANSPORT"
    assert connection.retryable is True

    rate_limit = classify_failure(
        ModelHTTPError(status_code=429, model_name="deepseek-v4", body=None)
    )
    assert rate_limit.code == "RATE_LIMIT"
    assert rate_limit.retryable is True

    bad_request = classify_failure(
        ModelHTTPError(status_code=400, model_name="deepseek-v4", body=None)
    )
    assert bad_request.code == "UNKNOWN"
    assert bad_request.retryable is False


def test_content_validation_error_not_executor_repairable() -> None:
    from generation.page_objects import ContentValidationError

    exc = ContentValidationError(
        "questions",
        [{"path": "items.0.correct_key", "message": "Extra inputs are not permitted"}],
    )
    c = classify_failure(exc)
    assert c.code == "VALIDATION"
    assert c.retryable is True
    assert c.repairable is False


def test_teaching_output_invalid_has_dedicated_recoverable_code() -> None:
    c = classify_failure(
        TeachingPlanOutputInvalidError(
            attempt_count=2,
            details=["SLOT_ORDER: sections are invalid"],
        )
    )
    assert c.code == "MODEL_OUTPUT_INVALID"
    assert c.retryable is True
    assert c.repairable is False


def test_validation_repairable_once() -> None:
    class M(BaseModel):
        x: int

    try:
        M.model_validate({"x": "nope"})
    except ValidationError as exc:
        c = classify_failure(exc)
        assert c.code == "VALIDATION"
        assert c.repairable is True
        assert c.retryable is False


def test_programming_terminal() -> None:
    c = classify_failure(TypeError("bad"))
    assert c.code == "PROGRAMMING"
    assert c.retryable is False


def test_lease_lost_quiet() -> None:
    c = classify_failure(LeaseLostError("gone"))
    assert c.code == "LEASE_LOST"
    assert c.retryable is False


def test_structured_error_non_empty_message() -> None:
    err = structured_error_from_exc(exc=TypeError(""), stage="writing_blocks")
    assert err["message"]
    assert err["code"] == "PROGRAMMING"


def test_resume_decisions() -> None:
    assert decide_resume(None, current_lease_token=1) == ResumeDecision.RUN_MISSING
    assert (
        decide_resume({"status": "ready"}, current_lease_token=1)
        == ResumeDecision.SKIP_READY
    )
    assert (
        decide_resume({"status": "visual_pending"}, current_lease_token=1)
        == ResumeDecision.SKIP_READY
    )
    assert (
        decide_resume({"status": "started", "lease_token": 2}, current_lease_token=2)
        == ResumeDecision.SKIP_IN_FLIGHT
    )
    assert (
        decide_resume({"status": "started", "lease_token": 1}, current_lease_token=2)
        == ResumeDecision.RETRY_ABANDONED
    )
    assert (
        decide_resume({"status": "started"}, current_lease_token=2)
        == ResumeDecision.RETRY_ABANDONED
    )
    assert (
        decide_resume({"status": "failed_recoverable"}, current_lease_token=1)
        == ResumeDecision.RETRY_FAILED
    )
    assert (
        decide_resume({"status": "failed_terminal"}, current_lease_token=1)
        == ResumeDecision.BLOCK_TERMINAL
    )
