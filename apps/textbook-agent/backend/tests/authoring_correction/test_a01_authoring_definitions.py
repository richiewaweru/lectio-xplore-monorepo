"""A01 authoring definition gates."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.work_orders import (
    _capability_contract_hash,
    build_learn_writer_request,
    compile_learn_work_orders,
)
from learn.resources.native_policy import default_learn_policy
from learn.resources.selection import derive_learn_block_candidates
from print.generation.selection_snapshot import PrintSelectionDecision, PrintSelectionSnapshot
from print.generation.work_orders import (
    _form_contract_hash,
    build_print_writer_request,
    compile_print_work_orders,
)
from print.resources.native_policy import default_print_policy
from print.resources.selection import derive_print_block_candidates

BACKEND = Path(__file__).resolve().parents[2]
PAGE_CONTRACTS = BACKEND / "contracts" / "lectio-page"
LEARN_CONTRACTS = BACKEND / "contracts"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_complete(card: dict, *, capability_id: str, native_path: str) -> None:
    assert card["definition_version"] == "2.0.0"
    assert card["capability_id"] == capability_id
    assert card["native_path"] == native_path
    assert card["purpose"]
    assert set(card["modes"]).intersection({"generate", "convert-approved"})
    assert card["instructions"]["text"].strip()
    assert card["instructions"]["resource_ref"].startswith("contracts/authoring/instructions/")
    assert card["schema_ref"] == card["payload_schema_ref"]
    assert card["payload_schema"]
    assert card["field_guidance"]
    assert card["required_inputs"]
    assert card["capacity"] is not None
    assert card["validator_refs"]
    assert len(card["definition_hash"]) == 64


def test_a01_generation_enabled_capabilities_have_complete_authoring_definitions() -> None:
    page_view = _read_json(PAGE_CONTRACTS / "form-writer-view.v1.json")
    page_policy = default_print_policy()
    for form_id in page_policy["offered_forms"]:
        if form_id in set(page_policy.get("denied_forms", [])):
            continue
        _assert_complete(page_view["forms"][form_id], capability_id=form_id, native_path="print")

    learn_view = _read_json(LEARN_CONTRACTS / "learn-writer-view.v1.json")
    learn_policy = default_learn_policy()
    generation_enabled = set(learn_policy["offered_content"]) | set(learn_policy["offered_interactions"])
    generation_enabled -= set(learn_policy.get("denied_capabilities", []))
    for capability_id in sorted(generation_enabled):
        _assert_complete(
            learn_view["capabilities"][capability_id],
            capability_id=capability_id,
            native_path="learn",
        )


def test_a01_instruction_text_reaches_actual_writer_requests() -> None:
    print_plan = TeachingPlan(
        arc="A01",
        teaching_plan_id="tp-a01-print",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                blocks=[
                    TeachingPlanBlock(
                        id="b1",
                        position=0,
                        intent="explain",
                        brief="Explain the idea.",
                        evidence="Evidence",
                    )
                ],
            )
        ],
    )
    print_snapshot = PrintSelectionSnapshot(
        teaching_plan_id="tp-a01-print",
        teaching_plan_revision=1,
        teaching_plan_hash="tp-hash",
        native_policy_hash="policy-hash",
        package_contract_hash="package-hash",
        decisions=[PrintSelectionDecision(block_id="b1", form_id="prose")],
    ).seal()
    print_order = compile_print_work_orders(teaching_plan=print_plan, snapshot=print_snapshot)[0]
    print_request = build_print_writer_request(print_order)
    assert "Assigned object: prose." in print_request["instructions"]["text"]
    assert print_request["definition_hash"] == print_order.capability_contract_hash

    learn_plan = TeachingPlan(
        arc="A01",
        teaching_plan_id="tp-a01-learn",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                blocks=[
                    TeachingPlanBlock(
                        id="b1",
                        position=0,
                        intent="check-understanding",
                        brief="Check one taught idea.",
                        evidence="Evidence",
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            support_level="guided",
                            evidence="Evidence",
                        ),
                    )
                ],
            )
        ],
    )
    learn_snapshot = LearnSelectionSnapshot(
        teaching_plan_id="tp-a01-learn",
        teaching_plan_revision=1,
        teaching_plan_hash="tp-hash",
        native_policy_hash="policy-hash",
        package_contract_hash="package-hash",
        decisions=[LearnSelectionDecision(block_id="b1", interaction_id="choice")],
    ).seal()
    learn_order = compile_learn_work_orders(teaching_plan=learn_plan, snapshot=learn_snapshot)[0]
    learn_request = build_learn_writer_request(learn_order)
    assert "Capability: choice." in learn_request["instructions"]["text"]
    assert learn_request["definition_hash"] == learn_order.capability_contract_hash


def test_a01_missing_instruction_and_unknown_validator_fail_readiness() -> None:
    page_view = _read_json(PAGE_CONTRACTS / "form-writer-view.v1.json")
    bad_page = copy.deepcopy(page_view["forms"])
    bad_page["prose"]["instructions"]["text"] = ""
    assert (
        derive_print_block_candidates(
            block_id="b1",
            intent="explain",
            action=None,
            package_compatible=["prose"],
            policy=default_print_policy(),
            form_cards={"prose": {"supported_intents": ["explain"], "supported_actions": []}},
            writer_view=bad_page,
        ).excluded["prose"]
        == "missing_instructions"
    )
    bad_page["prose"] = copy.deepcopy(page_view["forms"]["prose"])
    bad_page["prose"]["validator_refs"] = ["print.not_registered"]
    assert (
        derive_print_block_candidates(
            block_id="b1",
            intent="explain",
            action=None,
            package_compatible=["prose"],
            policy=default_print_policy(),
            form_cards={"prose": {"supported_intents": ["explain"], "supported_actions": []}},
            writer_view=bad_page,
        ).excluded["prose"]
        == "unknown_validator_refs"
    )

    learn_caps = _read_json(LEARN_CONTRACTS / "learn-capabilities.v1.json")["capabilities"]
    learn_view = _read_json(LEARN_CONTRACTS / "learn-writer-view.v1.json")["capabilities"]
    bad_learn = copy.deepcopy(learn_view)
    bad_learn["choice"]["instructions"]["text"] = ""
    assert (
        derive_learn_block_candidates(
            block_id="b1",
            intent="check-understanding",
            action="select-one",
            capabilities=learn_caps,
            policy=default_learn_policy(),
            writer_view=bad_learn,
        ).excluded["choice"]
        == "missing_instructions"
    )
    bad_learn["choice"] = copy.deepcopy(learn_view["choice"])
    bad_learn["choice"]["validator_refs"] = ["learn.notRegistered"]
    assert (
        derive_learn_block_candidates(
            block_id="b1",
            intent="check-understanding",
            action="select-one",
            capabilities=learn_caps,
            policy=default_learn_policy(),
            writer_view=bad_learn,
        ).excluded["choice"]
        == "unknown_validator_refs"
    )


def test_a01_instruction_and_schema_changes_alter_definition_hashes() -> None:
    page_card = _read_json(PAGE_CONTRACTS / "form-writer-view.v1.json")["forms"]["prose"]
    page_instruction = copy.deepcopy(page_card)
    page_instruction["instructions"]["text"] += "\nA01 hash proof."
    assert _form_contract_hash("prose", page_instruction) != _form_contract_hash("prose", page_card)
    page_schema = copy.deepcopy(page_card)
    page_schema["payload_schema"]["description"] = "A01 schema hash proof"
    assert _form_contract_hash("prose", page_schema) != _form_contract_hash("prose", page_card)

    learn_card = _read_json(LEARN_CONTRACTS / "learn-writer-view.v1.json")["capabilities"]["choice"]
    learn_instruction = copy.deepcopy(learn_card)
    learn_instruction["instructions"]["text"] += "\nA01 hash proof."
    assert _capability_contract_hash("choice", learn_instruction) != _capability_contract_hash(
        "choice", learn_card
    )
    learn_schema = copy.deepcopy(learn_card)
    learn_schema["payload_schema"]["description"] = "A01 schema hash proof"
    assert _capability_contract_hash("choice", learn_schema) != _capability_contract_hash(
        "choice", learn_card
    )
