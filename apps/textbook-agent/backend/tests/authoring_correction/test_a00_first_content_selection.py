"""A00 regression for Learn content selection using content_candidates[0]."""

from __future__ import annotations

from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from learn.generation.native_selection import build_learn_selection_snapshot
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash


def test_a00_explain_content_selection_is_semantic_not_first_candidate() -> None:
    """An explanatory brief should select explanation content, not tuple index 0."""
    plan = TeachingPlan(
        arc="A00 content selection",
        teaching_plan_id="tp-a00-content-selection",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="Explain condensation",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent="explain",
                        brief="Explain condensation in clear causal prose.",
                        evidence="Learner can explain why droplets form.",
                    )
                ],
            )
        ],
    )
    _, policy_hash = policy_version_and_hash(default_learn_policy())

    snapshot = build_learn_selection_snapshot(
        plan,
        teaching_plan_hash="hash-a00-content-selection",
        native_policy_hash=policy_hash,
        package_contract_hash="pkg-a00",
    )

    decision = snapshot.decisions[0]
    assert snapshot.candidate_map["b-explain"]["content"][0] == "callout-block"
    assert "explanation-block" in snapshot.candidate_map["b-explain"]["content"]
    assert decision.content_id == "explanation-block"
