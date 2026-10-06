"""Spine call: code checks, derivation, figure repair, retry, prompt."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from application.unit_lesson import staged_teaching_planner as stp
from curriculum.teaching_plan.staged import TeachingSpineDraft, materialize_teaching_spine
from print.generation.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    MisconceptionRecord,
    PriorEstablishedEntry,
    ScopeContract,
    SlotRecord,
)
from print.generation.whole_lesson.prompt_render import BACKBONE_TEACHING_GUIDANCE
from print.generation.whole_lesson.teaching_errors import TeachingPlanOutputInvalidError
from tests.planning.legality_fixtures import make_snapshot

BACKBONE = {
    "anchor": {"id": "anchor-1", "story": "A garden bed.", "data": {}, "figure_ids": ["fig-a"]},
    "variants": [{"id": "variant-1", "story": "A bigger bed.", "data": {}, "figure_ids": []}],
    "figures": [
        {
            "id": "fig-a",
            "purpose": "See the dimensions of the bed.",
            "must_show": ["a rectangle"],
            "labels_required": [],
            "data": {},
        }
    ],
}


def _packet(*, backbone: bool = True) -> ImmutableLessonPacket:
    packet = ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="l1",
            subject="Maths",
            grade_level="Grade 6",
            objective="Find the area of a rectangle.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["area"]),
        anchor=AnchorRecord(id="anchor-1", description="A garden bed"),
        misconceptions=[
            MisconceptionRecord(id="m1", statement="Area equals perimeter."),
            MisconceptionRecord(id="m2", statement="Units do not matter."),
        ],
        prior_established=[PriorEstablishedEntry(id="p1", statement="Multiplication facts")],
        approved_items=[
            ApprovedItemRef(id="q1", card_id="c", stem="Area of the bed?", correct_key="A"),
            ApprovedItemRef(id="q2", card_id="c", stem="Area of the big bed?", correct_key="B"),
        ],
        slots=[
            SlotRecord(slot_id="orient"),
            SlotRecord(slot_id="explain"),
            SlotRecord(slot_id="check"),
        ],
        required_assessment_slots=["check"],
        limits=LessonLimits(max_total_blocks=6),
    )
    if not backbone:
        return packet
    return packet.model_copy(
        update={
            "backbone": BACKBONE,
            "item_backbone_refs": {
                "q1": {"target": "anchor-1", "figure_id": "fig-a"},
                "q2": {"target": "variant-1", "figure_id": None},
            },
        }
    )


def _section(title: str, entry: list[str], exit_: list[str], *, first=False, **kw) -> dict:
    data = {
        "display_title": title,
        "specific_purpose": f"{title} purpose",
        "entry_state": entry,
        "must_establish": [f"{title} idea"],
        "avoid_repeating": [],
        "bridge_from_previous": None if first else f"From before to {title}",
        "exit_state": exit_,
        "anchor_usage": "uses the bed",
        "planned_block_count": 2,
    }
    data.update(kw)
    return data


def _draft_dict(**overrides: Any) -> dict:
    data = {
        "learner_title": "Area of rectangles",
        "arc": "From counting squares to length times width.",
        "starting_state": ["Learners know multiplication"],
        "target_state": ["Learners compute rectangle area"],
        "misconception_focus_ids": ["m1"],
        "sections": [
            _section("Orient", ["Multiplication facts"], ["squares cover surfaces"], first=True,
                     misconception_ids=["m1"]),
            _section("Explain", ["squares cover surfaces"], ["area equals length times width"]),
            _section("Check", ["area equals length times width"], ["area computed"],
                     approved_item_ids=["q1", "q2"]),
        ],
    }
    data.update(overrides)
    return TeachingSpineDraft.model_validate(data)


def _spine(draft: TeachingSpineDraft | None = None, packet: ImmutableLessonPacket | None = None):
    packet = packet or _packet()
    return materialize_teaching_spine(
        draft or _draft_dict(),
        slot_ids=[s.slot_id for s in packet.slots],
        item_backbone_refs=packet.item_backbone_refs,
    ), packet


def _codes(errors: list[str]) -> set[str]:
    return {e.split(":", 1)[0] for e in errors}


def _mutated(mutate) -> TeachingSpineDraft:
    draft = _draft_dict().model_dump(mode="json")
    mutate(draft)
    return TeachingSpineDraft.model_validate(draft)


def test_good_spine_has_no_errors() -> None:
    spine, packet = _spine()
    assert stp.spine_check_errors(spine, packet) == []


def test_variant_targets_derived_from_items() -> None:
    spine, _ = _spine()
    assert spine.sections[0].backbone_targets == ["anchor-1"]
    assert spine.sections[2].backbone_targets == ["anchor-1", "variant-1"]


def test_section_count_check_via_spine_object() -> None:
    spine, packet = _spine()
    short = spine.model_copy(update={"sections": spine.sections[:2]})
    assert "SPINE_SECTION_COUNT" in _codes(stp.spine_check_errors(short, packet))


def test_state_chain_between_sections_is_repaired_not_an_error() -> None:
    def bad(d):
        d["sections"][1]["entry_state"] = ["quantum chromodynamics"]

    spine, packet = _spine(_mutated(bad))
    assert stp.spine_check_errors(spine, packet) == []
    changes = stp.repair_spine_state_chain(spine, packet)
    assert [c["repair"] for c in changes] == ["spine_state_chain"]
    assert changes[0]["slot_id"] == spine.sections[1].slot_id
    assert changes[0]["from_slot_id"] == spine.sections[0].slot_id
    assert "quantum chromodynamics" in spine.sections[0].exit_state
    # Idempotent once repaired.
    assert stp.repair_spine_state_chain(spine, packet) == []


def test_state_chain_section_zero_uses_starting_state_and_prior() -> None:
    def from_prior(d):
        d["starting_state"] = ["Learners are ready"]
        d["sections"][0]["entry_state"] = ["Multiplication facts"]  # in prior_established

    spine, packet = _spine(_mutated(from_prior))
    assert stp.repair_spine_state_chain(spine, packet) == []

    def bad(d):
        d["starting_state"] = ["Learners are ready"]
        d["sections"][0]["entry_state"] = ["Volume of cylinders"]

    spine, packet = _spine(_mutated(bad))
    changes = stp.repair_spine_state_chain(spine, packet)
    assert changes[0]["appended_to"] == "starting_state"
    assert "Volume of cylinders" in spine.starting_state
    assert stp.spine_check_errors(spine, packet) == []


def test_item_checks() -> None:
    def unknown(d):
        d["sections"][2]["approved_item_ids"] = ["q1", "q2", "zzz"]

    assert "SPINE_ITEM_UNKNOWN" in _codes(stp.spine_check_errors(*_spine(_mutated(unknown))))

    def duplicate(d):
        d["sections"][2]["approved_item_ids"] = ["q1", "q2"]
        d["sections"][1]["approved_item_ids"] = ["q1"]

    codes = _codes(stp.spine_check_errors(*_spine(_mutated(duplicate))))
    assert {"SPINE_ITEM_DUPLICATE", "SPINE_ITEM_OUTSIDE_ASSESSMENT_SLOT"} <= codes

    def unplaced(d):
        d["sections"][2]["approved_item_ids"] = ["q1"]

    # Selection is optional: leaving an approved item unplaced is legal.
    assert _codes(stp.spine_check_errors(*_spine(_mutated(unplaced)))) == set()

    def too_many(d):
        d["sections"][2]["planned_block_count"] = 1

    assert _codes(stp.spine_check_errors(*_spine(_mutated(too_many)))) == {
        "SPINE_ITEM_BLOCK_BUDGET"
    }

    def empty(d):
        d["sections"][2]["approved_item_ids"] = []
        d["sections"][1]["approved_item_ids"] = ["q1", "q2"]

    codes = _codes(stp.spine_check_errors(*_spine(_mutated(empty))))
    assert "SPINE_ASSESSMENT_SLOT_EMPTY" in codes
    assert "SPINE_ITEM_OUTSIDE_ASSESSMENT_SLOT" in codes


def test_items_per_section_bounded_by_block_maximum_not_total() -> None:
    # The real-run failure: more items than the check section has blocks.
    def crowded(d):
        d["sections"][2]["planned_block_count"] = 1
        d["sections"][2]["approved_item_ids"] = ["q1"]

    spine, packet = _spine(_mutated(crowded))
    assert stp.spine_check_errors(spine, packet) == []


def test_block_budget_sums_maxima() -> None:
    def over(d):
        for section in d["sections"]:
            section["planned_block_count"] = 3

    codes = _codes(stp.spine_check_errors(*_spine(_mutated(over))))
    assert "SPINE_BLOCK_BUDGET" in codes


def test_items_may_go_anywhere_without_required_slots() -> None:
    spine, packet = _spine()
    packet = packet.model_copy(update={"required_assessment_slots": []})
    assert stp.spine_check_errors(spine, packet) == []


def test_misconception_checks() -> None:
    def unknown(d):
        d["sections"][0]["misconception_ids"] = ["m1", "nope"]
        d["misconception_focus_ids"] = ["m1", "nope2"]

    errors = stp.spine_check_errors(*_spine(_mutated(unknown)))
    assert _codes(errors) == {"SPINE_MISCONCEPTION_UNKNOWN"}
    assert len(errors) == 2

    def unassigned(d):
        d["misconception_focus_ids"] = ["m1", "m2"]

    assert _codes(stp.spine_check_errors(*_spine(_mutated(unassigned)))) == {
        "SPINE_MISCONCEPTION_UNASSIGNED"
    }


def test_figure_unknown_and_no_backbone() -> None:
    def bad(d):
        d["sections"][1]["figure_plan"] = [{"purpose": "x", "backbone_figure_id": "fig-zz"}]

    assert _codes(stp.spine_check_errors(*_spine(_mutated(bad)))) == {"SPINE_FIGURE_UNKNOWN"}

    packet = _packet(backbone=False)
    spine, _ = _spine(_mutated(lambda d: d["sections"][1].update(
        figure_plan=[{"purpose": "x", "backbone_figure_id": "fig-a"}])), packet)
    assert _codes(stp.spine_check_errors(spine, packet)) == {"SPINE_FIGURE_UNKNOWN"}


def test_block_budget() -> None:
    def per_section(d):
        d["sections"][0]["planned_block_count"] = 4  # > max_blocks 3

    assert _codes(stp.spine_check_errors(*_spine(_mutated(per_section)))) == {"SPINE_BLOCK_BUDGET"}

    packet = _packet().model_copy(update={"limits": LessonLimits(max_total_blocks=5)})
    spine, _ = _spine(packet=packet)  # 2+2+2 = 6 > 5
    errors = stp.spine_check_errors(spine, packet)
    assert _codes(errors) == {"SPINE_BLOCK_BUDGET"} and "total 6" in errors[0]


def test_figure_plan_repair() -> None:
    spine, packet = _spine()
    assert spine.sections[2].figure_plan == []
    changes = stp.repair_spine_figure_plan(spine, packet)
    plan = spine.sections[2].figure_plan
    assert [p.backbone_figure_id for p in plan] == ["fig-a"]
    assert plan[0].purpose == "See the dimensions of the bed."
    assert changes[0]["slot_id"] == "check"
    # Idempotent.
    assert stp.repair_spine_figure_plan(spine, packet) == []


def _run(packet: ImmutableLessonPacket, monkeypatch, drafts: list) -> tuple[Any, list[dict]]:
    payloads: list[dict] = []
    queue = list(drafts)

    async def fake(*, system_prompt, user_payload, trace_id, generation_id, attempt_start=1):
        payloads.append(user_payload)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, item.model_dump_json()

    monkeypatch.setattr(stp, "_call_spine_model", fake)
    snapshot = make_snapshot()
    proj = stp.build_planner_projections(packet, snapshot)
    return (
        lambda: asyncio.run(
            stp.plan_teaching_spine(
                packet,
                snapshot=snapshot,
                teaching_guidance=proj["teaching_guidance"],
                slot_intent_policy=proj["slot_intent_policy"],
                assessment_source_policy=proj["assessment_source_policy"],
                trace_id="t",
                generation_id="g",
            )
        ),
        payloads,
    )


def test_uncovered_entry_state_is_repaired_on_first_attempt(monkeypatch) -> None:
    bad = _mutated(lambda d: d["sections"][1].update(entry_state=["quantum chromodynamics"]))
    run, payloads = _run(_packet(), monkeypatch, [bad])
    result = run()
    assert len(result.attempts) == 1 and len(payloads) == 1
    assert any(r["repair"] == "spine_state_chain" for r in result.repairs)
    assert "quantum chromodynamics" in result.spine.sections[0].exit_state


def test_retry_repairs_then_succeeds(monkeypatch) -> None:
    bad = _mutated(lambda d: d["sections"][2].update(approved_item_ids=[]))
    run, payloads = _run(_packet(), monkeypatch, [bad, _draft_dict()])
    result = run()
    assert len(result.attempts) == 2
    assert "repair" not in payloads[0]
    errs = payloads[1]["repair"]["validation_errors"]
    assert errs and errs[0].startswith("SPINE_ASSESSMENT_SLOT_EMPTY")
    assert payloads[1]["repair"]["previous_output"]["learner_title"] == "Area of rectangles"
    assert payloads[0]["approved_item_stems"][0] == {"id": "q1", "stem": "Area of the bed?"}
    assert result.attempts[0].errors == errs and result.attempts[1].errors == []
    # Figure plan repair applied on the success path.
    assert result.repairs and result.spine.sections[2].figure_plan[0].backbone_figure_id == "fig-a"


def test_three_bad_attempts_raise(monkeypatch) -> None:
    bad = _mutated(lambda d: d["sections"][2].update(approved_item_ids=[]))
    run, payloads = _run(_packet(), monkeypatch, [bad, bad, bad])
    with pytest.raises(TeachingPlanOutputInvalidError) as info:
        run()
    assert info.value.attempt_count == 3
    assert any("SPINE_ASSESSMENT_SLOT_EMPTY" in d for d in info.value.details)
    assert len(payloads) == 3


def test_transport_error_retries_without_repair(monkeypatch) -> None:
    from curriculum.llm_contract_errors import is_transport_error

    exc = TimeoutError("timed out")
    if not is_transport_error(exc):
        pytest.skip("TimeoutError is not classified as transport here")
    run, payloads = _run(_packet(), monkeypatch, [exc, _draft_dict()])
    result = run()
    assert len(result.attempts) == 2 and "repair" not in payloads[1]


def test_prompt_includes_backbone_guidance_and_no_leaks() -> None:
    spine_prompt = stp.render_staged_prompt(_packet(), None, kind="spine")
    assert BACKBONE_TEACHING_GUIDANCE in spine_prompt
    assert "{resource_identity}" not in spine_prompt
    plain = stp.render_staged_prompt(_packet(backbone=False), None, kind="spine")
    assert BACKBONE_TEACHING_GUIDANCE not in plain
    section_prompt = stp.render_staged_prompt(_packet(), None, kind="section")
    assert BACKBONE_TEACHING_GUIDANCE in section_prompt
    assert "LEARNER ACTION POLICY" in section_prompt
