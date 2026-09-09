"""A00 regression for Learn assembly copying a planning brief as final content."""

from __future__ import annotations

from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringProviderCall
from learn.generation.native_production import build_closed_learn_production
from learn.resources.native_policy import default_learn_policy


class ContentProvider:
    async def invoke(self, call: AuthoringProviderCall) -> dict[str, object]:
        assert call.native_path == "learn"
        if call.capability_id == "callout-block":
            return {
                "variant": "info",
                "body": "Evaporation is when liquid water changes into vapour, like a puddle drying after sunshine.",
            }
        return {
            "body": "Evaporation is when liquid water changes into vapour, like a puddle drying after sunshine.",
            "emphasis": ["evaporation"],
        }


def test_a00_ordered_assemble_does_not_copy_brief_as_content_body() -> None:
    """KNOWN_ANSWER_CASES content-brief: brief is input, not finished prose."""
    brief = "Explain evaporation with an everyday example."
    plan = TeachingPlan(
        arc="A00 content brief",
        teaching_plan_id="tp-a00-brief",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="Explain evaporation",
                blocks=[
                    TeachingPlanBlock(
                        id="b-content",
                        position=0,
                        intent="explain",
                        brief=brief,
                        evidence="Learner reads a complete factual explanation.",
                    )
                ],
            )
        ],
    )
    policy = default_learn_policy()
    policy["offered_content"] = ["explanation-block"]
    production = build_closed_learn_production(
        teaching_plan=plan,
        policy=policy,
        provider=ContentProvider(),
    )
    document = production["document"]
    block = next(iter(document["blocks"].values()))
    body = str((block.get("content") or {}).get("body") or "")

    assert body
    assert body != brief
    assert "evaporation" in body.lower()
