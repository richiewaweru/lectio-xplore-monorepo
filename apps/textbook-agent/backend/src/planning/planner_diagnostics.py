"""Sanitized failure diagnostics for constrained planner nodes.

Constrained nodes (structural planner, form planner) fail in ways the generic
LLM event stream cannot explain on its own: a provider contract rejection looks
identical to a local validation failure once it reaches the caller. These helpers
record the missing detail — which node, which model, which attempt, whether
provider reasoning was enabled, and whether a repair payload was attached.

Nothing here may log credentials, prompts, user payloads, or raw model text.
Only node identity, model identity, error classification, and our own validator
strings (which contain slot ids) are safe to emit.
"""

from __future__ import annotations

import logging
from typing import Any

from v3_execution.config import get_v3_spec
from v3_execution.config.models import V3_NODE_REASONING

logger = logging.getLogger(__name__)

_MAX_LOGGED_ERRORS = 5


def _http_status(exc: BaseException | None) -> Any:
    """Best-effort HTTP status from a provider exception or its cause."""
    for candidate in (exc, getattr(exc, "__cause__", None)):
        if candidate is None:
            continue
        status = getattr(candidate, "status_code", None)
        if status is not None:
            return status
    return None


def log_planner_attempt_failed(
    *,
    node: str,
    attempt: int,
    errors: list[str],
    exc: BaseException | None = None,
    repair_attached: bool = False,
    will_retry: bool = False,
) -> None:
    """Record one failed constrained-planner attempt.

    ``exc`` is ``None`` when the model answered but failed our own context
    validation — that distinction is the main thing this log exists to capture.
    """
    try:
        spec = get_v3_spec(node)
        model_name = spec.model_name
        family = spec.family.value
    except Exception:  # noqa: BLE001 - diagnostics must never mask the real failure
        model_name = "unknown"
        family = "unknown"

    logger.warning(
        "constrained planner attempt failed node=%s model=%s family=%s attempt=%d "
        "error_class=%s http_status=%s reasoning=%s error_count=%d errors=%s "
        "repair_attached=%s will_retry=%s",
        node,
        model_name,
        family,
        attempt,
        type(exc).__name__ if exc is not None else "context_validation",
        _http_status(exc),
        V3_NODE_REASONING.get(node, False),
        len(errors),
        errors[:_MAX_LOGGED_ERRORS],
        repair_attached,
        will_retry,
    )
