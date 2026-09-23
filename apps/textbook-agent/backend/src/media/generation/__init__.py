"""Visual generation package.

`execute_visual` is loaded on first access so contract imports do not pull
the executor (and its QC dependency) during package initialization.
"""

from __future__ import annotations

from typing import Any

__all__ = ["execute_visual"]


def __getattr__(name: str) -> Any:
    if name == "execute_visual":
        from media.generation.executor import execute_visual

        return execute_visual
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
