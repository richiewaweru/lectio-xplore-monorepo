"""Item-generation attempt diagnostics (Phase 02)."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import ValidationError
from pydantic_ai.exceptions import UnexpectedModelBehavior

from curriculum.llm_contract_errors import is_transport_error, structured_output_errors
from infra.execution.error_policy import classify_provider_error

OutcomeClass = Literal["OK", "TRANSPORT", "TIMEOUT", "RATE_LIMIT", "CONTRACT", "SEMANTIC", "UNKNOWN"]


class BackboneRefError(ValueError):
    """Item output does not reference the lesson backbone correctly (repairable)."""


def classify_item_failure(exc: BaseException) -> tuple[OutcomeClass, bool]:
    """Separate transport vs contract vs semantic item failures."""
    if isinstance(exc, BackboneRefError):
        return "SEMANTIC", True
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
    classification = classify_provider_error(
        exc,
        status_code=getattr(exc, "status_code", None),
    )
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
        return "TIMEOUT", True
    if classification.error_class == "retryable_rate_limit":
        return "RATE_LIMIT", True
    if classification.retryable or is_transport_error(exc):
        return "TRANSPORT", True
    extracted = structured_output_errors(exc)
    # Structured-output failures are often wrapped by UnexpectedModelBehavior.
    # If the extraction is just the fallback (type+message), do not treat it as
    # an automatic repair candidate; otherwise we would loop on programming
    # errors until exhaustion.
    if isinstance(exc, UnexpectedModelBehavior):
        only_fallback = (
            len(extracted) == 1
            and extracted[0].startswith(f"{type(exc).__name__}:")
        )
        if not only_fallback:
            return "CONTRACT", True
    return "UNKNOWN", False


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
