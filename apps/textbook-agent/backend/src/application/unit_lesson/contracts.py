"""Unit-lesson preparation contracts and type aliases."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from curriculum.models import (
    ComponentSelection,
    PathStructuralPagePlan,
    PathStructuralPlan,
)


class PathPreparationBlocked(ValueError):
    pass


StructuralPlanner = Callable[
    [dict[str, Any]], Awaitable[PathStructuralPlan | PathStructuralPagePlan]
]
ComponentSelector = Callable[[dict[str, Any]], Awaitable[ComponentSelection]]

__all__ = [
    "ComponentSelector",
    "PathPreparationBlocked",
    "StructuralPlanner",
]
