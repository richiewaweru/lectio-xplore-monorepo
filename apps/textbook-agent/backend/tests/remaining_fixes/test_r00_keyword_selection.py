"""R00 regression: ambiguous Learn content selection must invoke model selector, not keyword rank."""

from __future__ import annotations

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from learn.generation.native_selection import (
    build_learn_selection_snapshot,
    rank_learn_content_candidates,
)
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash


BRIEF = "Summarise the lesson takeaways briefly."
CONTENT_CANDIDATES = ["summary-block", "explanation-block"]
SEMANTIC_WINNER = "explanation-block"
BLOCK_INTENT = "summarise"


def test_r00_ambiguous_shortlist_uses_model_selector_not_keyword_rank() -> None:
    """Scenario 6 partial: misleading lexical rank must not replace configured selector."""
    ranked = rank_learn_content_candidates(
        CONTENT_CANDIDATES,
        brief=BRIEF,
        intent=BLOCK_INTENT,
        action=None,
    )
    assert ranked[0] == "summary-block"
    assert SEMANTIC_WINNER in ranked[1:]

    plan = TeachingPlan(
        arc="Evaporation explanation",
        teaching_plan_id="tp-r00-selection",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="Semantic content choice",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent=BLOCK_INTENT,
                        brief=BRIEF,
                        evidence="Learner reads a causal prose explanation.",
                    )
                ],
            )
        ],
    )
    policy = default_learn_policy()
    policy["offered_content"] = list(CONTENT_CANDIDATES)
    _, policy_hash = policy_version_and_hash(policy)

    snapshot = build_learn_selection_snapshot(
        plan,
        teaching_plan_hash="hash-r00-selection",
        native_policy_hash=policy_hash,
        package_contract_hash="pkg-r00",
        policy=policy,
    )

    assert snapshot.decisions[0].content_id == SEMANTIC_WINNER
