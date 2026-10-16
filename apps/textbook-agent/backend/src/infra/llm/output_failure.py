"""Safe, structural summary of a structured-output (schema) failure.

With in-library output retry disabled, pydantic-ai reports a reply that does
not match the output schema as ``UnexpectedModelBehavior`` ("Exceeded maximum
output retries") whose ``__cause__`` is a ``ToolRetryError``. That cause holds
the pydantic error list (or a plain string for empty/reasoning-only replies).

This module reduces such a failure to a closed ``kind``, pydantic error
``type`` codes, and field paths built only from ``loc``. It never reads
``msg`` or ``input`` text because those can echo model output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

KIND_SCHEMA_MISMATCH = "schema_mismatch"
KIND_NON_ACTIONABLE_REPLY = "non_actionable_reply"
KIND_EMPTY_REPLY = "empty_reply"
KIND_INCOMPLETE_TOOL_CALL = "incomplete_tool_call"

MAX_OUTPUT_FAILURE_ENTRIES = 20
_MAX_SEGMENT_LENGTH = 40
_MAX_PATH_LENGTH = 120
_MAX_CAUSE_DEPTH = 6
_UNSAFE = re.compile(r"[^A-Za-z0-9_\-]")


@dataclass(frozen=True)
class OutputFailureSummary:
    """Bounded, content-free description of a structured-output failure."""

    kind: str
    error_types: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    #: Sorted unique ``(path, error_type)`` pairs; ``path`` is ``""`` for the root.
    issues: tuple[tuple[str, str], ...] = ()

    def as_fields(self) -> dict[str, Any]:
        return {
            "output_failure_kind": self.kind,
            "output_failure_error_types": list(self.error_types),
            "output_failure_paths": list(self.paths),
        }


def _safe_path(loc: Any) -> str:
    if not isinstance(loc, (list, tuple)):
        return ""
    path = ""
    for part in loc:
        if isinstance(part, bool):
            continue
        if isinstance(part, int):
            path += f"[{part}]"
            continue
        segment = _UNSAFE.sub("_", str(part))[:_MAX_SEGMENT_LENGTH]
        if segment:
            path += f".{segment}" if path else segment
    return path[:_MAX_PATH_LENGTH]


def _safe_type(value: Any) -> str:
    return _UNSAFE.sub("_", str(value or "invalid"))[:_MAX_SEGMENT_LENGTH]


def _schema_summary(errors: Any) -> OutputFailureSummary | None:
    pairs: set[tuple[str, str]] = set()
    for item in errors:
        if isinstance(item, dict):
            pairs.add((_safe_path(item.get("loc")), _safe_type(item.get("type"))))
    if not pairs:
        return None
    issues = tuple(sorted(pairs))[:MAX_OUTPUT_FAILURE_ENTRIES]
    return OutputFailureSummary(
        kind=KIND_SCHEMA_MISMATCH,
        error_types=tuple(sorted({kind for _path, kind in pairs}))[:MAX_OUTPUT_FAILURE_ENTRIES],
        paths=tuple(sorted({path for path, _kind in pairs if path}))[
            :MAX_OUTPUT_FAILURE_ENTRIES
        ],
        issues=issues,
    )


def summarize_output_failure(exc: BaseException) -> OutputFailureSummary | None:
    """Return a safe summary when ``exc`` (or its cause chain) is an output failure."""
    from pydantic_ai.exceptions import (
        IncompleteToolCall,
        ToolRetryError,
        UnexpectedModelBehavior,
    )

    current: BaseException | None = exc
    unexpected = False
    for _ in range(_MAX_CAUSE_DEPTH):
        if current is None:
            break
        if isinstance(current, IncompleteToolCall):
            return OutputFailureSummary(kind=KIND_INCOMPLETE_TOOL_CALL)
        if isinstance(current, ToolRetryError):
            content = getattr(current.tool_retry, "content", None)
            if isinstance(content, list):
                summary = _schema_summary(content)
                if summary is not None:
                    return summary
            if isinstance(content, str) and content.strip():
                return OutputFailureSummary(kind=KIND_NON_ACTIONABLE_REPLY)
            return OutputFailureSummary(kind=KIND_EMPTY_REPLY)
        if isinstance(current, ValidationError):
            summary = _schema_summary(current.errors(include_input=False, include_url=False))
            if summary is not None:
                return summary
        if isinstance(current, UnexpectedModelBehavior):
            unexpected = True
        current = current.__cause__
    if unexpected:
        return OutputFailureSummary(kind=KIND_EMPTY_REPLY)
    return None


__all__ = [
    "KIND_EMPTY_REPLY",
    "KIND_INCOMPLETE_TOOL_CALL",
    "KIND_NON_ACTIONABLE_REPLY",
    "KIND_SCHEMA_MISMATCH",
    "MAX_OUTPUT_FAILURE_ENTRIES",
    "OutputFailureSummary",
    "summarize_output_failure",
]
