"""Packet slots must follow the structural plan, not conceptual constants."""

from __future__ import annotations

from planning.whole_lesson.packet_builder import (
    CONCEPTUAL_FIRST_EXPOSURE_SLOTS,
    build_lesson_packet,
)
from planning.whole_lesson.service import slot_ids_from_structural_plan


def _packet_for_slots(slot_ids: tuple[str, ...]):
    return build_lesson_packet(
        path_lesson_id="lesson-1",
        subject="Science",
        grade_level="Grade 4",
        objective="Explain why plants need light to make food.",
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


def test_slot_ids_from_structural_plan_conceptual_yaml_order() -> None:
    # Repo skeleton conceptual.first_exposure includes contrast.
    plan = {
        "sections": [
            {"id": "orient", "role": "orient"},
            {"id": "explain", "role": "explain"},
            {"id": "contrast", "role": "contrast"},
            {"id": "confront", "role": "confront"},
            {"id": "check", "role": "check"},
        ]
    }
    expected = ("orient", "explain", "contrast", "confront", "check")
    assert slot_ids_from_structural_plan(plan) == expected
    packet = _packet_for_slots(slot_ids_from_structural_plan(plan) or CONCEPTUAL_FIRST_EXPOSURE_SLOTS)
    assert [slot.slot_id for slot in packet.slots] == list(expected)


def test_slot_ids_from_structural_plan_factual_order() -> None:
    plan = {
        "sections": [
            {"role": "orient"},
            {"role": "organise"},
            {"role": "guided"},
            {"role": "independent"},
            {"role": "check"},
        ]
    }
    expected = ("orient", "organise", "guided", "independent", "check")
    assert slot_ids_from_structural_plan(plan) == expected
    packet = _packet_for_slots(expected)
    assert [slot.slot_id for slot in packet.slots] == list(expected)


def test_slot_ids_from_structural_plan_procedural_skeleton_order() -> None:
    # procedural.first_exposure from skeletons.yaml
    plan = {
        "sections": [
            {"id": "orient", "role": "orient"},
            {"id": "recall", "role": "recall"},
            {"id": "model", "role": "model"},
            {"id": "guided", "role": "guided"},
            {"id": "check", "role": "check"},
        ]
    }
    expected = ("orient", "recall", "model", "guided", "check")
    assert slot_ids_from_structural_plan(plan) == expected
    packet = _packet_for_slots(expected)
    assert [slot.slot_id for slot in packet.slots] == list(expected)


def test_slot_ids_from_structural_plan_prefers_role_over_id() -> None:
    plan = {"sections": [{"id": "wrong", "role": "orient"}, {"id": "explain"}]}
    assert slot_ids_from_structural_plan(plan) == ("orient", "explain")


def test_empty_structural_plan_falls_back_to_conceptual_constant() -> None:
    assert slot_ids_from_structural_plan({}) == ()
    assert slot_ids_from_structural_plan(None) == ()
    packet = _packet_for_slots(() or CONCEPTUAL_FIRST_EXPOSURE_SLOTS)
    assert [slot.slot_id for slot in packet.slots] == list(CONCEPTUAL_FIRST_EXPOSURE_SLOTS)


def test_packet_slots_preserve_plan_order_not_alphabetical() -> None:
    # Deliberately non-alphabetical order must be preserved.
    expected = ("check", "orient", "guided", "organise", "independent")
    packet = _packet_for_slots(expected)
    assert [slot.slot_id for slot in packet.slots] == list(expected)
