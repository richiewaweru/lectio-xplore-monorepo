"""A06 integrated offline — historical suite; real evidence moved to R04 gates.

Superseded claims (deepcopy reload, hash-only publish, dispatch_writer_async dual-path,
evaluator-only interaction checks) are removed. See tests/remaining_fixes/test_r04_*.py.
"""

from __future__ import annotations

import pytest

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from infra.authoring import AuthoringEngineError, AuthoringProviderCall
from learn.generation.interaction_writer import InteractionWriterError
from learn.generation.native_production import build_closed_learn_production
from learn.generation.preparation_context import LearnPreparationContext
from learn.generation.native_selection import build_learn_selection_snapshot
from learn.generation.ordered_assemble import assemble_ordered_learn_document
from learn.generation.work_orders import LearnWorkOrder, build_learn_writer_request
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash
from learn.resources.selection import load_learn_writer_view
from tests.authoring_correction.test_a04_learn_authoring import CapabilityProvider


def _learn_plan(*blocks: TeachingPlanBlock) -> TeachingPlan:
    return TeachingPlan(
        arc="Light drives photosynthesis.",
        teaching_plan_id="tp-a06",
        revision=1,
        sections=[TeachingPlanSection(slot_id="main", specific_purpose="Integrated offline", blocks=list(blocks))],
    )


def _snapshot(plan: TeachingPlan):
    plan_hash = "hash-a06"
    _, policy_hash = policy_version_and_hash(default_learn_policy())
    return build_learn_selection_snapshot(
        plan,
        teaching_plan_hash=plan_hash,
        native_policy_hash=policy_hash,
        package_contract_hash="pkg-a06",
        policy=default_learn_policy(),
    )


@pytest.mark.skip(reason="Superseded by R04-G01/G02: real dual-path persist + publish API — test_r04_g01_dual_path_persistence.py")
def test_a06_g02_dual_path_same_revision_mocked_only() -> None:
    """Former dual-path claim used dispatch_writer_async, not full Print production."""
    pytest.skip("Use test_r04_g01_dual_path_persistence")


@pytest.mark.skip(reason="Superseded by R04-G03/G05: runtime API + component mounts — test_r04_g03_*, interaction-shells.r04.test.ts")
def test_a06_g03_core_interactions_evaluate_and_reload() -> None:
    pytest.skip("Use R04 runtime and component gates")


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
        async def invoke(self, call: AuthoringProviderCall) -> dict:
            return {"not_a_valid_explanation_block": True}

    with pytest.raises(AuthoringEngineError, match="REPAIR_EXHAUSTED|INVALID_PAYLOAD"):
        build_closed_learn_production(
            teaching_plan=plan,
            provider=_BadProvider(),
            preparation_context=LearnPreparationContext(
                objective="Explain evaporation.",
                allowed_facts=["Evaporation turns liquid water into vapour."],
            ),
        )


@pytest.mark.skip(reason="Superseded by R04-G02: publish v1/v2 via API — test_r04_g02_publish_builder.py")
def test_a06_g04_publish_v1_immutable_v2_hash() -> None:
    pytest.skip("Use test_r04_g02_publish_builder")


def test_a06_g05_definition_edit_changes_writer_request_instructions() -> None:
    """Instruction drift changes writer request text (definition hash path simulated in R04-G06)."""
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
