"""Truthful Learn interaction selection modes (Treasure Joe Phase B)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring.capability_selector import CapabilitySelection
from learn.generation.native_production import (
    _legal_interaction_candidates,
    _select_interaction_for_block,
)


def _block(
    *,
    block_id: str = "b1",
    action: str | None = "select-one",
    intent: str = "check-understanding",
) -> TeachingPlanBlock:
    learner = None
    if action is not None:
        learner = LearnerActionBrief(
            action=action,
            target="the taught idea",
            purpose="check understanding",
            expected_evidence="learner responds correctly",
            difficulty="guided",
        )
    return TeachingPlanBlock(
        id=block_id,
        position=0,
        intent=intent,
        brief="Ask the learner to choose the cause.",
        evidence="Learner selects the correct cause",
        learner_action=learner,
    )


@pytest.mark.asyncio
async def test_single_candidate_is_deterministic_without_llm() -> None:
    block = _block(action="select-one")
    choose = AsyncMock(
        side_effect=AssertionError("LLM must not be called for one candidate")
    )
    kind, mode = await _select_interaction_for_block(
        block,
        candidates_by_block={"b1": ["choice"]},
        choose=choose,
    )
    assert kind == "choice"
    assert mode == "deterministic_single"
    choose.assert_not_called()


@pytest.mark.asyncio
async def test_yaml_default_without_shortlist_is_policy_default() -> None:
    block = _block(action="select-one")

    def _empty_legal(*_a, **_k):
        return []

    with patch(
        "learn.generation.native_production._legal_interaction_candidates",
        side_effect=_empty_legal,
    ):
        kind, mode = await _select_interaction_for_block(
            block,
            candidates_by_block=None,
            choose=AsyncMock(side_effect=AssertionError("no LLM")),
        )
    assert kind == "choice"
    assert mode == "policy_default"


@pytest.mark.asyncio
async def test_multi_candidate_uses_bounded_llm_and_validates() -> None:
    block = _block(action="enter-text")
    calls: list[dict] = []

    async def choose(context: dict) -> CapabilitySelection:
        calls.append(context)
        return CapabilitySelection(capability_id="short-response", reason="test")

    kind, mode = await _select_interaction_for_block(
        block,
        candidates_by_block={"b1": ["short-response", "numeric"]},
        choose=choose,
    )
    assert kind == "short-response"
    assert mode == "llm_multi_candidate"
    assert calls, "expected LLM choose invocation"


@pytest.mark.asyncio
async def test_multi_candidate_rejects_illegal_pick() -> None:
    block = _block(action="enter-text")

    async def choose(_context: dict) -> CapabilitySelection:
        return CapabilitySelection(capability_id="choice", reason="illegal")

    with pytest.raises(Exception):
        await _select_interaction_for_block(
            block,
            candidates_by_block={"b1": ["short-response", "numeric"]},
            choose=choose,
        )


@pytest.mark.asyncio
async def test_interaction_selection_prompt_not_loaded_for_single_candidate() -> None:
    block = _block(action="order-items")
    with patch(
        "core.prompts.loader.effective_prompt_text",
        side_effect=AssertionError("must not load interaction-selection for hashing"),
    ):
        kind, mode = await _select_interaction_for_block(
            block,
            candidates_by_block={"b1": ["sequence"]},
        )
    assert kind == "sequence"
    assert mode == "deterministic_single"


def test_yaml_candidates_used_when_runtime_shortlist_absent() -> None:
    block = _block(action="select-many")
    legal = _legal_interaction_candidates(block, candidates_by_block=None)
    assert legal == ["multi-select"]
