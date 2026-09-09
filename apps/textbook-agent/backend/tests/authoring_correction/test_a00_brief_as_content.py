"""A00 regression for Learn assembly copying a planning brief as final content."""

from __future__ import annotations

from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from learn.generation.native_selection import build_learn_selection_snapshot
from learn.generation.ordered_assemble import assemble_ordered_learn_document
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash


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
    _, policy_hash = policy_version_and_hash(default_learn_policy())
    snapshot = build_learn_selection_snapshot(
        plan,
        teaching_plan_hash="hash-a00-brief",
        native_policy_hash=policy_hash,
        package_contract_hash="pkg-a00",
    )

    document = assemble_ordered_learn_document(teaching_plan=plan, snapshot=snapshot)
    block = next(iter(document["blocks"].values()))
    body = str((block.get("content") or {}).get("body") or "")

    assert body
    assert body != brief
    assert "evaporation" in body.lower()
