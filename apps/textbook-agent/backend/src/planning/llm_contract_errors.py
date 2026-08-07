"""Shared structured-output / contract error extraction for planner repair loops."""

from __future__ import annotations

from pydantic import ValidationError


def structured_output_errors(exc: BaseException) -> list[str]:
    """Extract actionable validation messages from a structured-output failure.

    With in-library output retry disabled (``NO_OUTPUT_RETRY``), a schema failure
    does not surface as a bare ``ValidationError``. pydantic-ai raises
    ``UnexpectedModelBehavior`` whose ``__cause__`` is a ``ToolRetryError`` whose
    ``tool_retry.content`` holds the pydantic error list. Walk that chain first,
    then fall back to a direct ``ValidationError``, then to the exception text.
    """
    content = getattr(getattr(exc, "__cause__", None), "tool_retry", None)
    content = getattr(content, "content", None)
    if isinstance(content, list):
        messages: list[str] = []
        for item in content:
            if isinstance(item, dict):
                loc = ".".join(str(part) for part in (item.get("loc") or ()))
                messages.append(f"{loc}: {item.get('msg')}" if loc else str(item.get("msg")))
            else:
                messages.append(str(item))
        if messages:
            return messages
    if isinstance(exc, ValidationError):
        return [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        ]
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, ValidationError):
        return [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in cause.errors()
        ]
    return [f"{type(exc).__name__}: {exc}"]


def is_transport_error(exc: BaseException) -> bool:
    """Heuristic: provider/network failures are not contract repair targets."""
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    markers = (
        "timeout",
        "timed out",
        "rate limit",
        "ratelimit",
        "connection",
        "unavailable",
        "503",
        "502",
        "429",
        "transport",
        "network",
    )
    if any(marker in name for marker in ("timeout", "connection", "transport", "http")):
        return True
    return any(marker in text for marker in markers)
