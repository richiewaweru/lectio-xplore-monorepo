"""D4: skeleton shadow persistence retired with skeleton_shadow_records drop.

Catalog helpers in v3_blueprint.skeletons remain for Unit path shape.
"""

from __future__ import annotations

from typing import Any


async def record_skeleton_shadow(*_args: Any, **_kwargs: Any) -> None:
    """No-op — table and readers retired (D3/D4)."""
    return None


async def list_shadow_records(*_args: Any, **_kwargs: Any) -> list[Any]:
    return []


def structural_match_score(*_args: Any, **_kwargs: Any) -> float:
    return 0.0


def shadow_records_csv(*_args: Any, **_kwargs: Any) -> str:
    return ""


async def shadow_review_csv(*_args: Any, **_kwargs: Any) -> str:
    return ""
