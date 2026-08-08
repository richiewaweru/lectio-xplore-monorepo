"""Item-generation attempt diagnostics (Phase 02)."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from planning.llm_contract_errors import is_transport_error, structured_output_errors
from planning.whole_lesson.failure_policy import classify_failure
from pydantic import ValidationError

OutcomeClass = Literal["OK", "TRANSPORT", "TIMEOUT", "RATE_LIMIT", "CONTRACT", "SEMANTIC", "UNKNOWN"]


def classify_item_failure(exc: BaseException) -> tuple[OutcomeClass, bool]:
    """Separate transport vs contract vs semantic item failures."""
    message = str(exc).lower()
    if isinstance(exc, ValidationError) or (
        isinstance(exc, ValueError)
        and any(token in message for token in ("card_id", "schema", "field", "type"))
    ):
        return "CONTRACT", False
    if isinstance(exc, ValueError) and any(
        token in message
        for token in (
            "misconception",
            "coverage",
            "unmapped",
            "question ids must be unique",
            "semantic",
        )
    ):
        return "SEMANTIC", True
    classification = classify_failure(exc)
    if classification.code == "TIMEOUT":
        return "TIMEOUT", True
    if classification.code == "RATE_LIMIT":
        return "RATE_LIMIT", True
    if classification.code == "TRANSPORT" or is_transport_error(exc):
        return "TRANSPORT", True
    if classification.code in {"VALIDATION", "CONTRACT"} or structured_output_errors(exc):
        return "CONTRACT", classification.retryable
    return "UNKNOWN", classification.retryable


def new_item_correlation_id(*, generation_id: str | None, card_id: str) -> str:
    prefix = (generation_id or "nogeneration")[:12]
    return f"item:{prefix}:{card_id}:{uuid.uuid4().hex[:8]}"


def attempt_record(
    *,
    correlation_id: str,
    card_id: str,
    attempt: int,
    started_at: float,
    outcome_class: OutcomeClass,
    error: str | None = None,
    validation_errors: list[str] | None = None,
    retryable: bool | None = None,
) -> dict[str, Any]:
    return {
        "correlation_id": correlation_id,
        "card_id": card_id,
        "attempt": attempt,
        "latency_ms": round((time.perf_counter() - started_at) * 1000.0, 2),
        "class": outcome_class,
        "retryable": bool(retryable) if retryable is not None else outcome_class != "OK",
        "error": error,
        "validation_errors": list(validation_errors or []),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
