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
    AuthoringProviderOutputError,
    AuthoringProviderTerminalError,
    AuthoringRequest,
    AuthoringTransportError,
    LLMAuthoringProvider,
)
from infra.execution.call_budget import CallBudgetLedger
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
                            target="source of plant biomass",
                            purpose="Check understanding",
                            expected_evidence="Learner selects carbon dioxide.",
                            difficulty="guided",
                        ),
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
            "prompt": "Choose the source of most plant biomass.",
            "config": {
                "options": [
                    {"id": "air", "text": "Carbon dioxide"},
                    {"id": "soil", "text": "Soil"},
                ],
                "correct_option_id": "air",
            },
            "feedback": {"correct": "Yes.", "incorrect": "No."},
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
        lesson_context={"objective": "Identify the source of plant biomass."},
        allowed_facts=["Most plant biomass comes from carbon dioxide."],
        terminology=["biomass"],
    )

    assert print_result.payload == {
        "paragraphs": ["Light supplies energy for photosynthesis."]
    }
    # Learn generate schemas author prompt/config/feedback (R01 envelope).
    assert learn_result.payload["config"]["correct_option_id"] == "air"
    assert [call.native_path for call in provider.calls] == ["print", "learn"]
    assert next(call.output_schema for call in provider.calls) != provider.calls[1].output_schema
    assert all(
        "You author one already-selected educational capability" in call.prompt
        for call in provider.calls
    )


