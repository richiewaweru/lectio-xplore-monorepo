"""A00 regression for fallback content bypassing exhausted budgets."""

from __future__ import annotations

from learn.resources.native_policy import default_learn_policy
from learn.resources.selection import derive_learn_block_candidates


def test_a00_fallback_candidate_stays_excluded_when_budget_exhausted() -> None:
    """KNOWN_ANSWER_CASES fallback-budget: candidate budget 0 remains excluded."""
    policy = default_learn_policy()
    policy["offered_content"] = ["explanation-block"]
    policy["offered_interactions"] = []
    capabilities = [
        {
            "id": "explanation-block",
            "kind": "content",
            "availability": "available",
            "supported_intents": ["emphasise"],
            "supported_actions": ["read-explanation"],
            "payload_schema": {"type": "object"},
        }
    ]

    derived = derive_learn_block_candidates(
        block_id="b-budget",
        intent="emphasise",
        action=None,
        policy=policy,
        capabilities=capabilities,
        remaining_budgets={"explanation-block": 0},
        writer_view={
            "explanation-block": {
                "instructions": {"text": "Write explanatory prose."},
                "payload_schema": {"type": "object"},
                "required_inputs": ["brief"],
                "modes": ["generate"],
                "validator_refs": ["learn.payload_schema"],
            }
        },
    )

    assert derived.content_candidates == ()
    assert derived.excluded.get("explanation-block") == "budget_exhausted"
