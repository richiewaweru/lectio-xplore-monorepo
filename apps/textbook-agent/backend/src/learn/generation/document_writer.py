"""Retired stub writers — DO NOT use in production.

Production Learn writing uses ``document.writer.write_document_primitive`` and
``learn.generation.interaction_writer.write_interaction_from_request``.

This module remains only so historical unit tests that imported the symbols
can be updated; calling these functions raises.
"""

from __future__ import annotations

from typing import Any, Mapping


class StubWriterRetiredError(RuntimeError):
    """Raised when a retired stub writer is invoked."""


def write_document_node(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise StubWriterRetiredError(
        "write_document_node stub is retired — use document.writer.write_document_primitive"
    )


def write_interaction_node(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise StubWriterRetiredError(
        "write_interaction_node stub is retired — use "
        "learn.generation.interaction_writer.write_interaction_from_request"
    )


__all__ = ["StubWriterRetiredError", "write_document_node", "write_interaction_node"]
