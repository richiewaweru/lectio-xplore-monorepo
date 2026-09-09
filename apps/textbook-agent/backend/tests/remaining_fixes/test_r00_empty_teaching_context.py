"""R00 regression: closed Learn production must carry preparation facts, not hardcoded empties."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from infra.authoring import AuthoringProviderCall
from learn.generation.authoring_adapter import author_learn_work_orders
from learn.generation.native_production import build_closed_learn_production
from learn.generation.preparation_context import LearnPreparationContext
from learn.resources.native_policy import default_learn_policy


PREP_FACTS = [
    "Speed v equals 5 m/s.",
    "Time t equals 10 s.",
    "Distance d equals v times t.",
]


class ContentProvider:
    async def invoke(self, call: AuthoringProviderCall) -> dict[str, object]:
        if call.capability_id == "explanation-block":
            return {
                "body": "Distance equals speed multiplied by time.",
                "emphasis": ["distance"],
            }
        return {"variant": "info", "body": "Use v, t and d equals v times t."}


@pytest.mark.asyncio
async def test_r00_build_closed_learn_production_passes_preparation_facts() -> None:
    """Scenario 5 partial: production must not hardcode allowed_facts=[] when prep has facts."""
    plan = TeachingPlan(
        arc="Distance from speed and time",
        teaching_plan_id="tp-r00-facts",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="Use scoped preparation facts",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent="explain",
                        brief="Explain how to calculate distance from speed and time.",
                        evidence="Learner uses v, t and d equals v times t.",
                    )
                ],
            )
        ],
    )
    policy = default_learn_policy()
    policy["offered_content"] = ["explanation-block"]
    captured: dict[str, object] = {}

    async def spy(*args, **kwargs):
        captured.update(kwargs)
        return await author_learn_work_orders(*args, **kwargs)

    with patch("learn.generation.native_production.author_learn_work_orders", spy):
        build_closed_learn_production(
            teaching_plan=plan,
            policy=policy,
            provider=ContentProvider(),
            preparation_context=LearnPreparationContext(
                objective="Calculate distance from speed and time",
                allowed_facts=PREP_FACTS,
            ),
        )

    assert captured["allowed_facts"] == PREP_FACTS
