"""A05 gates for semantic selection and honest fallbacks."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from curriculum.teaching_plan.compatibility import ActionSourceIncompatibleError
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from learn.generation.native_selection import (
    LearnSelectionDecision,
    SelectionError as LearnSelectionError,
    build_learn_selection_snapshot,
    rank_learn_content_candidates,
    rank_learn_interaction_candidates,
    select_learn_deterministically,
    select_learn_first_legal,
    validate_learn_selection,
)
from learn.generation.work_orders import compile_learn_work_orders
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash
from learn.resources.selection import derive_learn_block_candidates
from print.generation.native_production import teaching_plan_content_hash
from print.generation.selection_snapshot import (
    PrintSelectionDecision,
    SelectionError as PrintSelectionError,
    build_print_selection_snapshot,
    rank_print_form_candidates,
    select_print_deterministically,
    select_print_first_legal,
    validate_print_selection,
)
from print.resources.native_policy import default_print_policy, policy_version_and_hash
from print.resources.selection import build_print_candidate_map


def _block(
    block_id: str,
    *,
    intent: str,
    brief: str,
    action: str | None = None,
    source_question_ids: list[str] | None = None,
    position: int = 0,
) -> TeachingPlanBlock:
    learner = None
    if action is not None:
        learner = LearnerActionBrief(
            action=action,
            support_level="guided",
            evidence="Evidence",
            source_item_ids=list(source_question_ids or []),
        )
    return TeachingPlanBlock(
        id=block_id,
        position=position,
        intent=intent,
        brief=brief,
        evidence="Evidence",
        source_question_ids=list(source_question_ids or []),
        learner_action=learner,
    )


def _plan(*blocks: TeachingPlanBlock, plan_id: str = "tp-a05", revision: int = 1) -> TeachingPlan:
    return TeachingPlan(
        arc="A05 selection",
        teaching_plan_id=plan_id,
        revision=revision,
        sections=[
            TeachingPlanSection(
                slot_id="main",
                specific_purpose="selection fixture",
                blocks=list(blocks),
            )
        ],
    )


def test_a05_g01_semantic_selector_and_sole_candidate() -> None:
    """Multiple eligible options use configured selector; sole candidate stays deterministic."""
    plan = _plan(
        _block(
            "b-explain",
            intent="explain",
            brief="Explain condensation in clear causal prose.",
        )
    )
    _, policy_hash = policy_version_and_hash(default_learn_policy())
    snapshot = build_learn_selection_snapshot(
        plan,
        teaching_plan_hash="hash-a05-g01",
        native_policy_hash=policy_hash,
        package_contract_hash="pkg-a05",
    )
    decision = snapshot.decisions[0]
    assert "explanation-block" in snapshot.candidate_map["b-explain"]["content"]
    assert decision.content_id == "explanation-block"

    ranked = rank_learn_content_candidates(
        snapshot.candidate_map["b-explain"]["content"],
        brief="Explain condensation in clear causal prose.",
        intent="explain",
        action=None,
    )
    assert ranked[0] == "explanation-block"

    sole_policy = default_learn_policy()
    sole_policy["offered_content"] = ["summary-block"]
    sole_policy["offered_interactions"] = []
    sole_plan = _plan(
        _block("b-sole", intent="summarise", brief="Summarise the lesson takeaways.")
    )
    sole_candidates_map, sole_decisions = select_learn_first_legal(sole_plan, policy=sole_policy)
    assert sole_candidates_map["b-sole"].content_candidates == ("summary-block",)
    assert sole_decisions[0].content_id == "summary-block"


def test_a05_g02_out_of_set_rejected_and_reorder_invariant() -> None:
    """Invalid selections fail; reordering the shortlist does not change semantic choice."""
    block = _block("b1", intent="explain", brief="Explain evaporation with causal prose.")
    plan = _plan(block)
    candidates = derive_learn_block_candidates(
        block_id=block.id,
        intent=block.intent,
        action=None,
    )
    legal = list(candidates.content_candidates)
    assert legal

    with pytest.raises(LearnSelectionError) as caught:
        validate_learn_selection(
            teaching_plan=plan,
            decisions=[
                LearnSelectionDecision(
                    block_id="b1",
                    content_id="NOT_IN_SHORTLIST",
                    interaction_id=None,
                )
            ],
            candidate_map={block.id: candidates},
        )
    assert caught.value.code == "OUT_OF_SET"

    reordered = list(reversed(legal))
    ranked_original = rank_learn_content_candidates(
        legal,
        brief=block.brief,
        intent=block.intent,
        action=None,
    )
    ranked_reordered = rank_learn_content_candidates(
        reordered,
        brief=block.brief,
        intent=block.intent,
        action=None,
    )
    assert ranked_original[0] == ranked_reordered[0]
    assert ranked_original[0] != legal[0] or len(legal) == 1

    print_candidates = {"b1": ("aside", "prose", "list")}
    first_legal = select_print_first_legal(plan, candidate_map=print_candidates)
    semantic = select_print_deterministically(plan, candidate_map=print_candidates)
    assert first_legal[0].form_id == "aside"
    assert semantic[0].form_id != first_legal[0].form_id
    assert semantic[0].form_id in print_candidates["b1"]


def test_a05_g03_required_interactions_persist_optional_explicit_none() -> None:
    """Required response keeps an interaction; passive blocks keep interaction=none."""
    required = _plan(
        _block(
            "b-seq",
            intent="sequence",
            brief="Put the stages in order",
            action="order-items",
        )
    )
    _, decisions = select_learn_deterministically(required)
    assert decisions[0].interaction_id == "sequence"

    passive = _plan(
        _block(
            "b-read",
            intent="explain",
            brief="Read the explanation",
            action="read-explanation",
        )
    )
    policy = default_learn_policy()
    policy["offered_interactions"] = []
    _, passive_decisions = select_learn_deterministically(passive, policy=policy)
    assert passive_decisions[0].interaction_id is None
    assert passive_decisions[0].content_id is not None


def test_a05_g04_fallback_cannot_restore_excluded_candidates() -> None:
    """Budget/readiness exclusions stay excluded; no semantic fallback map restores them."""
    policy = default_learn_policy()
    policy["offered_content"] = ["explanation-block"]
    policy["offered_interactions"] = []
    derived = derive_learn_block_candidates(
        block_id="b-budget",
        intent="emphasise",
        action=None,
        policy=policy,
        capabilities=[
            {
                "id": "explanation-block",
                "kind": "content",
                "availability": "available",
                "supported_intents": ["emphasise"],
                "supported_actions": ["read-explanation"],
                "payload_schema": {"type": "object"},
            }
        ],
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

    not_ready = derive_learn_block_candidates(
        block_id="b-ready",
        intent="check-understanding",
        action="select-one",
        policy=default_learn_policy(),
        capabilities=[
            {
                "id": "choice",
                "kind": "interaction",
                "availability": "available",
                "readiness": "planned",
                "supported_intents": ["check-understanding"],
                "supported_actions": ["select-one"],
                "payload_schema": {"type": "object"},
            }
        ],
        writer_view={"choice": {"payload_schema": {"type": "object"}}},
    )
    assert "choice" not in not_ready.interaction_candidates
    assert not_ready.excluded.get("choice") == "not_generation_ready"


def test_a05_g05_missing_source_fails_at_owning_stage() -> None:
    """Incompatible approved sources fail explicitly; order-items keeps empty sources."""
    block = _block(
        "b-mcq",
        intent="check-understanding",
        brief="Order the items",
        action="order-items",
        source_question_ids=["item-mcq-1"],
    )
    plan = _plan(block)
    candidates = derive_learn_block_candidates(
        block_id=block.id,
        intent=block.intent,
        action="order-items",
    )
    interaction = candidates.interaction_candidates[0]
    decision = LearnSelectionDecision(
        block_id=block.id,
        content_id=candidates.content_candidates[0] if candidates.content_candidates else None,
        interaction_id=interaction,
        source_item_ids=["item-mcq-1"],
    )
    from learn.generation.native_selection import LearnSelectionSnapshot, candidate_map_payload

    snap = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id or "",
        teaching_plan_revision=plan.revision or 1,
        teaching_plan_hash="h",
        native_policy_hash="p",
        package_contract_hash="c",
        candidate_map=candidate_map_payload({block.id: candidates}),
        decisions=[decision],
    ).seal()
    mcq = SimpleNamespace(id="item-mcq-1", options=({"key": "A", "text": "x"},), stem="Stem")
    with pytest.raises(ActionSourceIncompatibleError):
        compile_learn_work_orders(teaching_plan=plan, snapshot=snap, approved_items=[mcq])

    order_block = _block(
        "b-new-order",
        intent="sequence",
        brief="Order the lifecycle stages",
        action="order-items",
    )
    _, order_decisions = select_learn_deterministically(_plan(order_block))
    assert order_decisions[0].source_item_ids == []


def test_a05_g06_shared_teaching_revision_across_paths() -> None:
    """Print and Learn production reference the same approved teaching revision/hash."""
    block = _block(
        "b-shared",
        intent="explain",
        brief="Explain why plants need light.",
        action="read-explanation",
    )
    plan = _plan(block, plan_id="tp-shared", revision=3)
    plan_hash = teaching_plan_content_hash(plan)

    _, learn_hash = policy_version_and_hash(default_learn_policy())
    learn_snapshot = build_learn_selection_snapshot(
        plan,
        teaching_plan_hash=plan_hash,
        native_policy_hash=learn_hash,
        package_contract_hash="pkg-learn-a05",
    )
    assert learn_snapshot.teaching_plan_id == "tp-shared"
    assert learn_snapshot.teaching_plan_revision == 3
    assert learn_snapshot.teaching_plan_hash == plan_hash

    print_candidates = build_print_candidate_map(
        plan,
        compatible_objects_by_intent={"explain": ("prose", "list", "aside")},
    )
    _, print_hash = policy_version_and_hash(default_print_policy())
    print_snapshot = build_print_selection_snapshot(
        plan,
        candidate_map=print_candidates,
        teaching_plan_hash=plan_hash,
        native_policy_hash=print_hash,
        package_contract_hash="pkg-page-a05",
    )
    assert print_snapshot.teaching_plan_id == "tp-shared"
    assert print_snapshot.teaching_plan_revision == 3
    assert print_snapshot.teaching_plan_hash == plan_hash

    with pytest.raises(PrintSelectionError):
        validate_print_selection(
            teaching_plan=plan,
            decisions=[PrintSelectionDecision(block_id="b-shared", form_id="figure")],
            candidate_map=print_candidates,
        )
