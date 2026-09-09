"""R03 Learn gates: model selector for ambiguous shortlists."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring.capability_selector import (
    CapabilitySelection,
    CapabilitySelectionError,
)
from learn.generation.native_production import build_closed_learn_production_async
from learn.generation.native_selection import (
    build_learn_selection_snapshot,
    build_learn_selection_snapshot_async,
    rank_learn_content_candidates,
    select_learn_with_model_async,
)
from learn.generation.preparation_context import LearnPreparationContext
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash
from learn.resources.selection import LearnBlockCandidates


BRIEF = "Summarise the lesson takeaways briefly."
CONTENT_CANDIDATES = ["summary-block", "explanation-block"]
SEMANTIC_WINNER = "explanation-block"


def _ambiguous_content_candidates(plan: TeachingPlan) -> dict[str, LearnBlockCandidates]:
    rows: dict[str, LearnBlockCandidates] = {}
    for section in plan.sections:
        for block in section.blocks:
            if block.learner_action is None:
                rows[block.id] = LearnBlockCandidates(
                    block_id=block.id,
                    intent=block.intent,
                    action=None,
                    content_candidates=tuple(CONTENT_CANDIDATES),
                    interaction_candidates=(),
                    excluded={},
                    requires_response=False,
                    interaction_optional=True,
                )
            else:
                rows[block.id] = LearnBlockCandidates(
                    block_id=block.id,
                    intent=block.intent,
                    action=block.learner_action.action,
                    content_candidates=(),
                    interaction_candidates=("sequence", "choice"),
                    excluded={},
                    requires_response=True,
                    interaction_optional=False,
                )
    return rows


class RecordingChoose:
    def __init__(self, responses: list[str | CapabilitySelection]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def __call__(self, context: dict) -> CapabilitySelection:
        self.calls.append(context)
        raw = self.responses.pop(0)
        if isinstance(raw, CapabilitySelection):
            return raw
        return CapabilitySelection(capability_id=raw, reason="mock selection")


def _summarise_plan(*, interaction: bool = False) -> TeachingPlan:
    learner = None
    if interaction:
        learner = LearnerActionBrief(
            action="choose-one",
            support_level="guided",
            evidence="Pick the best summary.",
            source_item_ids=["q1"],
        )
    return TeachingPlan(
        arc="Evaporation explanation",
        teaching_plan_id="tp-r03-learn",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="Semantic content choice",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent="summarise",
                        brief=BRIEF,
                        evidence="Learner reads a causal prose explanation.",
                        learner_action=learner,
                    )
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_r03_g01_ambiguous_learn_invokes_selector_through_production() -> None:
    """R03-G01: content and interaction shortlists invoke configured selector."""
    content_block = TeachingPlanBlock(
        id="b-content",
        position=0,
        intent="summarise",
        brief=BRIEF,
        evidence="Content surface",
    )
    interaction_block = TeachingPlanBlock(
        id="b-interact",
        position=1,
        intent="sequence",
        brief="Put the stages in order.",
        evidence="Order evidence",
        learner_action=LearnerActionBrief(
            action="order-items",
            support_level="guided",
            evidence="Order the stages.",
            source_item_ids=[],
        ),
    )
    plan = TeachingPlan(
        arc="R03 learn selection",
        teaching_plan_id="tp-r03-g01",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="apply",
                specific_purpose="content and interaction",
                blocks=[content_block, interaction_block],
            )
        ],
    )
    policy = default_learn_policy()
    policy["offered_content"] = list(CONTENT_CANDIDATES)
    policy["offered_interactions"] = ["sequence", "choice"]
    choose = RecordingChoose([SEMANTIC_WINNER, "sequence"])

    with (
        patch(
            "learn.generation.native_selection.build_learn_candidate_map",
            return_value=_ambiguous_content_candidates(plan),
        ),
        patch(
            "learn.generation.native_production.author_learn_work_orders",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "learn.generation.native_production.assemble_ordered_learn_document",
            return_value={"blocks": {}, "sections": []},
        ),
    ):
        production = await build_closed_learn_production_async(
            teaching_plan=plan,
            policy=policy,
            preparation_context=LearnPreparationContext(objective=plan.arc or "Objective"),
            choose=choose,
        )
    snapshot = production["selection_snapshot"]
    by_block = {item.block_id: item for item in snapshot.decisions}
    assert by_block["b-content"].content_id == SEMANTIC_WINNER
    assert by_block["b-interact"].interaction_id == "sequence"
    assert len(choose.calls) == 2
    lanes = {call["lane"] for call in choose.calls}
    assert lanes == {"content", "interaction"}
    for call in choose.calls:
        assert "eligible_candidates" in call


@pytest.mark.asyncio
async def test_r03_g03_nonfirst_lexically_disfavored_honored_sole_skips_call() -> None:
    """R03-G03: production honors legal nonfirst ID; sole candidate skips selector."""
    ranked = rank_learn_content_candidates(
        CONTENT_CANDIDATES,
        brief=BRIEF,
        intent="summarise",
        action=None,
    )
    assert ranked[0] == "summary-block"
    assert SEMANTIC_WINNER in ranked[1:]

    plan = _summarise_plan()
    policy = default_learn_policy()
    policy["offered_content"] = list(CONTENT_CANDIDATES)
    choose = RecordingChoose([SEMANTIC_WINNER])
    _, policy_hash = policy_version_and_hash(policy)

    with patch(
        "learn.generation.native_selection.build_learn_candidate_map",
        return_value=_ambiguous_content_candidates(plan),
    ):
        snapshot = await build_learn_selection_snapshot_async(
            plan,
            teaching_plan_hash="hash-r03-g03",
            native_policy_hash=policy_hash,
            package_contract_hash="pkg-r03",
            policy=policy,
            choose=choose,
        )
    assert snapshot.decisions[0].content_id == SEMANTIC_WINNER
    assert len(choose.calls) == 1

    sole_policy = default_learn_policy()
    sole_policy["offered_content"] = ["summary-block"]
    sole_plan = TeachingPlan(
        arc="Sole",
        teaching_plan_id="tp-sole",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="wrap",
                specific_purpose="sole",
                blocks=[
                    TeachingPlanBlock(
                        id="b-sole",
                        position=0,
                        intent="summarise",
                        brief="Summarise.",
                        evidence="Evidence",
                    )
                ],
            )
        ],
    )
    sole_choose = RecordingChoose([])
    await build_learn_selection_snapshot_async(
        sole_plan,
        teaching_plan_hash="hash-sole",
        native_policy_hash=policy_hash,
        package_contract_hash="pkg-r03",
        policy=sole_policy,
        choose=sole_choose,
    )
    assert sole_choose.calls == []


@pytest.mark.asyncio
async def test_r03_g04_invalid_id_repair_then_exhaust_no_keyword_fallback() -> None:
    """R03-G04: bounded repair on same shortlist; exhaustion is typed; no keyword rank."""
    plan = _summarise_plan()
    policy = default_learn_policy()
    policy["offered_content"] = list(CONTENT_CANDIDATES)

    always_bad = RecordingChoose(["not-in-shortlist", "still-invalid"])
    with (
        patch(
            "learn.generation.native_selection.build_learn_candidate_map",
            return_value=_ambiguous_content_candidates(plan),
        ),
        pytest.raises(CapabilitySelectionError) as exc,
    ):
        await select_learn_with_model_async(plan, policy=policy, choose=always_bad)
    assert exc.value.code == "SELECTOR_EXHAUSTED"
    assert len(always_bad.calls) == 2

    repair_ok = RecordingChoose(["bogus-id", SEMANTIC_WINNER])
    with patch(
        "learn.generation.native_selection.build_learn_candidate_map",
        return_value=_ambiguous_content_candidates(plan),
    ):
        candidates, decisions = await select_learn_with_model_async(
            plan, policy=policy, choose=repair_ok
        )
    assert decisions[0].content_id == SEMANTIC_WINNER
    assert len(repair_ok.calls) == 2
    assert candidates["b-explain"].content_candidates == tuple(CONTENT_CANDIDATES)


@pytest.mark.asyncio
async def test_r03_g05_candidate_order_permutation_no_production_keyword_bonuses() -> None:
    """R03-G05: permuted shortlist order does not change closed-set semantics."""
    plan = _summarise_plan()
    policy = default_learn_policy()
    permuted = ["explanation-block", "summary-block"]
    policy["offered_content"] = permuted
    choose = RecordingChoose(["summary-block"])
    with patch(
        "learn.generation.native_selection.build_learn_candidate_map",
        return_value=_ambiguous_content_candidates(plan),
    ):
        _, decisions = await select_learn_with_model_async(plan, policy=policy, choose=choose)
    assert decisions[0].content_id == "summary-block"

    src_root = Path(__file__).resolve().parents[2] / "src"
    learn_selection = (src_root / "learn" / "generation" / "native_selection.py").read_text(
        encoding="utf-8"
    )
    learn_prod = (src_root / "learn" / "generation" / "native_production.py").read_text(
        encoding="utf-8"
    )
    print_selection = (src_root / "print" / "generation" / "selection_snapshot.py").read_text(
        encoding="utf-8"
    )
    learn_prod_section = learn_selection.split("async def select_learn_with_model_async")[1].split(
        "async def build_learn_selection_snapshot_async"
    )[0]
    print_prod_section = print_selection.split("async def select_print_with_model_async")[1].split(
        "async def build_print_selection_snapshot_async"
    )[0]
    assert "rank_learn_content_candidates(" not in learn_prod_section
    assert "rank_learn_interaction_candidates(" not in learn_prod_section
    assert "intent_bonus" not in learn_prod_section
    assert "rank_learn" not in learn_prod
    assert "rank_print_form_candidates(" not in print_prod_section
    assert "prefer_figure_for_visual_slots" not in (
        src_root / "print" / "generation" / "native_production.py"
    ).read_text(encoding="utf-8")


def test_r00_keyword_selection_passes_with_configured_selector() -> None:
    """R00 regression: keyword rank must not pick production winner."""
    ranked = rank_learn_content_candidates(
        CONTENT_CANDIDATES,
        brief=BRIEF,
        intent="summarise",
        action=None,
    )
    assert ranked[0] == "summary-block"

    plan = _summarise_plan()
    policy = default_learn_policy()
    policy["offered_content"] = list(CONTENT_CANDIDATES)
    _, policy_hash = policy_version_and_hash(policy)
    choose = RecordingChoose([SEMANTIC_WINNER])

    with patch(
        "learn.generation.native_selection.build_learn_candidate_map",
        return_value=_ambiguous_content_candidates(plan),
    ):
        snapshot = build_learn_selection_snapshot(
            plan,
            teaching_plan_hash="hash-r00-selection",
            native_policy_hash=policy_hash,
            package_contract_hash="pkg-r00",
            policy=policy,
            choose=choose,
        )
    assert snapshot.decisions[0].content_id == SEMANTIC_WINNER
    assert len(choose.calls) == 1
