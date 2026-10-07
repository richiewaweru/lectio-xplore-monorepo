"""Repeated slots (confront per misconception) carry unique instance ids end to end."""

from __future__ import annotations

import pytest

from application.unit_lesson.teaching_plan_service import slot_ids_from_structural_plan
from curriculum.planning.skeletons import SkeletonPreviewRequest
from curriculum.planning.skeletons import load_skeleton_catalog
from curriculum.teaching_plan.instance_ids import (
    assign_slot_instance_ids,
    catalog_slot_key,
    normalize_slot_instance_ids,
)
from curriculum.teaching_plan.models import TeachingPlanDraftBlock, materialize_teaching_plan
from curriculum.teaching_plan.staged import (
    TeachingSpineDraft,
    assemble_teaching_plan_draft,
    materialize_teaching_spine,
)
from print.generation.whole_lesson.legality import build_lesson_legality_snapshot
from print.generation.whole_lesson.packet_builder import build_lesson_packet
from tests.planning.test_staged_sections import _block
from tests.planning.test_staged_spine import _section

REPEATED = ("orient", "explain", "contrast", "confront-1", "confront-2", "check")


def _packet(slot_ids):
    return build_lesson_packet(
        path_lesson_id="lesson-1",
        subject="Science",
        grade_level="Grade 4",
        objective="Explain why plants need light.",
        knowledge_type="conceptual",
        lesson_mode="first_exposure",
        must_establish=["Light is required."],
        must_not_introduce=[],
        terminology=["light"],
        anchor_id="anchor-1",
        anchor_description="Two plants",
        misconceptions=[],
        prior_established=[],
        approved_items=[],
        slot_ids=slot_ids,
    )


def test_two_high_risk_misconceptions_yield_unique_confront_instances() -> None:
    preview = load_skeleton_catalog().preview(
        SkeletonPreviewRequest(
            objective="Explain why plants need light.",
            lesson_mode="first_exposure",
            misconception_count=2,
            group_profiles=["core"],
        ),
        knowledge_type="conceptual",
    )
    roles = [slot.slot_id for slot in preview.variants[0].slots]
    assert roles.count("confront") == 2
    ids = assign_slot_instance_ids(roles)
    assert len(set(ids)) == len(ids)
    assert [i for i in ids if i.startswith("confront")] == ["confront-1", "confront-2"]


def test_repeated_roles_become_unique_instance_ids() -> None:
    plan = {"sections": [{"role": "orient"}, {"role": "confront"}, {"role": "confront"}, {"role": "check"}]}
    assert slot_ids_from_structural_plan(plan) == ("orient", "confront", "confront-2", "check")


def test_packet_resolves_catalogue_by_role_and_rejects_duplicates() -> None:
    packet = _packet(REPEATED)
    by_id = {slot.slot_id: slot for slot in packet.slots}
    assert [slot.slot_id for slot in packet.slots] == list(REPEATED)
    base = _packet(("confront",)).slots[0]
    for sid in ("confront-1", "confront-2"):
        assert by_id[sid].purpose == base.purpose
        assert by_id[sid].typical_intents == base.typical_intents
        assert by_id[sid].typical_intents  # not an empty fallback
    # Duplicates are normalised, never rejected (any slot type).
    dup = _packet(("orient", "guided", "guided", "confront", "confront", "check"))
    assert [s.slot_id for s in dup.slots] == [
        "orient", "guided", "guided-2", "confront", "confront-2", "check",
    ]
    assert dup.slots[2].typical_intents == dup.slots[1].typical_intents
    assert dup.slots[2].purpose == dup.slots[1].purpose


def test_legality_for_instance_resolves_to_role_rules() -> None:
    catalog = load_skeleton_catalog()
    assert catalog_slot_key(catalog.slots, "confront-2") == "confront"
    assert catalog_slot_key(catalog.slots, "confront") == "confront"
    snapshot = build_lesson_legality_snapshot(_packet(REPEATED))
    assert snapshot.typical_by_slot["confront-1"] == snapshot.typical_by_slot["confront-2"]
    assert snapshot.typical_by_slot["confront-2"]


def test_staged_spine_and_assembly_accept_repeated_instances() -> None:
    slots = ["orient", "confront-1", "confront-2", "check"]
    draft = TeachingSpineDraft.model_validate(
        {
            "learner_title": "Area of rectangles",
            "arc": "From counting squares to length times width.",
            "starting_state": ["Learners know multiplication"],
            "target_state": ["Learners compute rectangle area"],
            "misconception_focus_ids": ["m1"],
            "sections": [
                _section("Orient", ["a"], ["b"], first=True),
                _section("Confront one", ["b"], ["c"]),
                _section("Confront two", ["c"], ["d"]),
                _section("Check", ["d"], ["e"]),
            ],
        }
    )
    spine = materialize_teaching_spine(draft, slot_ids=slots, item_backbone_refs={})
    assert [s.slot_id for s in spine.sections] == slots
    blocks = {
        slot: [TeachingPlanDraftBlock.model_validate(_block("explain-cause")) for _ in range(2)]
        for slot in slots
    }
    assembled = assemble_teaching_plan_draft(spine, blocks)
    assert [a.slot_id for a in assembled.anchor_usage] == slots
    plan = materialize_teaching_plan(assembled, slot_ids=slots)
    section_ids = [s.slot_id for s in plan.sections]
    assert section_ids == slots
    block_ids = [b.id for s in plan.sections for b in s.blocks]
    assert len(set(block_ids)) == len(block_ids)


def test_normalize_is_stable_and_handles_any_repeated_type() -> None:
    assert normalize_slot_instance_ids(["orient", "check"]) == ["orient", "check"]
    assert normalize_slot_instance_ids(["orient", "guided", "guided", "guided", "check"]) == [
        "orient", "guided", "guided-2", "guided-3", "check",
    ]
    # Never collides with an id that already exists.
    assert normalize_slot_instance_ids(["guided", "guided", "guided-2"]) == [
        "guided", "guided-3", "guided-2",
    ]


def test_staged_flow_with_repeated_non_confront_type_and_duplicate_ids() -> None:
    # Even raw duplicate ids from a legacy caller flow through, uniquely keyed.
    raw = ["orient", "guided", "guided", "check"]
    draft = TeachingSpineDraft.model_validate(
        {
            "learner_title": "Area of rectangles",
            "arc": "From counting squares to length times width.",
            "starting_state": ["Learners know multiplication"],
            "target_state": ["Learners compute rectangle area"],
            "misconception_focus_ids": ["m1"],
            "sections": [
                _section("Orient", ["a"], ["b"], first=True),
                _section("Guided one", ["b"], ["c"]),
                _section("Guided two", ["c"], ["d"]),
                _section("Check", ["d"], ["e"]),
            ],
        }
    )
    spine = materialize_teaching_spine(draft, slot_ids=raw, item_backbone_refs={})
    ids = [s.slot_id for s in spine.sections]
    assert ids == ["orient", "guided", "guided-2", "check"]
    blocks = {
        slot: [TeachingPlanDraftBlock.model_validate(_block("explain-cause")) for _ in range(2)]
        for slot in ids
    }
    assembled = assemble_teaching_plan_draft(spine, blocks)
    plan = materialize_teaching_plan(assembled, slot_ids=raw)
    assert [s.slot_id for s in plan.sections] == ids
    packet = _packet(ids)
    assert [s.slot_id for s in packet.slots] == ids
    typical = build_lesson_legality_snapshot(packet).typical_by_slot
    assert typical["guided-2"] == typical["guided"]