@pytest.mark.asyncio
async def test_a02_request_capture_is_scoped() -> None:
    provider = ScriptedProvider(
        {
            "prompt": "Choose the source of most plant biomass.",
            "config": {
                "options": [
                    {"id": "air", "text": "Carbon dioxide"},
                    {"id": "soil", "text": "Soil"},
                ],
                "correct_option_id": "air",
            },
            "feedback": {"correct": "Yes.", "incorrect": "No."},
        }
    )
    await run_learn_authoring(
        _learn_order(),
        engine=_shared_engine(provider),
        lesson_context={"objective": "Identify the source of plant biomass."},
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
        await run_print_authoring(
            _print_order(),
            engine=_shared_engine(provider),
            allowed_facts=["Leaves use light energy."],
        )

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
            allowed_facts=["Leaves use light energy."],
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
    assert result.provenance.source_identities == ()
    assert result.provenance.teaching_revision == 3
    assert len(result.provenance.definition_hash) == 64
    assert len(result.provenance.input_hash) == 64
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_authoring_provider_uses_one_unmetered_retry_free_dispatch(monkeypatch) -> None:
    from v3_execution import llm_helpers

    calls: list[dict[str, Any]] = []

    async def one_dispatch(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"paragraphs": ["Structured output is parsed by the engine."]}

    monkeypatch.setattr(llm_helpers, "run_structured_agent", one_dispatch)
    result = await LLMAuthoringProvider().invoke(
        AuthoringProviderCall(
            work_order_id="one-dispatch",
            capability_id="demo",
            native_path="learn",
            mode="generate",
            attempt=1,
            is_repair=False,
            prompt="Return this capability payload.",
            output_schema={"type": "object", "required": ["paragraphs"]},
        )
    )

    assert result == {"paragraphs": ["Structured output is parsed by the engine."]}
    assert len(calls) == 1
    assert calls[0]["output_type"] == dict[str, Any]
    assert calls[0]["retries"] == {"output": 0}
    assert calls[0]["retry_policy"].max_attempts == 1


@pytest.mark.asyncio
async def test_structured_output_error_uses_same_engine_repair_and_budget() -> None:
    provider = ScriptedProvider(
        AuthoringProviderOutputError(["paragraphs: expected at least one item"]),
        {"paragraphs": ["The engine corrected the structured output."]},
    )
    ledger = CallBudgetLedger()
    engine = _shared_engine(provider, repairs=1, transport=1)
    engine.budget_ledger = ledger

    result = await run_print_authoring(
        _print_order(),
        engine=engine,
        allowed_facts=["Correctable structured output."],
    )

    assert result.payload["paragraphs"] == ["The engine corrected the structured output."]
    assert result.repair_attempts == 1
    assert len(provider.calls) == 2
    assert [call.is_repair for call in provider.calls] == [False, True]
    budget = ledger.load(provider.calls[0].work_order_id)
    assert budget is not None and budget.dispatched_count == 2
    assert budget.consumed == 2


@pytest.mark.asyncio
async def test_terminal_provider_failure_does_not_enter_semantic_repair() -> None:
    provider = ScriptedProvider(AuthoringProviderTerminalError("permanent_auth", "bad API key"))
    engine = _shared_engine(provider, repairs=2, transport=2)

    with pytest.raises(AuthoringEngineError) as caught:
        await run_print_authoring(
            _print_order(),
            engine=engine,
            allowed_facts=["The provider is not authorized."],
        )

    assert caught.value.code == "PROVIDER_FAILURE"
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_llm_adapter_dispatches_match_budget_for_output_and_transport_errors(monkeypatch) -> None:
    """Count at the actual run_llm boundary, below the structured-output helper."""
    from types import SimpleNamespace

    import httpx
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    from v3_execution import llm_helpers

    spec = object()
    monkeypatch.setattr(llm_helpers, "get_v3_spec", lambda _node: spec)
    monkeypatch.setattr(llm_helpers, "get_v3_slot", lambda _node: "slot")
    monkeypatch.setattr(
        llm_helpers, "get_v3_model_settings", lambda _node, base_settings=None: base_settings or {}
    )
    monkeypatch.setattr(
        llm_helpers,
        "prepare_structured_agent",
        lambda **_kwargs: ("model", dict[str, Any], llm_helpers.StructuredCallContext(), spec, None),
    )
    monkeypatch.setattr(llm_helpers, "Agent", lambda **_kwargs: object())

    definition = AuthoringDefinition(
        capability_id="dispatch-count",
        native_path="learn",
        modes=("generate",),
        instructions="Return an object with ok=true.",
        payload_schema={
            "type": "object",
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean"}},
            "additionalProperties": False,
        },
    )
    request = AuthoringRequest(
        work_order_id="llm-dispatch-count",
        definition=definition,
        scoped_request={},
        inputs={},
        teaching_revision=1,
    )

    dispatches = 0

    async def malformed_then_valid(**_kwargs):
        nonlocal dispatches
        dispatches += 1
        if dispatches == 1:
            raise UnexpectedModelBehavior("provider returned invalid JSON")
        return SimpleNamespace(output={"ok": True})

    monkeypatch.setattr(llm_helpers, "run_llm", malformed_then_valid)
    ledger = CallBudgetLedger()
    engine = AuthoringEngine(
        provider=LLMAuthoringProvider(),
        max_repair_attempts=1,
        budget_ledger=ledger,
    )
    result = await engine.execute(request)

    assert result.payload == {"ok": True}
    budget = ledger.load(request.work_order_id)
    assert budget is not None
    assert dispatches == budget.dispatched_count == budget.consumed == 2
    assert budget.ambiguous_count == 0

    dispatches = 0

    async def rate_limited(**_kwargs):
        nonlocal dispatches
        dispatches += 1
        response = httpx.Response(429, request=httpx.Request("POST", "https://provider.invalid"))
        raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)

    monkeypatch.setattr(llm_helpers, "run_llm", rate_limited)
    transport_ledger = CallBudgetLedger()
    transport_engine = AuthoringEngine(
        provider=LLMAuthoringProvider(),
        max_transport_attempts=1,
        budget_ledger=transport_ledger,
    )
    with pytest.raises(AuthoringEngineError) as caught:
        await transport_engine.execute(
            AuthoringRequest(
                work_order_id="llm-rate-limit",
                definition=definition,
                scoped_request={},
                inputs={},
                teaching_revision=1,
            )
        )

    assert caught.value.code == "PROVIDER_TRANSPORT_EXHAUSTED"
    budget = transport_ledger.load("llm-rate-limit")
    assert budget is not None
    assert dispatches == budget.consumed == 1
    assert budget.dispatched_count == 0
    assert budget.ambiguous_count == 1

    dispatches = 0

    async def timed_out(**_kwargs):
        nonlocal dispatches
        dispatches += 1
        raise TimeoutError("provider request timed out")

    monkeypatch.setattr(llm_helpers, "run_llm", timed_out)
    timeout_ledger = CallBudgetLedger()
    timeout_engine = AuthoringEngine(
        provider=LLMAuthoringProvider(),
        max_transport_attempts=1,
        budget_ledger=timeout_ledger,
    )
    with pytest.raises(AuthoringEngineError) as timeout_caught:
        await timeout_engine.execute(
            AuthoringRequest(
                work_order_id="llm-timeout",
                definition=definition,
                scoped_request={},
                inputs={},
                teaching_revision=1,
            )
        )
    assert timeout_caught.value.code == "PROVIDER_TRANSPORT_EXHAUSTED"
    timeout_budget = timeout_ledger.load("llm-timeout")
    assert timeout_budget is not None
    assert dispatches == timeout_budget.consumed == timeout_budget.ambiguous_count == 1
    assert timeout_budget.dispatched_count == 0

    dispatches = 0

    async def programming_error(**_kwargs):
        nonlocal dispatches
        dispatches += 1
        raise AssertionError("adapter programming defect")

    monkeypatch.setattr(llm_helpers, "run_llm", programming_error)
    programming_ledger = CallBudgetLedger()
    programming_engine = AuthoringEngine(
        provider=LLMAuthoringProvider(),
        max_repair_attempts=2,
        budget_ledger=programming_ledger,
    )
    with pytest.raises(AuthoringEngineError) as programming_caught:
        await programming_engine.execute(
            AuthoringRequest(
                work_order_id="llm-programming-error",
                definition=definition,
                scoped_request={},
                inputs={},
                teaching_revision=1,
            )
        )
    assert programming_caught.value.code == "PROVIDER_FAILURE"
    assert programming_caught.value.retryable is False
    programming_budget = programming_ledger.load("llm-programming-error")
    assert programming_budget is not None
    assert dispatches == programming_budget.consumed == programming_budget.dispatched_count == 1
    assert programming_budget.ambiguous_count == 0


