"""R00 regression: approved-source resolver must not bind positional pool items."""

from __future__ import annotations

import json

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringEngine, AuthoringProviderCall, AuthoringRequest
from learn.generation.authoring_adapter import run_learn_authoring
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.work_orders import compile_learn_work_orders


SENTINEL = "UNRELATED_SOURCE_MUST_NOT_LEAK"


class CaptureEngine(AuthoringEngine):
    captured: AuthoringRequest | None = None

    async def execute(self, request: AuthoringRequest, *, provider=None):
        CaptureEngine.captured = request
        return await super().execute(request, provider=provider)


class ChoiceProvider:
    async def invoke(self, call: AuthoringProviderCall) -> dict[str, object]:
        return {
            "prompt": "Which process turns liquid into vapour?",
            "config": {
                "options": [
                    {"id": "a", "text": "freezing"},
                    {"id": "b", "text": "evaporation"},
                ],
                "correct_option_id": "b",
            },
            "feedback": {
                "correct": "Correct.",
                "incorrect": "Not yet — try again.",
            },
        }


def _pool() -> list[dict[str, object]]:
    return [
        {
            "id": "q1",
            "stem": f"{SENTINEL} unrelated freezing question",
            "options": [{"id": "a", "text": "freezing"}, {"id": "b", "text": "solid"}],
            "correct_key": "a",
        },
        {
            "id": "q2",
            "stem": "What is evaporation?",
            "options": [{"id": "a", "text": "freezing"}, {"id": "b", "text": "liquid to vapour"}],
            "correct_key": "b",
        },
    ]


def _choice_order(*, approved_item_ids: list[str], source_refs: list[str] | None = None) -> object:
    refs = list(source_refs if source_refs is not None else approved_item_ids)
    plan = TeachingPlan(
        arc="Approved source ownership",
        teaching_plan_id="tp-r00-source",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="check",
                specific_purpose="Approved choice conversion",
                blocks=[
                    TeachingPlanBlock(
                        id="b-choice",
                        position=0,
                        intent="check-understanding",
                        brief="Convert the approved evaporation question.",
                        evidence="Learner selects evaporation.",
                        source_question_ids=refs,
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            target="evaporation choice",
                            purpose="Check understanding",
                            expected_evidence="Learner selects evaporation.",
                            difficulty="guided",
                        ),
                    )
                ],
            )
        ],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=1,
        teaching_plan_hash="hash-r00-source",
        native_policy_hash="policy-r00",
        package_contract_hash="pkg-r00",
        decisions=[
            LearnSelectionDecision(
                block_id="b-choice",
                interaction_id="choice",
                source_item_ids=refs,
            )
        ],
    ).seal()
    orders = compile_learn_work_orders(
        teaching_plan=plan,
        snapshot=snapshot,
        approved_items=_pool(),
    )
    order = orders[0]
    if approved_item_ids:
        return order.model_copy(update={"approved_item_ids": approved_item_ids})
    return order.model_copy(update={"approved_item_ids": [], "authoring_mode": "new", "source_refs": []})


@pytest.mark.asyncio
async def test_r00_no_ref_work_order_does_not_bind_first_pool_item() -> None:
    """Scenario 3 partial: source-free work order with nonempty pool stays in generate mode."""
    order = _choice_order(approved_item_ids=[], source_refs=[])
    engine = CaptureEngine(
        registry=__import__(
            "learn.generation.authoring_adapter",
            fromlist=["build_learn_authoring_registry"],
        ).build_learn_authoring_registry(),
        provider=ChoiceProvider(),
    )

    await run_learn_authoring(
        order,
        engine=engine,
        approved_items=_pool(),
        lesson_context={"objective": "Understand evaporation"},
        allowed_facts=["Liquid can become vapour."],
    )
    request = CaptureEngine.captured
    assert request is not None
    assert request.mode == "generate"
    assert request.approved_item is None
    assert request.inputs["approved_items_when_converting"] == []


@pytest.mark.asyncio
async def test_r00_explicit_q2_excludes_q1_sentinel_from_model_visible_inputs() -> None:
    """Scenario 2 partial: explicit q2 reference must not leak q1 into conversion inputs."""
    order = _choice_order(approved_item_ids=["q2"], source_refs=["q2"])
    engine = CaptureEngine(
        registry=__import__(
            "learn.generation.authoring_adapter",
            fromlist=["build_learn_authoring_registry"],
        ).build_learn_authoring_registry(),
        provider=ChoiceProvider(),
    )

    await run_learn_authoring(
        order,
        engine=engine,
        approved_items=_pool(),
    )
    request = CaptureEngine.captured
    assert request is not None
    serialized = json.dumps(request.inputs["approved_items_when_converting"], sort_keys=True)
    assert SENTINEL not in serialized
    assert len(request.inputs["approved_items_when_converting"]) == 1
    assert request.inputs["approved_items_when_converting"][0]["id"] == "q2"
