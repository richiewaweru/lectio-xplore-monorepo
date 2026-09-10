"""A04 gates for Learn content and interaction authoring."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from infra.authoring import AuthoringProviderCall
from learn.generation.authoring_adapter import (
    run_learn_authoring,
    run_learn_work_order_authoring,
)
from learn.generation.interaction_writer import (
    InteractionWriterError,
    validate_interaction_contract,
    write_interaction_from_request,
)
from learn.generation.native_production import build_closed_learn_production
from learn.generation.preparation_context import LearnPreparationContext
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.ordered_assemble import assemble_ordered_learn_document, block_component_sequence
from learn.generation.work_orders import LearnWorkOrder
from learn.resources.native_policy import default_learn_policy
from learn.resources.selection import load_learn_writer_view
from learn.runtime.evaluation import evaluate_interaction


CORE_CONFIG: dict[str, dict[str, Any]] = {
    "choice": {
        "options": [{"id": "a", "text": "liquid to solid"}, {"id": "b", "text": "liquid to vapour"}],
        "correct_option_id": "b",
    },
    "multi-select": {
        "options": [{"id": "stone", "text": "stone"}, {"id": "evaporation", "text": "evaporation"}, {"id": "metal", "text": "metal"}, {"id": "condensation", "text": "condensation"}],
        "correct_option_ids": ["evaporation", "condensation"],
    },
    "fill-blank": {"answers": ["chlorophyll"], "blank_ids": ["pigment"], "case_sensitive": False},
    "numeric": {"value": 50, "tolerance": 0, "unit": "m"},
    "short-response": {"evaluation": "teacher-review", "review_guidance": "Explain the condensation."},
    "match-pairs": {"pairs": [{"left": "evaporation", "right": "liquid to vapour"}, {"left": "condensation", "right": "vapour to liquid"}]},
    "classify": {
        "categories": [{"id": "liquid", "label": "liquid"}, {"id": "gas", "label": "gas"}],
        "pairs": [{"left": "rain", "right": "liquid"}, {"left": "water vapour", "right": "gas"}, {"left": "dew", "right": "liquid"}],
    },
    "sequence": {
        "items": [{"id": "egg", "label": "egg"}, {"id": "larva", "label": "larva"}, {"id": "pupa", "label": "pupa"}, {"id": "adult", "label": "adult"}],
        "order": ["egg", "larva", "pupa", "adult"],
    },
}

CONTENT_PAYLOADS: dict[str, dict[str, Any]] = {
    "section-header": {"title": "Evaporation", "subject": "science", "grade_band": "secondary"},
    "hook-hero": {"headline": "Where did the puddle go?", "body": "Sunlight helps water leave the surface as vapour.", "anchor": "evaporation"},
    "explanation-block": {"body": "Evaporation changes liquid water into water vapour at the surface.", "emphasis": ["evaporation"]},
    "definition-card": {"term": "Evaporation", "formal": "A phase change from liquid to gas.", "plain": "Liquid water becomes water vapour."},
    "key-fact": {"fact": "Evaporation changes liquid water into vapour."},
    "callout-block": {"variant": "info", "body": "Evaporation happens at the surface of a liquid."},
    "process-steps": {"title": "Evaporation steps", "steps": [{"number": 1, "action": "Add energy", "detail": "Water molecules gain enough energy to leave the surface."}]},
    "worked-example-card": {"title": "Distance example", "setup": "A cart moves at 5 m/s for 10 s.", "steps": [{"label": "Multiply", "content": "5 x 10 = 50"}], "conclusion": "The distance is 50 m."},
    "summary-block": {"items": [{"text": "Evaporation makes vapour."}]},
    "timeline-block": {"title": "Butterfly cycle", "events": [{"id": "egg", "year": "1", "title": "Egg", "summary": "The cycle begins."}]},
    "diagram-compare": {"before_label": "Liquid", "after_label": "Vapour", "caption": "Water changes state.", "alt_text": "Liquid water compared with water vapour."},
    "quiz-check": {
        "question": "What is evaporation?",
        "options": [{"text": "Liquid to solid", "correct": False, "explanation": "That is freezing."}, {"text": "Liquid to vapour", "correct": True, "explanation": "That is evaporation."}],
        "feedback_correct": "Correct.",
        "feedback_incorrect": "Review evaporation.",
    },
    "fill-in-blank": {"segments": [{"text": "The green pigment is ", "is_blank": False}, {"text": "", "is_blank": True, "answer": "chlorophyll"}]},
}

CORE_GENERATED = CORE_CONFIG


def _interaction_envelope(
    capability_id: str,
    *,
    prompt: str | None = None,
    feedback: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "prompt": prompt or f"Complete this {capability_id.replace('-', ' ')} activity.",
        "config": dict(CORE_CONFIG[capability_id]),
        "feedback": feedback
        or {
            "correct": "Correct.",
            "incorrect": "Not yet — review and try again.",
        },
    }


class CapabilityProvider:
    def __init__(self) -> None:
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> dict[str, Any]:
        self.calls.append(call)
        if call.capability_id in CORE_CONFIG:
            return _interaction_envelope(call.capability_id)
        return dict(CONTENT_PAYLOADS[call.capability_id])


def _request(capability_id: str, *, action: str, approved_items: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "work_order_id": f"a04::{capability_id}",
        "block_id": f"b-{capability_id}",
        "capability_id": capability_id,
        "lane": "interaction",
        "brief": f"Author {capability_id}",
        "intent": "check-understanding",
        "action": action,
        "evidence": "Known-answer regression",
        "teaching_plan_hash": "a04",
        "lesson_context": {"objective": "Known-answer regression objective"},
        "allowed_facts": ["Scoped fact for regression."],
        "terminology": [],
        "approved_items": approved_items or [],
    }


def _writer_card(capability_id: str) -> Mapping[str, Any]:
    return (load_learn_writer_view()["capabilities"])[capability_id]


def _order(capability_id: str, *, lane: str = "content", block_id: str | None = None) -> LearnWorkOrder:
    card = _writer_card(capability_id)
    return LearnWorkOrder(
        work_order_id=f"learn::a04::{block_id or capability_id}::{capability_id}",
        block_id=block_id or capability_id,
        section_id="s-a04",
        lane=lane,  # type: ignore[arg-type]
        capability_id=capability_id,
        teaching_plan_id="tp-a04",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-a04",
        capability_contract_hash=str(card["definition_hash"]),
        expected_output_schema=dict(card["payload_schema"]),
        field_guidance=dict(card.get("field_guidance") or {}),
        authoring_definition=dict(card),
        instructions=card.get("instructions"),
        required_inputs=list(card.get("required_inputs") or []),
        modes=list(card.get("modes") or []),
        validator_refs=list(card.get("validator_refs") or []),
        brief="Write a real payload about evaporation.",
        intent="explain",
        action="read-explanation" if lane == "content" else "select-one",
        evidence="A04 gate evidence",
    )


def test_a04_g01_native_production_authors_content_before_assembly() -> None:
    plan = TeachingPlan(
        arc="Evaporation",
        teaching_plan_id="tp-a04-native",
        revision=1,
        sections=[TeachingPlanSection(slot_id="explain", blocks=[TeachingPlanBlock(id="b1", position=0, intent="explain", brief="Explain evaporation with an everyday example.", evidence="Read explanation")])],
    )
    policy = default_learn_policy()
    policy["offered_content"] = ["explanation-block"]
    provider = CapabilityProvider()

    production = build_closed_learn_production(
        teaching_plan=plan,
        policy=policy,
        provider=provider,
        preparation_context=LearnPreparationContext(
            objective="Explain evaporation",
            allowed_facts=["Liquid water can become vapour through evaporation."],
        ),
    )

    block = next(iter(production["document"]["blocks"].values()))
    assert block["content"]["body"] != "Explain evaporation with an everyday example."
    assert "Evaporation changes liquid water" in block["content"]["body"]
    assert provider.calls and provider.calls[0].capability_id == "explanation-block"


@pytest.mark.parametrize(
    "capability_id,action,approved,response",
    [
        ("choice", "select-one", {"id": "choice-nonfirst", **CORE_GENERATED["choice"], "correct_key": "b", "stem": "What is evaporation?"}, {"selected_option_id": "b"}),
        ("multi-select", "select-many", {"id": "multi-nonleading", "stem": "Which processes involve a phase change?", **CORE_GENERATED["multi-select"], "correct_keys": ["evaporation", "condensation"]}, {"selected_option_ids": ["evaporation", "condensation"]}),
        ("fill-blank", "complete-missing-values", {"id": "fill-pigment", "stem": "The green pigment in leaves is ____.", "answers": ["chlorophyll"]}, {"blanks": ["chlorophyll"]}),
        ("numeric", "enter-number", {"id": "numeric-distance", "stem": "How far does the cart travel?", "value": 50, "unit": "m"}, {"value": 50}),
        ("short-response", "enter-text", {"id": "short-review", "prompt": "Explain why a cold glass develops droplets.", "evaluation": "teacher-review", "review_guidance": "Assess whether the response links a relevant observation to its claim."}, {"text": "Water vapour condenses on the cold glass."}),
        ("match-pairs", "match-pairs", {"id": "match-water", "stem": "Match each process to its description.", "pairs": {"evaporation": "liquid to vapour", "condensation": "vapour to liquid"}}, {"matches": [{"left": "evaporation", "right": "liquid to vapour"}, {"left": "condensation", "right": "vapour to liquid"}]}),
        ("classify", "classify-items", {"id": "classify-water", "stem": "Classify each state of water.", **CORE_GENERATED["classify"], "mapping": {"rain": "liquid", "water vapour": "gas", "dew": "liquid"}}, {"matches": [{"left": "rain", "right": "liquid"}, {"left": "water vapour", "right": "gas"}, {"left": "dew", "right": "liquid"}]}),
        ("sequence", "order-items", {"id": "sequence-butterfly", "stem": "Order the butterfly life stages.", "correct_order": ["egg", "larva", "pupa", "adult"]}, {"order": ["egg", "larva", "pupa", "adult"]}),
    ],
)
def test_a04_g02_g04_core_interactions_convert_and_evaluate(
    capability_id: str,
    action: str,
    approved: Mapping[str, Any],
    response: Mapping[str, Any],
) -> None:
    contract = write_interaction_from_request(
        _request(capability_id, action=action, approved_items=[approved]),
    )

    assert contract["kind"] == capability_id
    assert validate_interaction_contract(contract) == []
    result = evaluate_interaction(contract, response)
    if capability_id == "short-response":
        assert result.outcome == "pending-review"
        assert result.score_earned == 0
    else:
        assert result.outcome == "correct"


@pytest.mark.parametrize("capability_id,action", [
    ("choice", "select-one"),
    ("multi-select", "select-many"),
    ("fill-blank", "complete-missing-values"),
    ("numeric", "enter-number"),
    ("short-response", "enter-text"),
    ("match-pairs", "match-pairs"),
    ("classify", "classify-items"),
    ("sequence", "order-items"),
])
def test_a04_g02_core_interactions_generate_through_provider(capability_id: str, action: str) -> None:
    provider = CapabilityProvider()

    contract = write_interaction_from_request(
        _request(capability_id, action=action),
        provider=provider,
    )

    assert provider.calls[0].capability_id == capability_id
    assert contract["config"] == CORE_CONFIG[capability_id]
    assert contract["prompt"] != "Author " + capability_id
    assert validate_interaction_contract(contract) == []


def test_a04_g03_malformed_approved_keys_fail_without_guessing() -> None:
    bad = {
        "id": "choice-nonfirst",
        "stem": "What is evaporation?",
        "options": [{"id": "a", "text": "liquid to solid"}, {"id": "b", "text": "liquid to vapour"}],
        "correct_key": "z",
    }

    with pytest.raises(InteractionWriterError, match="correct_key"):
        write_interaction_from_request(_request("choice", action="select-one", approved_items=[bad]))


def test_a04_g05_assembly_rejects_missing_results() -> None:
    plan = TeachingPlan(
        arc="Missing authoring",
        teaching_plan_id="tp-a04-missing",
        revision=1,
        sections=[TeachingPlanSection(slot_id="s-a04", blocks=[TeachingPlanBlock(id="b1", position=0, intent="explain", brief="Explain evaporation.", evidence="Read")])],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=1,
        teaching_plan_hash="hash-a04",
        native_policy_hash="policy-a04",
        package_contract_hash="pkg-a04",
        decisions=[LearnSelectionDecision(block_id="b1", content_id="explanation-block")],
    ).seal()

    with pytest.raises(InteractionWriterError, match="MISSING_CONTENT_PAYLOAD"):
        assemble_ordered_learn_document(teaching_plan=plan, snapshot=snapshot)


@pytest.mark.asyncio
async def test_a04_g06_policy_content_schemas_and_ordering_preserved() -> None:
    content_ids = list(default_learn_policy()["offered_content"])
    provider = CapabilityProvider()
    orders = [_order(cid, block_id=f"b{index}") for index, cid in enumerate(content_ids)]
    results = {
        order.work_order_id: await run_learn_work_order_authoring(
            order,
            provider=provider,
            lesson_context={"objective": "Cover all offered content types"},
            allowed_facts=["Scoped fact for content regression."],
        )
        for order in orders
    }
    plan = TeachingPlan(
        arc="All content",
        teaching_plan_id="tp-a04-content",
        revision=1,
        sections=[TeachingPlanSection(slot_id="s-a04", blocks=[TeachingPlanBlock(id=order.block_id, position=index, intent="explain", brief=order.brief, evidence="Read") for index, order in enumerate(orders)])],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=1,
        teaching_plan_hash="hash-a04",
        native_policy_hash="policy-a04",
        package_contract_hash="pkg-a04",
        decisions=[LearnSelectionDecision(block_id=order.block_id, content_id=order.capability_id) for order in orders],
    ).seal()

    document = assemble_ordered_learn_document(
        teaching_plan=plan,
        snapshot=snapshot,
        work_orders=orders,
        authored_results=results,
    )

    assert block_component_sequence(document) == content_ids
    assert {call.capability_id for call in provider.calls} == set(content_ids)


@pytest.mark.asyncio
async def test_a04_payload_strategies_audit_does_not_restore_wide_pipeline() -> None:
    pytest.skip("Phase M: component_lectio payload_strategies deleted")
