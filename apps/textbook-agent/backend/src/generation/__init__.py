from __future__ import annotations

from typing import Any

__all__ = ["generation_router"]


def __getattr__(name: str) -> Any:
    if name == "generation_router":
        from .routes import router as generation_router

        return generation_router
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
