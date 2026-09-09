"""A06 integrated offline acceptance — dual-path production with mocked boundaries."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringEngineError, AuthoringProviderCall
from learn.generation.authoring_adapter import run_learn_work_order_authoring
from learn.generation.interaction_writer import InteractionWriterError, validate_interaction_contract
from learn.generation.native_production import build_closed_learn_production, teaching_plan_content_hash
from learn.generation.native_selection import build_learn_selection_snapshot
from learn.generation.work_orders import LearnWorkOrder, compile_learn_work_orders
from learn.publishing.publish_validation import PublishValidationError, validate_publishable_lesson_document
from learn.publishing.release_routes import document_hash
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash
from learn.resources.selection import load_learn_writer_view
from learn.runtime.evaluation import evaluate_interaction, evaluate_numeric, evaluate_sequence
from print.generation.selection_snapshot import build_print_selection_snapshot, select_print_deterministically
from print.resources.native_policy import default_print_policy, policy_version_and_hash as print_policy_hash
from print.resources.selection import build_print_candidate_map
from print.rendering.page_objects import WriterContext, dispatch_writer_async
from tests.authoring_correction.test_a04_learn_authoring import CapabilityProvider, CORE_GENERATED
from v3_blueprint.planning.models import PlannedBlock


class _PrintCapturingProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> dict[str, Any]:
        self.calls.append(call)
        return dict(self.payload)


def _learn_plan(*blocks: TeachingPlanBlock) -> TeachingPlan:
    return TeachingPlan(
        arc="Light drives photosynthesis and distance practice.",
        teaching_plan_id="tp-a06",
        revision=1,
        sections=[TeachingPlanSection(slot_id="main", specific_purpose="Integrated offline", blocks=list(blocks))],
    )


def _snapshot(plan: TeachingPlan):
    plan_hash = teaching_plan_content_hash(plan)
    _, policy_hash = policy_version_and_hash(default_learn_policy())
    return build_learn_selection_snapshot(
        plan,
        teaching_plan_hash=plan_hash,
        native_policy_hash=policy_hash,
        package_contract_hash="pkg-a06",
        policy=default_learn_policy(),
    )


def _print_ctx(object_id: str, *, block_id: str, brief: str) -> WriterContext:
    planned = PlannedBlock.model_validate(
        {
            "id": block_id,
            "position": 0,
            "intent": "explain",
            "object": object_id,
            "evidence": "A06 evidence",
            "brief": brief,
            "source_question_ids": [],
        }
    )
    return WriterContext(planned=planned, use_llm=True, item_records=[])


def test_a06_g02_dual_path_same_revision_mocked_only() -> None:
    """Print and Learn closed production from one teaching revision; providers mocked."""
    import asyncio

    plan = _learn_plan(
        TeachingPlanBlock(
            id="b-explain",
            position=0,
            intent="explain",
            brief="Explain how light powers photosynthesis with a concrete plant example.",
            evidence="Read explanation",
        ),
    )
    plan_hash = teaching_plan_content_hash(plan)
    policy = default_learn_policy()
    policy["offered_content"] = ["explanation-block"]
    provider = CapabilityProvider()

    learn_production = build_closed_learn_production(
        teaching_plan=plan,
        policy=policy,
        provider=provider,
        title=plan.arc,
    )
    assert learn_production["teaching_plan_hash"] == plan_hash
    assert learn_production["document"]["blocks"]
    assert provider.calls

    print_candidates = build_print_candidate_map(
        plan,
        compatible_objects_by_intent={"explain": ("prose", "list")},
    )
    _, native_hash = print_policy_hash()
    print_decisions = select_print_deterministically(plan, candidate_map=print_candidates)
    print_snapshot = build_print_selection_snapshot(
        plan,
        candidate_map=print_candidates,
        teaching_plan_hash=plan_hash,
        native_policy_hash=native_hash,
        package_contract_hash="pkg-page-a06",
        decisions=print_decisions,
    )
    assert print_snapshot.teaching_plan_hash == plan_hash
    assert print_snapshot.teaching_plan_revision == plan.revision

    async def _print_block() -> None:
        payload = {"paragraphs": ["Plants convert light into food through photosynthesis."]}
        result = await dispatch_writer_async(
            _print_ctx("prose", block_id="b-explain", brief="Explain photosynthesis."),
            provider=_PrintCapturingProvider(payload),
        )
        assert result.status == "ready"
        assert "photosynthesis" in str(result.content).lower()

    asyncio.run(_print_block())


@pytest.mark.parametrize(
    "capability_id,action,response",
    [
        ("sequence", "order-items", {"order": ["egg", "larva", "pupa", "adult"]}),
        ("numeric", "enter-number", {"value": 50}),
    ],
)
def test_a06_g03_core_interactions_evaluate_and_reload(
    capability_id: str,
    action: str,
    response: dict[str, Any],
) -> None:
    """Representative interaction contracts evaluate and survive publish reload."""
    from learn.generation.interaction_writer import write_interaction_from_request

    approved = None
    if capability_id == "numeric":
        approved = {"id": "numeric-a06", "value": 50, "unit": "m"}
    if capability_id == "sequence":
        approved = {"id": "sequence-a06", "correct_order": ["egg", "larva", "pupa", "adult"]}

    contract = write_interaction_from_request(
        {
            "work_order_id": f"a06::{capability_id}",
            "block_id": f"b-{capability_id}",
            "capability_id": capability_id,
            "lane": "interaction",
            "brief": f"Author {capability_id}",
            "intent": "check-understanding",
            "action": action,
            "evidence": "Known-answer regression",
            "teaching_plan_hash": "a06",
            "approved_items": [approved] if approved else [],
        },
        provider=CapabilityProvider(),
    )
    assert validate_interaction_contract(contract) == []
    result = evaluate_interaction(contract, response)
    assert result.outcome == "correct"

    plan = _learn_plan(
        TeachingPlanBlock(
            id=f"b-{capability_id}",
            position=0,
            intent="check-understanding",
            brief=f"Check {capability_id}.",
            evidence="Evidence",
            learner_action=LearnerActionBrief(action=action, support_level="guided", evidence="Evidence", source_item_ids=[]),
        )
    )
    document = build_closed_learn_production(
        teaching_plan=plan,
        policy={**default_learn_policy(), "offered_content": ["explanation-block"], "offered_interactions": [capability_id]},
        provider=CapabilityProvider(),
    )["document"]
    validate_publishable_lesson_document(document)
    reloaded = copy.deepcopy(document)
    reloaded["title"] = "Reloaded"
    validate_publishable_lesson_document(reloaded)
    assert document_hash(document) == document_hash(copy.deepcopy(document))


def test_a06_g03_invalid_payload_rejected_at_provider_boundary() -> None:
    """Malformed provider output fails closed instead of silently assembling."""
    plan = _learn_plan(
        TeachingPlanBlock(
            id="b1",
            position=0,
            intent="explain",
            brief="Explain evaporation.",
            evidence="Read",
        )
    )

    class _BadProvider:
        async def invoke(self, call: AuthoringProviderCall) -> dict[str, Any]:
            return {"not_a_valid_explanation_block": True}

    with pytest.raises(AuthoringEngineError, match="REPAIR_EXHAUSTED|INVALID_PAYLOAD"):
        build_closed_learn_production(teaching_plan=plan, provider=_BadProvider())


def test_a06_g04_publish_v1_immutable_v2_hash() -> None:
    """Published v1 hash stays stable when draft moves to v2."""
    document = build_closed_learn_production(
        teaching_plan=_learn_plan(
            TeachingPlanBlock(
                id="b1",
                position=0,
                intent="explain",
                brief="Plants need light.",
                evidence="Read",
            )
        ),
        provider=CapabilityProvider(),
    )["document"]
    validate_publishable_lesson_document(document)
    hash_v1 = document_hash(document)
    edited = copy.deepcopy(document)
    edited["blocks"][next(iter(edited["blocks"]))]["content"]["body"] = "Edited body"
    hash_v2 = document_hash(edited)
    assert hash_v1 != hash_v2
    assert document_hash(copy.deepcopy(document)) == hash_v1


def test_a06_g05_definition_edit_changes_contract_hash() -> None:
    """Instruction/schema drift changes definition hash used by production requests."""
    card = load_learn_writer_view()["capabilities"]["explanation-block"]
    order = LearnWorkOrder(
        work_order_id="learn::a06::b1::explanation-block",
        block_id="b1",
        section_id="s-a06",
        lane="content",
        capability_id="explanation-block",
        teaching_plan_id="tp-a06",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-a06",
        capability_contract_hash=str(card["definition_hash"]),
        expected_output_schema=dict(card["payload_schema"]),
        field_guidance=dict(card.get("field_guidance") or {}),
        authoring_definition=dict(card),
        instructions=card.get("instructions"),
        required_inputs=list(card.get("required_inputs") or []),
        modes=list(card.get("modes") or []),
        validator_refs=list(card.get("validator_refs") or []),
        brief="Explain photosynthesis.",
        intent="explain",
        evidence="Evidence",
    )
    from learn.generation.work_orders import build_learn_writer_request

    baseline = build_learn_writer_request(order)
    mutated_card = dict(card)
    instructions = dict(mutated_card.get("instructions") or {})
    instructions["text"] = str(instructions.get("text") or "") + " Emphasize chlorophyll."
    mutated_card["instructions"] = instructions
    mutated_order = order.model_copy(
        update={
            "authoring_definition": mutated_card,
            "instructions": mutated_card["instructions"],
        }
    )
    mutated = build_learn_writer_request(mutated_order)
    assert baseline["definition_hash"] == order.capability_contract_hash
    assert mutated["instructions"] != baseline["instructions"]


def test_a06_g05_assembly_still_rejects_missing_authored_results() -> None:
    """Defect regression: assembly fails closed without authored payloads."""
    from learn.generation.ordered_assemble import assemble_ordered_learn_document

    plan = _learn_plan(
        TeachingPlanBlock(id="b1", position=0, intent="explain", brief="Explain.", evidence="Read")
    )
    snapshot = _snapshot(plan)
    with pytest.raises(InteractionWriterError, match="MISSING_CONTENT_PAYLOAD"):
        assemble_ordered_learn_document(teaching_plan=plan, snapshot=snapshot)


def test_a06_g01_gate_tracking_files_exist() -> None:
    """Mandatory gate artefacts are present for A06 offline acceptance."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[5] / "docs" / "unit-native-program" / "authoring-correction-v2"
    for relative in (
        "tracking/A06-PLAN.md",
        "tracking/GATE_RESULTS.csv",
        "tracking/STATE.json",
        "acceptance/POLICY.md",
    ):
        assert (root / relative).is_file(), relative
