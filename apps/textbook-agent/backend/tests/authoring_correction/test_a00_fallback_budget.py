"""A00 regression for fallback content bypassing exhausted budgets."""

from __future__ import annotations

from learn.resources.native_policy import default_learn_policy
from learn.resources.selection import derive_learn_block_candidates


def test_a00_fallback_candidate_stays_excluded_when_budget_exhausted() -> None:
    """Document-primitive fallback must honor per-kind budgets (frozen v2)."""
    policy = default_learn_policy()
    # Empty offered_content → shared document primitives are the content surface.
    policy["offered_content"] = []
    capabilities: list[dict] = []

    derived = derive_learn_block_candidates(
        block_id="b-budget",
        intent="emphasise",
        action=None,
        policy=policy,
        capabilities=capabilities,
        remaining_budgets={
            "paragraph": 0,
            "heading": 0,
            "list": 0,
            "figure": 0,
            "table": 0,
            "callout": 0,
        },
        writer_view={},
    )

    assert derived.content_candidates == ()
    assert derived.excluded.get("paragraph") == "budget_exhausted"
    assert derived.excluded.get("callout") == "budget_exhausted"
