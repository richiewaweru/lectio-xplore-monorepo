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
from collections.abc import Sequence
from typing import Any

from infra.authoring.model_policy import V3_NODE_REASONING, get_v3_spec

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


def log_path_lesson_modes(*, unit_id: str | None, lessons: Sequence[Any]) -> None:
    """Emit one ``path_lesson_modes`` event per persisted plan (no lesson content).

    ``lessons`` are canonical plan lessons. Only keys, mode values and whether a
    reason exists are logged. A ``path_lesson_mode_missing`` warning follows when
    any lesson has no mode.
    """
    try:
        per_lesson = [
            {
                "key": getattr(lesson, "key", None),
                "lesson_mode": getattr(lesson, "lesson_mode", None),
                "has_reason": bool(getattr(lesson, "lesson_mode_reason", None)),
            }
            for lesson in lessons
        ]
        with_mode = sum(1 for item in per_lesson if item["lesson_mode"])
        logger.info(
            "path_lesson_modes unit_id=%s total_lessons=%d lessons_with_mode=%d",
            unit_id,
            len(per_lesson),
            with_mode,
            extra={
                "event": "path_lesson_modes",
                "unit_id": unit_id,
                "total_lessons": len(per_lesson),
                "lessons_with_mode": with_mode,
                "lessons": per_lesson,
            },
        )
        if with_mode < len(per_lesson):
            logger.warning(
                "path_lesson_mode_missing unit_id=%s missing=%d total_lessons=%d",
                unit_id,
                len(per_lesson) - with_mode,
                len(per_lesson),
                extra={
                    "event": "path_lesson_mode_missing",
                    "unit_id": unit_id,
                    "missing_count": len(per_lesson) - with_mode,
                    "total_lessons": len(per_lesson),
                    "missing_keys": [item["key"] for item in per_lesson if not item["lesson_mode"]],
                },
            )
    except Exception:
        logger.debug("path_lesson_modes logging failed", exc_info=True)


def log_path_lesson_mode_invalid(*, key: str | None, raw_value: object) -> None:
    logger.warning(
        "path_lesson_mode_invalid key=%s raw_value=%r",
        key,
        str(raw_value)[:60],
        extra={
            "event": "path_lesson_mode_invalid",
            "key": key,
            "raw_value": str(raw_value)[:60],
        },
    )
