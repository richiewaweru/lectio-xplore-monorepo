from __future__ import annotations

from typing import Any

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringEngineError,
    AuthoringProviderCall,
    AuthoringRequest,
    AuthoringTransportError,
)
from learn.generation.authoring_adapter import build_learn_authoring_registry, run_learn_authoring
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.work_orders import compile_learn_work_orders
from print.generation.authoring_adapter import build_print_authoring_registry, run_print_authoring
from print.generation.selection_snapshot import PrintSelectionDecision, PrintSelectionSnapshot
from print.generation.work_orders import compile_print_work_orders


class ScriptedProvider:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.calls.append(call)
        if not self.responses:
            raise AssertionError("provider called more often than scripted")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _shared_engine(
    provider: ScriptedProvider,
    *,
    repairs: int = 1,
    transport: int = 2,
) -> AuthoringEngine:
    registry = build_print_authoring_registry()
    learn_registry = build_learn_authoring_registry()
    registry.validators.update(learn_registry.validators)
    registry.converters.update(learn_registry.converters)
    return AuthoringEngine(
        registry=registry,
        provider=provider,
        max_repair_attempts=repairs,
        max_transport_attempts=transport,
    )


def _print_order(form_id: str = "prose"):
    plan = TeachingPlan(
        arc="A02",
        teaching_plan_id="tp-a02-print",
        revision=3,
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                blocks=[
                    TeachingPlanBlock(
                        id="pb1",
                        position=0,
                        intent="explain",
                        brief="Explain why leaves need light for photosynthesis.",
                        evidence="Learner states the role of light.",
                        source_question_ids=["src-print-1"],
                    )
                ],
            )
        ],
    )
    snapshot = PrintSelectionSnapshot(
        teaching_plan_id="tp-a02-print",
        teaching_plan_revision=3,
        teaching_plan_hash="print-teaching-hash",
        native_policy_hash="print-policy-hash",
        package_contract_hash="print-package-hash",
        decisions=[PrintSelectionDecision(block_id="pb1", form_id=form_id)],
    ).seal()
    return compile_print_work_orders(teaching_plan=plan, snapshot=snapshot)[0]


def _learn_order():
    plan = TeachingPlan(
        arc="A02",
        teaching_plan_id="tp-a02-learn",
        revision=4,
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                blocks=[
                    TeachingPlanBlock(
                        id="lb1",
                        position=0,
                        intent="check-understanding",
                        brief="Choose the source of most plant biomass.",
                        evidence="Learner selects carbon dioxide.",
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            support_level="guided",
                            evidence="Learner selects carbon dioxide.",
                        ),
                        source_question_ids=["src-learn-1"],
                    )
                ],
            )
        ],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id="tp-a02-learn",
        teaching_plan_revision=4,
        teaching_plan_hash="learn-teaching-hash",
        native_policy_hash="learn-policy-hash",
        package_contract_hash="learn-package-hash",
        decisions=[LearnSelectionDecision(block_id="lb1", interaction_id="choice")],
    ).seal()
    return compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)[0]


@pytest.mark.asyncio
async def test_a02_print_and_learn_adapters_share_engine_with_own_schemas() -> None:
    provider = ScriptedProvider(
        {"paragraphs": ["Light supplies energy for photosynthesis."]},
        {
            "options": [
                {"id": "air", "text": "Carbon dioxide"},
                {"id": "soil", "text": "Soil"},
            ],
            "correct_option_id": "air",
        },
    )
    engine = _shared_engine(provider)

    print_result = await run_print_authoring(
        _print_order(),
        engine=engine,
        allowed_facts=["Leaves use light energy."],
        terminology=["photosynthesis"],
    )
    learn_result = await run_learn_authoring(
        _learn_order(),
        engine=engine,
        allowed_facts=["Most plant biomass comes from carbon dioxide."],
        terminology=["biomass"],
    )

    assert print_result.payload == {
        "paragraphs": ["Light supplies energy for photosynthesis."]
    }
    assert learn_result.payload["correct_option_id"] == "air"
    assert [call.native_path for call in provider.calls] == ["print", "learn"]
    assert [call.output_schema for call in provider.calls][0] != provider.calls[1].output_schema
    assert all(
        "You author one already-selected educational capability" in call.prompt
        for call in provider.calls
    )


