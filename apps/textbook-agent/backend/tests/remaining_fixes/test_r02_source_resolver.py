"""R02 gates G01–G03: exact approved-source resolution."""

from __future__ import annotations

import json

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringEngine, AuthoringEngineError, AuthoringProviderCall, AuthoringRequest
from learn.generation.authoring_adapter import run_learn_authoring
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.source_resolver import resolve_learn_work_order_sources
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
            "feedback": {"correct": "Correct.", "incorrect": "Not yet."},
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
        teaching_plan_id="tp-r02-source",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="check",
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
                            support_level="guided",
                            evidence="Learner selects evaporation.",
                            source_item_ids=refs,
                        ),
                    )
                ],
            )
        ],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=1,
        teaching_plan_hash="hash-r02-source",
        native_policy_hash="policy-r02",
        package_contract_hash="pkg-r02",
        decisions=[
            LearnSelectionDecision(
                block_id="b-choice",
                interaction_id="choice",
                source_item_ids=refs,
            )
        ],
    ).seal()
    orders = compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot, approved_items=_pool())
    order = orders[0]
    if approved_item_ids:
        return order.model_copy(update={"approved_item_ids": approved_item_ids})
    return order.model_copy(update={"approved_item_ids": [], "authoring_mode": "new", "source_refs": []})


def test_r02_g01_no_ref_work_order_zero_scoped_items() -> None:
    """R02-G01: empty refs → zero scoped items and generate mode."""
    order = _choice_order(approved_item_ids=[], source_refs=[])
    resolved = resolve_learn_work_order_sources(order, _pool())
    assert resolved.ref_ids == ()
    assert resolved.items == ()
    assert resolved.mode == "generate"
    assert resolved.primary_item is None


@pytest.mark.asyncio
async def test_r02_g01_no_implicit_conversion_despite_populated_pool() -> None:
    """R02-G01: provider request stays in generate with empty conversion inputs."""
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
    assert request.inputs["approved_items_when_converting"] == []


@pytest.mark.asyncio
async def test_r02_g02_explicit_q2_only_in_model_visible_inputs() -> None:
    """R02-G02: q2 only in inputs and repair prompt; q1 sentinel absent."""
    order = _choice_order(approved_item_ids=["q2"], source_refs=["q2"])
    engine = CaptureEngine(
        registry=__import__(
            "learn.generation.authoring_adapter",
            fromlist=["build_learn_authoring_registry"],
        ).build_learn_authoring_registry(),
        provider=ChoiceProvider(),
    )
    await run_learn_authoring(order, engine=engine, approved_items=_pool())
    request = CaptureEngine.captured
    assert request is not None
    serialized = json.dumps(request.inputs["approved_items_when_converting"], sort_keys=True)
    assert SENTINEL not in serialized
    assert len(request.inputs["approved_items_when_converting"]) == 1
    assert request.inputs["approved_items_when_converting"][0]["id"] == "q2"
    prompt_blob = json.dumps(request.scoped_request, sort_keys=True)
    assert SENTINEL not in prompt_blob


def test_r02_g03_missing_reference_fails_before_provider() -> None:
    """R02-G03: missing approved id fails at resolution."""
    order = _choice_order(approved_item_ids=["q2"], source_refs=["q2"]).model_copy(
        update={"approved_item_ids": ["missing"], "source_refs": ["missing"]},
    )
    with pytest.raises(AuthoringEngineError, match="missing from pool"):
        resolve_learn_work_order_sources(order, _pool())


def test_r02_g03_duplicate_pool_id_fails_before_provider() -> None:
    """R02-G03: duplicate ambiguous pool ids fail at resolution."""
    order = _choice_order(approved_item_ids=["q1"], source_refs=["q1"])
    pool = [* _pool(), {"id": "q1", "stem": "duplicate", "options": [], "correct_key": "a"}]
    with pytest.raises(AuthoringEngineError, match="duplicate ambiguous"):
        resolve_learn_work_order_sources(order, pool)


def test_r02_g03_multi_source_without_contract_fails() -> None:
    """R02-G03: multi-source rejected for single-source converters."""
    order = _choice_order(approved_item_ids=["q1", "q2"], source_refs=["q1", "q2"])
    with pytest.raises(AuthoringEngineError, match="does not support multi-source"):
        resolve_learn_work_order_sources(order, _pool())
