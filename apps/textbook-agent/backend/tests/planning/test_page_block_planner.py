"""RUN_03 gate: fixture page-block planning without component selector."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from planning import page_blocks
from planning.page_blocks import plan_conceptual_first_exposure_blocks


@pytest.mark.asyncio
async def test_fixture_plans_all_conceptual_first_exposure_slots(monkeypatch) -> None:
    called = AsyncMock()
    monkeypatch.setattr(
        "planning.agents.run_component_selector",
        called,
    )
    plans = await plan_conceptual_first_exposure_blocks(allow_paid=False)
    assert set(plans) == set(page_blocks.CONCEPTUAL_FIRST_EXPOSURE_SLOTS)
    for slot_id, plan in plans.items():
        assert plan.blocks, slot_id
        for index, block in enumerate(plan.blocks):
            assert block.position == index
            assert block.object != "heading"
            assert block.evidence.strip()
            assert block.brief.strip()
    called.assert_not_called()


@pytest.mark.asyncio
async def test_paid_without_planner_raises() -> None:
    with pytest.raises(page_blocks.PageBlockPlanError, match="Paid"):
        await page_blocks.plan_section_blocks(slot_id="orient", allow_paid=True)
