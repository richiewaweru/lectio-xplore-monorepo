"""Policy cleanup v4 — knowledge and assessment policy gates (G02–G17 core)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from infra.authoring import AuthoringEngineError, AuthoringProviderCall
from infra.authoring.policy_resolver import (
    LEGACY_ABSENT_VERSION,
    POLICY_VERSION,
    resolve_authoring_policy,
    with_assessment_fallback,
)
from learn.generation.authoring_adapter import (
    build_learn_authoring_registry,
    run_learn_authoring,
)
from learn.generation.interaction_writer import write_interaction_from_request
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.preparation_context import learn_preparation_context_from_state
from learn.generation.work_orders import compile_learn_work_orders
from learn.runtime.evaluation import evaluate_interaction
from learn.resources.selection import load_learn_writer_view


EVAP_FACT = (
    "Evaporation changes liquid water into water vapour and can occur below boiling point."
)


class CaptureProvider:
    def __init__(self) -> None:
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> dict[str, Any]:
        self.calls.append(call)
        if call.capability_id == "explanation-block":
            return {
                "body": "Evaporation turns liquid water into vapour.",
                "emphasis": ["evaporation"],
            }
        if call.capability_id == "short-response":
            return {
                "prompt": "What is the green pigment in leaves?",
                "config": {
                    "evaluation": "accepted-answers",
                    "accepted_answers": ["chlorophyll"],
                    "case_sensitive": False,
                },
                "feedback": {"correct": "Yes.", "incorrect": "Not yet."},
            }
        return {"variant": "info", "body": "Scoped content."}


def _explain_order(*, knowledge_override: dict[str, Any] | None = None):
    plan = TeachingPlan(
        arc="Explain evaporation",
        teaching_plan_id="tp-policy-evap",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent="explain",
                        brief="Explain evaporation.",
                        evidence="Learner explains evaporation.",
                    )
                ],
            )
        ],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=1,
        teaching_plan_hash="hash-policy",
        native_policy_hash="policy-hash",
        package_contract_hash="pkg-hash",
        decisions=[LearnSelectionDecision(block_id="b-explain", content_id="explanation-block")],
    ).seal()
    order = compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)[0]
    if knowledge_override:
        definition = dict(order.authoring_definition or {})
        definition["knowledge"] = knowledge_override
        order = order.model_copy(update={"authoring_definition": definition})
    return order


def _short_request(
    *,
    approved: dict[str, Any],
    requested_assessment_policy: str | None = None,
) -> dict[str, Any]:
    from tests.authoring_correction.test_a04_learn_authoring import _request

    req = _request("short-response", action="enter-text", approved_items=[approved])
    if requested_assessment_policy:
        req["requested_assessment_policy"] = requested_assessment_policy
    return req


@pytest.mark.asyncio
async def test_g13_approved_short_response_preserves_answers() -> None:
    contract = write_interaction_from_request(
        _short_request(
            approved={
                "id": "q-chloro",
                "stem": "What is the green pigment in leaves?",
                "accepted_answers": ["chlorophyll"],
                "case_sensitive": False,
            }
        )
    )
    assert contract["prompt"] == "What is the green pigment in leaves?"
    assert contract["config"]["evaluation"] == "accepted-answers"
    assert contract["config"]["accepted_answers"] == ["chlorophyll"]
    assert contract["config"]["case_sensitive"] is False
    ok = evaluate_interaction(contract, {"text": "Chlorophyll"})
    assert ok.outcome == "correct"
    bad = evaluate_interaction(contract, {"text": "xanthophyll"})
    assert bad.outcome == "incorrect"


@pytest.mark.asyncio
async def test_g14_automatic_required_missing_answer_fails() -> None:
    with pytest.raises(Exception, match="INCOMPATIBLE_APPROVED_ITEM|automatic_required|accepted answers"):
        write_interaction_from_request(
            _short_request(
                approved={
                    "id": "q-chloro",
                    "stem": "What is the green pigment in leaves?",
                    "review_guidance": "Should not matter",
                },
                requested_assessment_policy="automatic_required",
            )
        )


@pytest.mark.asyncio
async def test_g15_explicit_teacher_review() -> None:
    contract = write_interaction_from_request(
        _short_request(
            approved={
                "id": "q-chloro",
                "stem": "Explain how the evidence supports your conclusion.",
                "evaluation": "teacher-review",
                "review_guidance": (
                    "Assess whether the response links a relevant observation to its claim."
                ),
            },
            requested_assessment_policy="teacher_review",
        )
    )
    assert contract["config"]["evaluation"] == "teacher-review"
    assert "accepted_answers" not in contract["config"]
    assert "links a relevant observation" in contract["config"]["review_guidance"]
    result = evaluate_interaction(contract, {"text": "Because the glass is cold."})
    assert result.outcome == "pending-review"


@pytest.mark.asyncio
async def test_g16_automatic_preferred_fallback_records_reason() -> None:
    contract = write_interaction_from_request(
        _short_request(
            approved={
                "id": "q-chloro",
                "stem": "What is the green pigment in leaves?",
                "review_guidance": "Look for the pigment name chlorophyll.",
            }
        )
    )
    assert contract["config"]["evaluation"] == "teacher-review"
    assert (
        contract.get("provenance", {}).get("policy", {}).get("fallback_reason")
        == "missing_accepted_answers_automatic_preferred"
    )


def test_g02_package_default_knowledge_on_writer_view() -> None:
    view = load_learn_writer_view()
    card = view["capabilities"]["explanation-block"]
    assert card["knowledge"]["default"] == "supplied_preferred"
    assert "supplied_only" in card["knowledge"]["supported"]
    sr = view["capabilities"]["short-response"]
    assert sr["assessment"]["default"] == "automatic_preferred"
    assert sr["assessment"]["teacher_review_permitted"] is True


def test_g02_changing_exported_default_changes_resolution() -> None:
    decision = resolve_authoring_policy(
        capability_id="explanation-block",
        native_path="learn",
        modes=["generate"],
        authoring_mode="generate",
        raw_definition={
            "knowledge": {
                "default": "supplied_only",
                "supported": ["supplied_only", "supplied_preferred"],
            }
        },
        allowed_facts=[],
    )
    assert decision.effective_knowledge_policy == "supplied_only"
    assert decision.knowledge_policy_source.startswith("package:")


def test_g03_explicit_overrides_and_conflicts() -> None:
    ok = resolve_authoring_policy(
        capability_id="explanation-block",
        native_path="learn",
        modes=["generate"],
        authoring_mode="generate",
        requested_knowledge_policy="supplied_only",
        allowed_facts=[EVAP_FACT],
    )
    assert ok.effective_knowledge_policy == "supplied_only"
    assert ok.knowledge_policy_source == "task"

    with pytest.raises(AuthoringEngineError, match="POLICY_CONFLICT"):
        resolve_authoring_policy(
            capability_id="choice",
            native_path="learn",
            modes=["generate", "convert-approved"],
            authoring_mode="convert-approved",
            requested_assessment_policy="teacher_review",
            raw_definition={
                "assessment": {
                    "default": "automatic_required",
                    "supported": ["automatic_required"],
                    "teacher_review_permitted": False,
                }
            },
        )

    with pytest.raises(AuthoringEngineError, match="POLICY_CONFLICT"):
        resolve_authoring_policy(
            capability_id="short-response",
            native_path="learn",
            modes=["generate", "convert-approved"],
            authoring_mode="convert-approved",
            requested_assessment_policy="automatic_required",
            approved_item_assessment="teacher_review",
        )


def test_g04_definition_hash_includes_knowledge() -> None:
    view = load_learn_writer_view()
    card = view["capabilities"]["explanation-block"]
    assert card.get("definition_hash")
    assert card.get("definition_version")
    assert "knowledge" in card


def test_g05_legacy_absent_is_deterministic() -> None:
    decision = resolve_authoring_policy(
        capability_id="short-response",
        native_path="learn",
        modes=["generate", "convert-approved"],
        authoring_mode="generate",
        legacy_absent=True,
        allowed_facts=[],
    )
    assert decision.knowledge_policy_source == LEGACY_ABSENT_VERSION
    assert decision.assessment_policy_source == LEGACY_ABSENT_VERSION
    assert decision.input_availability == "legacy_unknown"


def test_g09_objective_never_becomes_fact() -> None:
    prep = learn_preparation_context_from_state(
        {
            "shared_preparation_packet": {
                "objective": "Explain evaporation",
                "title": "Evaporation lesson",
                "prior_established": [],
                "must_establish": [],
            },
            "teaching_plan": {"arc": "Water cycle arc"},
        }
    )
    assert prep.objective == "Explain evaporation"
    assert prep.allowed_facts == []
    assert prep.input_availability == "intentionally_absent"
    assert "Explain evaporation" not in prep.allowed_facts
    assert "Water cycle arc" not in prep.allowed_facts


def test_g09_real_statement_and_id_not_as_fact() -> None:
    prep = learn_preparation_context_from_state(
        {
            "shared_preparation_packet": {
                "objective": "Explain evaporation",
                "must_establish": [{"id": "fact-evap-1", "statement": EVAP_FACT}],
            }
        }
    )
    assert prep.allowed_facts == [EVAP_FACT]
    assert "fact-evap-1" not in prep.allowed_facts
    assert prep.referenced_fact_ids == ["fact-evap-1"]


def test_g08_unresolved_fact_id() -> None:
    prep = learn_preparation_context_from_state(
        {
            "shared_preparation_packet": {
                "objective": "Explain evaporation",
                "must_establish": [{"id": "fact-evap-1"}],
            }
        }
    )
    assert prep.unresolved_fact_ids == ["fact-evap-1"]
    assert prep.input_availability == "unresolved_references"


@pytest.mark.asyncio
async def test_g06_supplied_preferred_objective_only_reaches_provider() -> None:
    order = _explain_order()
    provider = CaptureProvider()
    result = await run_learn_authoring(
        order,
        provider=provider,
        lesson_context={"objective": "Explain evaporation"},
        allowed_facts=[],
    )
    assert len(provider.calls) == 1
    prompt = provider.calls[0].prompt
    assert "Explain evaporation" in prompt
    assert "supplied_preferred" in prompt.lower() or "No facts were supplied" in prompt
    assert '"allowed_facts": []' in prompt or "allowed_facts\": []" in prompt.replace(" ", "")
    assert result.provenance.policy["executed_knowledge_mode"] == "model_knowledge"
    assert result.provenance.policy["effective_knowledge_policy"] == "supplied_preferred"


@pytest.mark.asyncio
async def test_g07_supplied_only_fails_zero_calls() -> None:
    order = _explain_order()
    provider = CaptureProvider()
    with pytest.raises(AuthoringEngineError, match="MISSING_AUTHORING_INPUT|supplied_only"):
        await run_learn_authoring(
            order,
            provider=provider,
            lesson_context={"objective": "Explain evaporation"},
            allowed_facts=[],
            requested_knowledge_policy="supplied_only",
        )
    assert provider.calls == []


@pytest.mark.asyncio
async def test_g08_unresolved_refs_fail_under_permissive() -> None:
    order = _explain_order()
    provider = CaptureProvider()
    with pytest.raises(AuthoringEngineError, match="MISSING_AUTHORING_INPUT|unresolved"):
        await run_learn_authoring(
            order,
            provider=provider,
            lesson_context={"objective": "Explain evaporation"},
            allowed_facts=[],
            unresolved_fact_ids=["fact-evap-1"],
            referenced_fact_ids=["fact-evap-1"],
        )
    assert provider.calls == []


@pytest.mark.asyncio
async def test_g10_blank_objective_fails_convert_without_facts_ok() -> None:
    order = _explain_order()
    with pytest.raises(AuthoringEngineError, match="MISSING_AUTHORING_INPUT"):
        await run_learn_authoring(
            order,
            lesson_context={"objective": "   "},
            allowed_facts=[EVAP_FACT],
        )

    from tests.authoring_correction.test_a04_learn_authoring import _request

    contract = write_interaction_from_request(
        _request(
            "choice",
            action="select-one",
            approved_items=[
                {
                    "id": "c1",
                    "stem": "What is evaporation?",
                    "options": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}],
                    "correct_key": "b",
                }
            ],
        )
    )
    assert contract["prompt"] == "What is evaporation?"


@pytest.mark.asyncio
async def test_g11_prompt_includes_resolved_mode_not_catalogue() -> None:
    order = _explain_order()
    provider = CaptureProvider()
    await run_learn_authoring(
        order,
        provider=provider,
        lesson_context={"objective": "Explain evaporation"},
        allowed_facts=[EVAP_FACT],
    )
    prompt = provider.calls[0].prompt
    assert "KNOWLEDGE POLICY" in prompt
    assert "explanation-block" in prompt
    assert "learn-capabilities" not in prompt
    assert "sibling" not in prompt.lower() or "Do not emit sibling schemas" in prompt


@pytest.mark.asyncio
async def test_g17_unreferenced_approved_items_inaccessible() -> None:
    order = _explain_order()
    # generate content order has no source refs
    result = await run_learn_authoring(
        order,
        provider=CaptureProvider(),
        lesson_context={"objective": "Explain evaporation"},
        allowed_facts=[EVAP_FACT],
        approved_items=[
            {"id": "q1", "stem": "UNRELATED_SOURCE_MUST_NOT_LEAK", "accepted_answers": ["x"]}
        ],
    )
    assert result.mode == "generate"
    assert "UNRELATED_SOURCE_MUST_NOT_LEAK" not in str(result.payload)
