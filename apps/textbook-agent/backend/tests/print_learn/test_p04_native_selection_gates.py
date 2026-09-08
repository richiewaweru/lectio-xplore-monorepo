"""P04 native selection, validation, work-order and policy gates."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from curriculum.teaching_plan.compatibility import ActionSourceIncompatibleError
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from learn.generation.activity_authoring import plan_activity_authoring
from learn.generation.native_selection import (
    LearnSelectionDecision,
    SelectionError as LearnSelectionError,
    build_learn_selection_snapshot,
    rank_learn_interaction_candidates,
    select_learn_deterministically,
    select_learn_first_legal,
    validate_learn_selection,
)
from learn.generation.work_orders import (
    WriterRequestLeakError as LearnWriterLeakError,
    build_learn_writer_request,
    compile_learn_work_orders,
)
from learn.resources.native_policy import (
    default_learn_policy,
    policy_version_and_hash as learn_policy_hash,
)
from learn.resources.selection import (
    NoCompatibleLearnCapabilityError,
    build_learn_candidate_map,
    derive_learn_block_candidates,
)
from print.generation.selection_snapshot import (
    PrintSelectionDecision,
    SelectionError as PrintSelectionError,
    build_print_selection_snapshot,
    validate_print_selection,
)
from print.generation.work_orders import (
    WriterRequestLeakError as PrintWriterLeakError,
    build_print_writer_request,
    compile_print_work_orders,
    decisions_cover_teaching_plan,
)
from print.resources.native_policy import (
    default_print_policy,
    policy_version_and_hash as print_policy_hash,
)
from print.resources.selection import (
    NoCompatiblePrintCapabilityError,
    build_print_candidate_map,
    derive_print_block_candidates,
)


def _plan(*blocks: TeachingPlanBlock, plan_id: str = "tp-p04", revision: int = 1) -> TeachingPlan:
    return TeachingPlan(
        arc="P04 native selection fixture",
        teaching_plan_id=plan_id,
        revision=revision,
        sections=[
            TeachingPlanSection(
                slot_id="orient",
                specific_purpose="fixture",
                blocks=list(blocks),
            )
        ],
    )


def _block(
    block_id: str,
    *,
    intent: str,
    brief: str = "Brief",
    action: str | None = None,
    support: str = "guided",
    evidence: str = "Evidence of understanding",
    source_question_ids: list[str] | None = None,
    dependencies: list[str] | None = None,
    position: int = 0,
) -> TeachingPlanBlock:
    learner = None
    if action is not None:
        learner = LearnerActionBrief(
            action=action,
            support_level=support,  # type: ignore[arg-type]
            evidence=evidence,
            source_item_ids=list(source_question_ids or []),
            dependencies=list(dependencies or []),
        )
    return TeachingPlanBlock(
        id=block_id,
        position=position,
        intent=intent,
        brief=brief,
        evidence=evidence,
        source_question_ids=list(source_question_ids or []),
        learner_action=learner,
    )


# ---------------------------------------------------------------------------
# P04-N01
# ---------------------------------------------------------------------------


def test_p04_n01_compare_without_response_and_sequence() -> None:
    """Compare-without-response selects content only; order-items can select Sequence."""
    compare = _block(
        "b-compare",
        intent="compare",
        brief="Compare before/after without answering",
        action="compare-without-response",
    )
    order = _block(
        "b-order",
        intent="sequence",
        brief="Put the stages in order",
        action="order-items",
        support="independent",
        position=1,
    )
    # Gate synonym reconstruct-order also resolves to Sequence eligibility.
    reconstruct = _block(
        "b-reconstruct",
        intent="sequence",
        brief="Reconstruct the order",
        action="reconstruct-order",
        support="independent",
        position=2,
    )
    plan = TeachingPlan(
        arc="N01",
        teaching_plan_id="tp-n01",
        revision=1,
        sections=[
            TeachingPlanSection(slot_id="orient", specific_purpose="compare", blocks=[compare]),
            TeachingPlanSection(slot_id="apply", specific_purpose="order", blocks=[order, reconstruct]),
        ],
    )

    candidates, decisions = select_learn_deterministically(plan)
    by_id = {item.block_id: item for item in decisions}

    assert candidates["b-compare"].requires_response is False
    assert by_id["b-compare"].interaction_id is None
    assert by_id["b-compare"].content_id is not None
    assert "sequence" in candidates["b-order"].interaction_candidates
    assert by_id["b-order"].interaction_id == "sequence"
    assert "sequence" in candidates["b-reconstruct"].interaction_candidates
    assert by_id["b-reconstruct"].interaction_id == "sequence"


# ---------------------------------------------------------------------------
# P04-N02
# ---------------------------------------------------------------------------


def test_p04_n02_selection_errors_are_attributable() -> None:
    block = _block("b1", intent="explain", action="read-explanation")
    plan = _plan(block)
    candidates = build_learn_candidate_map(plan, fail_on_empty_required=False)
    legal_content = list(candidates["b1"].content_candidates)
    assert legal_content, "fixture needs at least one legal content candidate"

    with pytest.raises(LearnSelectionError) as out_of_set:
        validate_learn_selection(
            teaching_plan=plan,
            decisions=[
                LearnSelectionDecision(
                    block_id="b1",
                    content_id="NOT_IN_CANDIDATE_SET_zz9",
                    interaction_id=None,
                )
            ],
            candidate_map=candidates,
        )
    assert out_of_set.value.code == "OUT_OF_SET"

    with pytest.raises(LearnSelectionError) as missing:
        validate_learn_selection(
            teaching_plan=plan,
            decisions=[],
            candidate_map=candidates,
        )
    assert missing.value.code == "MISSING_BLOCK"

    with pytest.raises(LearnSelectionError) as duplicate:
        validate_learn_selection(
            teaching_plan=plan,
            decisions=[
                LearnSelectionDecision(block_id="b1", content_id=legal_content[0]),
                LearnSelectionDecision(block_id="b1", content_id=legal_content[0]),
            ],
            candidate_map=candidates,
        )
    assert duplicate.value.code == "DUPLICATE_BLOCK"

    with pytest.raises(LearnSelectionError) as altered:
        validate_learn_selection(
            teaching_plan=plan,
            decisions=[LearnSelectionDecision(block_id="b1", content_id=legal_content[0])],
            candidate_map=candidates,
            expected_teaching_plan_id="other-id",
        )
    assert altered.value.code == "ALTERED_TEACHING_IDENTITY"

    # Print path mirrors the same attributable codes.
    print_candidates = {"b1": ("prose", "list")}
    with pytest.raises(PrintSelectionError) as print_oos:
        validate_print_selection(
            teaching_plan=plan,
            decisions=[PrintSelectionDecision(block_id="b1", form_id="figure")],
            candidate_map=print_candidates,
        )
    assert print_oos.value.code == "OUT_OF_SET"


# ---------------------------------------------------------------------------
# P04-N03
# ---------------------------------------------------------------------------


def test_p04_n03_optional_none_and_required_incompatibility() -> None:
    optional = _block(
        "b-opt",
        intent="explain",
        action="read-explanation",
    )
    plan_opt = _plan(optional, plan_id="tp-n03-opt")
    # Empty optional interaction set → explicit none (no invented activity).
    policy = default_learn_policy()
    policy["offered_interactions"] = []
    candidates, decisions = select_learn_deterministically(plan_opt, policy=policy)
    assert candidates["b-opt"].interaction_candidates == ()
    assert decisions[0].interaction_id is None
    assert decisions[0].content_id is not None

    required = _block(
        "b-req",
        intent="sequence",
        action="order-items",
        support="independent",
    )
    plan_req = _plan(required, plan_id="tp-n03-req")
    empty_required_policy = default_learn_policy()
    empty_required_policy["offered_interactions"] = []
    with pytest.raises(NoCompatibleLearnCapabilityError) as exc:
        build_learn_candidate_map(plan_req, policy=empty_required_policy)
    assert exc.value.code == "NO_COMPATIBLE_CAPABILITY"
    assert exc.value.block_id == "b-req"
    assert "interaction" in exc.value.reason or "compatible" in exc.value.reason


# ---------------------------------------------------------------------------
# P04-N04
# ---------------------------------------------------------------------------


def test_p04_n04_writer_requests_exclude_sibling_schemas() -> None:
    compare = _block(
        "b-c",
        intent="compare",
        action="compare-without-response",
    )
    order = _block(
        "b-o",
        intent="sequence",
        action="order-items",
        support="independent",
        position=1,
    )
    plan = TeachingPlan(
        arc="N04",
        teaching_plan_id="tp-n04",
        revision=1,
        sections=[
            TeachingPlanSection(slot_id="orient", specific_purpose="c", blocks=[compare]),
            TeachingPlanSection(slot_id="apply", specific_purpose="o", blocks=[order]),
        ],
    )
    _, learn_hash = learn_policy_hash()
    snap = build_learn_selection_snapshot(
        plan,
        teaching_plan_hash="hash-n04",
        native_policy_hash=learn_hash,
        package_contract_hash="pkg-learn",
    )
    orders = compile_learn_work_orders(teaching_plan=plan, snapshot=snap)
    assert orders
    sibling_sentinel = "SIBLING_PAYLOAD_SCHEMA_SENTINEL_p04n04_zz9"
    for order in orders:
        request = build_learn_writer_request(
            order,
            allowed_facts=["chlorophyll absorbs light"],
            terminology=["chlorophyll"],
            sibling_sentinels={
                "sibling_payload_schema": {sibling_sentinel: {"x": 1}},
                "full_catalogue": ["choice", "sequence", "prose"],
            },
        )
        blob = json.dumps(request)
        assert sibling_sentinel not in blob
        assert "full_catalogue" not in blob
        assert "sibling_payload_schema" not in blob
        assert request["payload_schema"]
        assert request["capability_id"] == order.capability_id
        with pytest.raises(LearnWriterLeakError):
            # Deliberately polluted request must fail the leak assertion.
            polluted = dict(request)
            polluted["sibling_payload_schema"] = {"leak": True}
            from learn.generation.work_orders import assert_no_sibling_schema_leak

            assert_no_sibling_schema_leak(
                polluted, selected_capability_id=order.capability_id
            )

    # Print writer path
    print_plan = _plan(
        _block("bp", intent="explain", action="read-explanation"),
        plan_id="tp-n04-print",
    )
    print_candidates = build_print_candidate_map(
        print_plan,
        compatible_objects_by_intent={"explain": ("prose", "list", "aside")},
        fail_on_empty_required=True,
    )
    _, print_hash = print_policy_hash()
    print_snap = build_print_selection_snapshot(
        print_plan,
        candidate_map=print_candidates,
        teaching_plan_hash="hash-n04-p",
        native_policy_hash=print_hash,
        package_contract_hash="pkg-page",
    )
    print_orders = compile_print_work_orders(teaching_plan=print_plan, snapshot=print_snap)
    assert print_orders
    req = build_print_writer_request(
        print_orders[0],
        allowed_facts=["fact-a"],
        sibling_sentinels={"sibling_payload_schema": {sibling_sentinel: 1}},
    )
    assert sibling_sentinel not in json.dumps(req)
    with pytest.raises(PrintWriterLeakError):
        from print.generation.work_orders import assert_no_sibling_schema_leak as print_leak

        print_leak(
            {**req, "full_catalogue": True},
            selected_form_id=print_orders[0].form_id,
        )


# ---------------------------------------------------------------------------
# P04-N05
# ---------------------------------------------------------------------------


def test_p04_n05_coverage_dependencies_and_assets() -> None:
    upstream = _block(
        "b-up",
        intent="explain",
        action="read-explanation",
        brief="Teach the process",
    )
    dependent = _block(
        "b-dep",
        intent="sequence",
        action="order-items",
        support="independent",
        dependencies=["asset-process-diagram"],
        position=1,
    )
    plan = TeachingPlan(
        arc="N05",
        teaching_plan_id="tp-n05",
        revision=1,
        sections=[
            TeachingPlanSection(slot_id="orient", specific_purpose="up", blocks=[upstream]),
            TeachingPlanSection(slot_id="apply", specific_purpose="dep", blocks=[dependent]),
        ],
    )
    _, learn_hash = learn_policy_hash()
    snap = build_learn_selection_snapshot(
        plan,
        teaching_plan_hash="hash-n05",
        native_policy_hash=learn_hash,
        package_contract_hash="pkg",
    )
    assert {d.block_id for d in snap.decisions} == {"b-up", "b-dep"}
    dep_decision = next(d for d in snap.decisions if d.block_id == "b-dep")
    assert "asset-process-diagram" in dep_decision.dependency_ids
    orders = compile_learn_work_orders(teaching_plan=plan, snapshot=snap)
    assert {o.block_id for o in orders} >= {"b-up", "b-dep"}
    assert any("asset-process-diagram" in o.dependency_ids for o in orders)

    # Unsupported / missing assets prevent premature selection of asset-gated caps.
    derived = derive_learn_block_candidates(
        block_id="hotspot",
        intent="locate",
        action="identify-region",
        available_asset_ids=[],
        policy={
            **default_learn_policy(),
            "offered_interactions": ["image-hotspot"],
            "denied_capabilities": [],
            "require_assets_for": ["image-hotspot"],
        },
    )
    assert "image-hotspot" not in derived.interaction_candidates
    assert derived.excluded.get("image-hotspot") in {
        "asset_unavailable",
        "not_in_native_policy",
        "package_unavailable",
        "intent_unsupported",
        "action_unsupported",
    }

    # Print coverage
    print_plan = plan
    print_candidates = {
        "b-up": ("prose",),
        "b-dep": ("list",),
    }
    decisions = [
        PrintSelectionDecision(block_id="b-up", form_id="prose"),
        PrintSelectionDecision(block_id="b-dep", form_id="list"),
    ]
    decisions_cover_teaching_plan(print_plan, decisions)
    figure = derive_print_block_candidates(
        block_id="fig",
        intent="show-structure",
        action=None,
        package_compatible=["figure", "prose"],
        available_asset_ids=[],
    )
    assert "figure" not in figure.candidates
    assert figure.excluded.get("figure") == "asset_unavailable"


# ---------------------------------------------------------------------------
# P04-N06
# ---------------------------------------------------------------------------


def test_p04_n06_policy_change_shifts_eligibility_without_component_edits() -> None:
    block = _block(
        "b-seq",
        intent="sequence",
        action="order-items",
        support="independent",
    )
    plan = _plan(block, plan_id="tp-n06")

    baseline = derive_learn_block_candidates(
        block_id=block.id,
        intent=block.intent,
        action=block.learner_action.action if block.learner_action else None,
    )
    assert "sequence" in baseline.interaction_candidates

    narrowed = copy.deepcopy(default_learn_policy())
    narrowed["offered_interactions"] = [
        item for item in narrowed["offered_interactions"] if item != "sequence"
    ]
    after = derive_learn_block_candidates(
        block_id=block.id,
        intent=block.intent,
        action=block.learner_action.action if block.learner_action else None,
        policy=narrowed,
    )
    assert "sequence" not in after.interaction_candidates
    assert after.excluded.get("sequence") == "not_in_native_policy"

    # Print policy change likewise — no object-catalogue edits.
    print_base = derive_print_block_candidates(
        block_id="bp",
        intent="explain",
        action="read-explanation",
        package_compatible=["prose", "aside", "list"],
    )
    assert "prose" in print_base.candidates
    print_narrow = default_print_policy()
    print_narrow["denied_forms"] = list(print_narrow.get("denied_forms") or []) + ["prose"]
    print_after = derive_print_block_candidates(
        block_id="bp",
        intent="explain",
        action="read-explanation",
        package_compatible=["prose", "aside", "list"],
        policy=print_narrow,
    )
    assert "prose" not in print_after.candidates
    assert print_after.excluded.get("prose") == "not_in_native_policy"


def test_p04_activity_authoring_rejects_incompatible_approved_type() -> None:
    """Incompatible approved task type → explicit error, not silent rewrite."""
    block = _block(
        "b-mcq",
        intent="check-understanding",
        action="order-items",
        support="independent",
        source_question_ids=["item-mcq-1"],
    )
    plan = _plan(block, plan_id="tp-auth")
    # Force a selection that would try to consume the MCQ under an ordering action.
    candidates = build_learn_candidate_map(plan, fail_on_empty_required=False)
    content = candidates["b-mcq"].content_candidates[:1]
    interaction = candidates["b-mcq"].interaction_candidates[:1]
    if not interaction:
        pytest.skip("no interaction candidate for order-items under current policy")
    decision = LearnSelectionDecision(
        block_id="b-mcq",
        content_id=content[0] if content else None,
        interaction_id=interaction[0],
        source_item_ids=["item-mcq-1"],
    )
    # Bypass auto-select; seal a snapshot with the explicit decision.
    from learn.generation.native_selection import LearnSelectionSnapshot, candidate_map_payload

    snap = LearnSelectionSnapshot(
        teaching_plan_id="tp-auth",
        teaching_plan_revision=1,
        teaching_plan_hash="h",
        native_policy_hash="p",
        package_contract_hash="c",
        candidate_map=candidate_map_payload(candidates),
        decisions=[decision],
    ).seal()
    mcq = SimpleNamespace(id="item-mcq-1", options=({"key": "A", "text": "x"},), stem="Stem")
    with pytest.raises(ActionSourceIncompatibleError):
        compile_learn_work_orders(teaching_plan=plan, snapshot=snap, approved_items=[mcq])

    # New activity path without sources is fine.
    open_block = _block(
        "b-new",
        intent="sequence",
        action="order-items",
        support="independent",
    )
    open_plan = _plan(open_block, plan_id="tp-auth-new")
    _, learn_hash = learn_policy_hash()
    open_snap = build_learn_selection_snapshot(
        open_plan,
        teaching_plan_hash="h2",
        native_policy_hash=learn_hash,
        package_contract_hash="c",
    )
    orders = compile_learn_work_orders(teaching_plan=open_plan, snapshot=open_snap)
    interaction_orders = [o for o in orders if o.lane == "interaction"]
    assert interaction_orders
    plan_out = plan_activity_authoring(interaction_orders[0], approved_items=[])
    assert plan_out.mode == "new"


# ---------------------------------------------------------------------------
# Corrective round — no fabricated actions / no Sequence bias
# ---------------------------------------------------------------------------


def test_p04_omitted_learner_action_does_not_fabricate_order_items() -> None:
    """Missing learner_action stays missing; no INTENT_ACTION_DEFAULTS invent order-items."""
    block = _block("b-seq-no-action", intent="sequence")
    derived = derive_learn_block_candidates(
        block_id=block.id,
        intent=block.intent,
        action=None,
    )
    assert derived.action is None
    assert derived.requires_response is False
    assert derived.interaction_candidates == ()
    assert "sequence" not in derived.interaction_candidates
    # Do not invent an interaction; empty dual shortlist fails closed when selecting.
    plan = _plan(block, plan_id="tp-seq-no-action")
    with pytest.raises(NoCompatibleLearnCapabilityError):
        select_learn_deterministically(plan)


def test_p04_practise_guided_without_action_is_not_forced_onto_sequence() -> None:
    block = _block("b-pg", intent="practise-guided")
    plan = _plan(block, plan_id="tp-pg-no-action")
    candidates, decisions = select_learn_deterministically(plan)
    assert candidates["b-pg"].action is None
    assert candidates["b-pg"].requires_response is False
    assert decisions[0].interaction_id is None
    assert decisions[0].content_id is not None
    assert "sequence" not in candidates["b-pg"].interaction_candidates


def test_p04_required_action_empty_interaction_set_fails_closed() -> None:
    """Required response with empty interaction set cannot silently become content."""
    required = _block(
        "b-req-empty",
        intent="sequence",
        action="order-items",
        support="independent",
    )
    plan = _plan(required, plan_id="tp-req-empty")
    policy = default_learn_policy()
    policy["offered_interactions"] = []
    with pytest.raises(NoCompatibleLearnCapabilityError) as exc:
        select_learn_deterministically(plan, policy=policy)
    assert exc.value.code == "NO_COMPATIBLE_CAPABILITY"
    # Even candidate derivation with fail_on_empty_required must not invent content-as-response.
    derived = derive_learn_block_candidates(
        block_id=required.id,
        intent=required.intent,
        action="order-items",
        policy=policy,
    )
    assert derived.requires_response is True
    assert derived.interaction_candidates == ()


def test_p04_out_of_set_and_unavailable_ids_stay_excluded() -> None:
    derived = derive_learn_block_candidates(
        block_id="b-spatial",
        intent="name-parts",
        action="identify-region",
    )
    assert "image-hotspot" not in derived.interaction_candidates
    assert "drag-label" not in derived.interaction_candidates
    # Unavailable package ids remain excluded even if policy somehow lists them.
    policy = default_learn_policy()
    policy["offered_interactions"] = list(policy["offered_interactions"]) + [
        "image-hotspot",
        "drag-label",
        "not-a-real-capability",
    ]
    again = derive_learn_block_candidates(
        block_id="b-spatial-2",
        intent="name-parts",
        action="place-labels",
        policy=policy,
    )
    assert "image-hotspot" not in again.interaction_candidates
    assert "drag-label" not in again.interaction_candidates
    assert "not-a-real-capability" not in again.interaction_candidates


def test_p04_sequence_not_auto_preferred_when_choice_also_legal() -> None:
    """When both choice and sequence are legal, Sequence is not writer-biased first."""
    # Closed shortlist with both; brief matches Choice choose_when cues.
    ranked = rank_learn_interaction_candidates(
        ["choice", "sequence"],
        brief="The response reduces to one option; pick the correct distractor set.",
        intent="check-understanding",
        action="select-one",
    )
    assert ranked[0] == "choice"
    assert ranked[-1] == "sequence"

    # Equal / weak guidance keeps shortlist order (choice before sequence) — no Sequence bump.
    tied = rank_learn_interaction_candidates(
        ["choice", "sequence"],
        brief="Learner checks understanding of the topic.",
        intent="check-understanding",
        action=None,
    )
    assert tied[0] == "choice"

    # first-legal helper also refuses Sequence bias.
    order = _block(
        "b-order",
        intent="sequence",
        action="order-items",
        support="independent",
    )
    # Inject dual candidates via a synthetic shortlist ranking check already covers
    # production; first-legal on a real order-items block still selects Sequence alone.
    _, first_decisions = select_learn_first_legal(_plan(order, plan_id="tp-first-legal"))
    assert first_decisions[0].interaction_id == "sequence"


def test_p04_n01_still_holds_via_first_legal_and_ranked() -> None:
    """N01: compare-without-response → content only; reconstruct-order can select Sequence."""
    compare = _block(
        "b-compare",
        intent="compare",
        brief="Compare before/after without answering",
        action="compare-without-response",
    )
    order = _block(
        "b-order",
        intent="sequence",
        brief="Put the stages in order; one defensible order of distinguishable stages.",
        action="order-items",
        support="independent",
        position=1,
    )
    reconstruct = _block(
        "b-reconstruct",
        intent="sequence",
        brief="Reconstruct the order",
        action="reconstruct-order",
        support="independent",
        position=2,
    )
    plan = TeachingPlan(
        arc="N01-corrective",
        teaching_plan_id="tp-n01-c",
        revision=1,
        sections=[
            TeachingPlanSection(slot_id="orient", specific_purpose="compare", blocks=[compare]),
            TeachingPlanSection(slot_id="apply", specific_purpose="order", blocks=[order, reconstruct]),
        ],
    )
    for selector in (select_learn_deterministically, select_learn_first_legal):
        candidates, decisions = selector(plan)
        by_id = {item.block_id: item for item in decisions}
        assert candidates["b-compare"].requires_response is False
        assert by_id["b-compare"].interaction_id is None
        assert by_id["b-compare"].content_id is not None
        assert "sequence" in candidates["b-order"].interaction_candidates
        assert by_id["b-order"].interaction_id == "sequence"
        assert "sequence" in candidates["b-reconstruct"].interaction_candidates
        assert by_id["b-reconstruct"].interaction_id == "sequence"
