"""D4: skeleton shadow persistence retired."""

from __future__ import annotations

import pytest

from v3_blueprint.shadow import (
    list_shadow_records,
    record_skeleton_shadow,
    structural_match_score,
)


@pytest.mark.asyncio
async def test_record_skeleton_shadow_is_noop() -> None:
    assert await record_skeleton_shadow(generation_id="g1") is None
    assert await list_shadow_records() == []
    assert structural_match_score(["a"], ["b"]) == 0.0