@pytest.mark.asyncio
async def test_actual_dispatch_budget_covers_repeated_invalid_5xx_and_auth(monkeypatch) -> None:
    """Repeated content defects repair within budget; transport/auth never become repair."""
    import httpx
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    from v3_execution import llm_helpers

    spec = object()
    monkeypatch.setattr(llm_helpers, "get_v3_spec", lambda _node: spec)
    monkeypatch.setattr(llm_helpers, "get_v3_slot", lambda _node: "slot")
    monkeypatch.setattr(
        llm_helpers, "get_v3_model_settings", lambda _node, base_settings=None: base_settings or {}
    )
    monkeypatch.setattr(
        llm_helpers,
        "prepare_structured_agent",
        lambda **_kwargs: ("model", dict[str, Any], llm_helpers.StructuredCallContext(), spec, None),
    )
    monkeypatch.setattr(llm_helpers, "Agent", lambda **_kwargs: object())

    definition = AuthoringDefinition(
        capability_id="dispatch-failure-matrix",
        native_path="learn",
        modes=("generate",),
        instructions="Return an object with ok=true.",
        payload_schema={
            "type": "object",
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean"}},
            "additionalProperties": False,
        },
    )
    dispatches = 0

    async def repeated_invalid(**_kwargs):
        nonlocal dispatches
        dispatches += 1
        raise UnexpectedModelBehavior("provider returned invalid JSON")

    monkeypatch.setattr(llm_helpers, "run_llm", repeated_invalid)
    repeated_ledger = CallBudgetLedger()
    repeated_engine = AuthoringEngine(
        provider=LLMAuthoringProvider(), max_repair_attempts=2, budget_ledger=repeated_ledger
    )
    with pytest.raises(AuthoringEngineError) as repeated_error:
        await repeated_engine.execute(
            AuthoringRequest(
                work_order_id="llm-repeated-invalid",
                definition=definition,
                scoped_request={},
                inputs={},
                teaching_revision=1,
            )
        )
    repeated_budget = repeated_ledger.load("llm-repeated-invalid")
    assert repeated_error.value.code == "REPAIR_EXHAUSTED"
    from print.generation.whole_lesson.failure_policy import classify_failure

    retry_policy = classify_failure(repeated_error.value)
    assert retry_policy.code == "VALIDATION"
    assert retry_policy.retryable is True
    assert retry_policy.repairable is False
    assert repeated_budget is not None
    assert dispatches == repeated_budget.dispatched_count == repeated_budget.consumed == 3

    for status_code, expected_code, work_order_id in [
        (503, "PROVIDER_TRANSPORT_EXHAUSTED", "llm-provider-5xx"),
        (401, "PROVIDER_FAILURE", "llm-provider-auth"),
    ]:
        dispatches = 0

        async def provider_status(status_code=status_code, **_kwargs):
            nonlocal dispatches
            dispatches += 1
            response = httpx.Response(
                status_code,
                request=httpx.Request("POST", "https://provider.invalid"),
            )
            raise httpx.HTTPStatusError(
                f"provider returned {status_code}", request=response.request, response=response
            )

        monkeypatch.setattr(llm_helpers, "run_llm", provider_status)
        ledger = CallBudgetLedger()
        engine = AuthoringEngine(
            provider=LLMAuthoringProvider(),
            max_transport_attempts=1,
            max_repair_attempts=2,
            budget_ledger=ledger,
        )
        with pytest.raises(AuthoringEngineError) as failure:
            await engine.execute(
                AuthoringRequest(
                    work_order_id=work_order_id,
                    definition=definition,
                    scoped_request={},
                    inputs={},
                    teaching_revision=1,
                )
            )
        budget = ledger.load(work_order_id)
        assert failure.value.code == expected_code
        assert budget is not None
        assert dispatches == budget.consumed == 1
        if status_code == 503:
            assert budget.ambiguous_count == 1
        else:
            assert budget.dispatched_count == 1