@pytest.mark.asyncio
async def test_a02_request_capture_is_scoped() -> None:
    provider = ScriptedProvider(
        {
            "options": [
                {"id": "air", "text": "Carbon dioxide"},
                {"id": "soil", "text": "Soil"},
            ],
            "correct_option_id": "air",
        }
    )
    await run_learn_authoring(
        _learn_order(),
        engine=_shared_engine(provider),
        allowed_facts=["Only this scoped fact is allowed."],
        terminology=["carbon dioxide"],
        approved_items=[
            {
                "id": "unrelated-approved-id",
                "stem": "This should never be present in a generate request.",
                "options": [{"id": "x", "text": "X"}, {"id": "y", "text": "Y"}],
                "correct_key": "x",
            }
        ],
        mode="generate",
    )

    prompt = provider.calls[0].prompt
    assert "Only this scoped fact is allowed." in prompt
    assert "unrelated-approved-id" not in prompt
    assert "This should never be present" not in prompt
    assert "full_catalogue" not in prompt
    assert "all_capabilities" not in prompt
    assert "sibling_payload_schema" not in prompt
    assert "other-path-setting" not in prompt


@pytest.mark.asyncio
async def test_a02_malformed_response_repairs_with_original_scope() -> None:
    provider = ScriptedProvider(
        {"paragraphs": []},
        {"paragraphs": ["Repaired with the same scope."]},
    )
    result = await run_print_authoring(
        _print_order(),
        engine=_shared_engine(provider),
        allowed_facts=["Do not broaden the lesson."],
        terminology=["light"],
    )

    assert result.repair_attempts == 1
    assert result.payload["paragraphs"] == ["Repaired with the same scope."]
    assert provider.calls[1].is_repair is True
    assert "Explain why leaves need light for photosynthesis." in provider.calls[1].prompt
    assert "paragraphs" in provider.calls[1].prompt
    assert "minItems 1" in provider.calls[1].prompt


@pytest.mark.asyncio
async def test_a02_repair_exhaustion_is_typed_failure() -> None:
    provider = ScriptedProvider({"paragraphs": []}, {"paragraphs": []})

    with pytest.raises(AuthoringEngineError) as caught:
        await run_print_authoring(_print_order(), engine=_shared_engine(provider))

    assert caught.value.code == "REPAIR_EXHAUSTED"
    assert caught.value.stage == "repair"
    assert caught.value.repair_attempts == 1
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_a02_missing_definition_input_and_provider_are_typed_failures() -> None:
    definition = AuthoringDefinition(
        capability_id="demo",
        native_path="test",
        modes=("generate",),
        instructions="Write a demo payload.",
        payload_schema={"type": "object"},
        required_inputs=("lesson_context",),
        validator_refs=(),
    )
    engine = AuthoringEngine(registry=build_print_authoring_registry(), provider=None)

    with pytest.raises(AuthoringEngineError) as missing_definition:
        await engine.execute(
            AuthoringRequest(
                work_order_id="missing-definition",
                definition=None,
                scoped_request={},
                inputs={},
                teaching_revision=1,
            )
        )
    assert missing_definition.value.code == "MISSING_AUTHORING_DEFINITION"

    with pytest.raises(AuthoringEngineError) as missing_input:
        await engine.execute(
            AuthoringRequest(
                work_order_id="missing-input",
                definition=definition,
                scoped_request={},
                inputs={},
                teaching_revision=1,
                mode="generate",
            )
        )
    assert missing_input.value.code == "MISSING_AUTHORING_INPUT"

    with pytest.raises(AuthoringEngineError) as no_provider:
        await run_print_authoring(
            _print_order(),
            engine=AuthoringEngine(registry=build_print_authoring_registry(), provider=None),
        )
    assert no_provider.value.code == "NO_COMPATIBLE_CAPABILITY"


@pytest.mark.asyncio
async def test_a02_provenance_present_and_transport_retries_bounded() -> None:
    provider = ScriptedProvider(
        AuthoringTransportError("timeout"),
        {"paragraphs": ["Transport retry stayed bounded."]},
    )

    result = await run_print_authoring(
        _print_order(),
        engine=_shared_engine(provider, transport=2),
        allowed_facts=["Bounded retry fact."],
        terminology=["retry"],
    )

    assert result.transport_attempts == 2
    assert result.repair_attempts == 0
    assert result.provenance.work_order_id == result.work_order_id
    assert result.provenance.source_identities == ("src-print-1",)
    assert result.provenance.teaching_revision == 3
    assert len(result.provenance.definition_hash) == 64
    assert len(result.provenance.input_hash) == 64
    assert len(provider.calls) == 2
