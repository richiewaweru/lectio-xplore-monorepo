"""Teaching-plan validation and departure rules."""

from __future__ import annotations

import pytest

from planning.page_blocks import PageBlockPlanError, validate_intent_departure
from planning.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    ScopeEntry,
    SlotRecord,
)
from planning.whole_lesson.teaching_plan import (
    AnchorUsageEntry,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from planning.whole_lesson.validation import validate_teaching_plan


def test_typical_intent_forbids_departure_reason() -> None:
    with pytest.raises(PageBlockPlanError):
        validate_intent_departure(
            intent="orient",
            typical_intents={"orient"},
            permitted_intents={"orient", "emphasise"},
            excluded_intents={"investigate"},
            departure_reason="just because",
        )


def test_atypical_intent_requires_departure_reason() -> None:
    with pytest.raises(PageBlockPlanError):
        validate_intent_departure(
            intent="emphasise",
            typical_intents={"orient"},
            permitted_intents={"orient", "emphasise"},
            excluded_intents=set(),
            departure_reason=None,
        )
    validate_intent_departure(
        intent="emphasise",
        typical_intents={"orient"},
        permitted_intents={"orient", "emphasise"},
        excluded_intents=set(),
        departure_reason="Need a short reminder before the check.",
    )


def test_object_leak_ignores_english_questions_in_prose() -> None:
    from planning.whole_lesson.validation import _contains_object_id

    assert _contains_object_id("Ask retrieval questions about the cell wall.") is None
    assert _contains_object_id('{"brief":"Ask retrieval questions about cells."}') is None
    assert _contains_object_id('{"object":"questions"}') == "questions"
    assert _contains_object_id("Use a worked-example here") == "worked-example"

    with pytest.raises(PageBlockPlanError):
        validate_intent_departure(
            intent="investigate",
            typical_intents=set(),
            permitted_intents={"orient"},
            excluded_intents={"investigate"},
            departure_reason=None,
        )


def test_empty_typical_intents_allows_permitted_without_departure() -> None:
    """Incomplete slot guidance must not block Patch 01 architecture proof."""
    validate_intent_departure(
        intent="explain",
        typical_intents=set(),
        permitted_intents={"orient", "explain"},
        excluded_intents=set(),
        departure_reason=None,
    )
    with pytest.raises(PageBlockPlanError, match="not permitted"):
        validate_intent_departure(
            intent="invented-intent",
            typical_intents=set(),
            permitted_intents={"orient", "explain"},
            excluded_intents=set(),
            departure_reason=None,
        )


def test_generic_brief_fails_validation() -> None:
    packet = ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="l1",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light to make food.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[ScopeEntry(id="must-1", statement="Light is required.")],
            terminology=["light", "food"],
        ),
        anchor=AnchorRecord(id="anchor-1", description="Two plants"),
        approved_items=[
            ApprovedItemRef(id="item-1", card_id="c1", stem="Q?", correct_key="A")
        ],
        slots=[SlotRecord(slot_id=s) for s in ("orient", "explain", "confront", "check")],
        limits=LessonLimits(),
    )
    plan = TeachingPlan(
        arc="Opens on two plants, isolates light, confronts soil-food belief, checks with a new case.",
        anchor_usage=[
            AnchorUsageEntry(slot_id="orient", usage="show plants"),
            AnchorUsageEntry(slot_id="explain", usage="reuse plants"),
            AnchorUsageEntry(slot_id="confront", usage="test soil belief"),
            AnchorUsageEntry(slot_id="check", usage="new case"),
        ],
        sections=[
            TeachingPlanSection(
                slot_id=slot,
                blocks=[
                    TeachingPlanBlock(
                        id=f"{slot}-b1",
                        position=0,
                        intent="orient" if slot == "orient" else "explain",
                        brief="explain the concept clearly for learners today",
                        evidence_refs=["lesson.objective"],
                        evidence="Because the objective needs an opening.",
                    )
                ],
            )
            for slot in ("orient", "explain", "confront", "check")
        ],
    )
    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "explain"},
        excluded_intents=set(),
        typical_by_slot={
            "orient": {"orient"},
            "explain": {"explain"},
            "confront": {"explain"},
            "check": {"explain"},
        },
    )
    assert not report.ok
    codes = {issue.code for issue in report.issues}
    assert "BRIEF_GENERIC" in codes or "BRIEF_TOO_SHORT" in codes or "BRIEF_NO_ANCHOR_OR_TERM" in codes


def _slot_order_packet(slots: tuple[str, ...], *, knowledge_type: str = "conceptual") -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="l-slot",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light to make food.",
            knowledge_type=knowledge_type,
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[ScopeEntry(id="must-1", statement="Light is required.")],
            terminology=["light", "food", "plant"],
        ),
        anchor=AnchorRecord(id="anchor-1", description="Two plants by a window"),
        approved_items=[
            ApprovedItemRef(id="item-1", card_id="c1", stem="Why did the leaf fail?", correct_key="A")
        ],
        slots=[SlotRecord(slot_id=slot) for slot in slots],
        limits=LessonLimits(),
    )


def _slot_order_plan(slots: tuple[str, ...]) -> TeachingPlan:
    return TeachingPlan(
        arc="Uses the window plants to establish light, then checks transfer on a new case.",
        anchor_usage=[
            AnchorUsageEntry(slot_id=slot, usage="" if slot not in {"orient", "explain"} else "use")
            for slot in slots
        ],
        sections=[
            TeachingPlanSection(
                slot_id=slot,
                blocks=[
                    TeachingPlanBlock(
                        id=f"{slot}-b1",
                        position=0,
                        intent="orient" if slot == "orient" else "explain",
                        brief=(
                            f"In {slot}, reuse the window plants and the term light "
                            "so learners see why food-making needs light."
                        ),
                        evidence_refs=["lesson.objective", "must-1", "anchor.anchor-1"],
                        evidence="Objective and must-establish force light as the cause.",
                    )
                ],
            )
            for slot in slots
        ],
    )


def _slot_order_report(plan: TeachingPlan, packet: ImmutableLessonPacket):
    slots = [section.slot_id for section in plan.sections] or [
        slot.slot_id for slot in packet.slots
    ]
    return validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "explain"},
        excluded_intents=set(),
        typical_by_slot={slot: {"orient", "explain"} for slot in slots},
    )


def test_slot_order_validation_uses_factual_packet_slots() -> None:
    factual = ("orient", "organise", "guided", "independent", "check")
    packet = _slot_order_packet(factual, knowledge_type="factual")
    report = _slot_order_report(_slot_order_plan(factual), packet)
    assert not any(issue.code == "SLOT_ORDER" for issue in report.issues)


def test_slot_order_validation_uses_procedural_packet_slots() -> None:
    procedural = ("orient", "recall", "model", "guided", "check")
    packet = _slot_order_packet(procedural, knowledge_type="procedural")
    report = _slot_order_report(_slot_order_plan(procedural), packet)
    assert not any(issue.code == "SLOT_ORDER" for issue in report.issues)


def test_slot_order_validation_rejects_missing_extra_and_reordered() -> None:
    expected = ("orient", "organise", "guided", "independent", "check")
    packet = _slot_order_packet(expected, knowledge_type="factual")

    missing = _slot_order_report(_slot_order_plan(expected[:-1]), packet)
    assert any(issue.code == "SLOT_ORDER" for issue in missing.issues)
    assert "organise" in missing.issues[0].message or "independent" in (
        next(i.message for i in missing.issues if i.code == "SLOT_ORDER")
    )

    extra = _slot_order_report(
        _slot_order_plan(expected + ("transfer",)),
        packet,
    )
    assert any(issue.code == "SLOT_ORDER" for issue in extra.issues)

    reordered = ("orient", "guided", "organise", "independent", "check")
    report = _slot_order_report(_slot_order_plan(reordered), packet)
    order_issue = next(i for i in report.issues if i.code == "SLOT_ORDER")
    assert str(list(expected)) in order_issue.message
    assert str(list(reordered)) in order_issue.message


def test_slot_order_exact_packet_order_passes_slot_check() -> None:
    expected = ("orient", "explain", "contrast", "confront", "check")
    packet = _slot_order_packet(expected)
    report = _slot_order_report(_slot_order_plan(expected), packet)
    assert not any(issue.code == "SLOT_ORDER" for issue in report.issues)


def test_required_visual_slot_needs_spatial_process_intent() -> None:
    slots = ("orient", "model")
    packet = _slot_order_packet(slots, knowledge_type="procedural")
    packet.slots[1].visual_required = True
    plan = _slot_order_plan(slots)

    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "explain", "show-structure"},
        excluded_intents=set(),
        typical_by_slot={slot: {"orient", "explain"} for slot in slots},
    )

    assert any(issue.code == "REQUIRED_VISUAL_INTENT" for issue in report.issues)

    plan.sections[1].blocks[0].intent = "show-structure"
    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "explain", "show-structure"},
        excluded_intents=set(),
        typical_by_slot={slot: {"orient", "explain"} for slot in slots},
    )
    assert not any(issue.code == "REQUIRED_VISUAL_INTENT" for issue in report.issues)


def test_anchor_usage_accepts_active_contrast_slot() -> None:
    packet = _slot_order_packet(("orient", "explain", "contrast", "confront", "check"))
    plan = TeachingPlan(
        arc="Orient, explain, contrast, confront, and check the idea.",
        anchor_usage=[
            AnchorUsageEntry(slot_id="orient", usage="Introduce the anchor."),
            AnchorUsageEntry(slot_id="explain", usage="Build the model."),
            AnchorUsageEntry(
                slot_id="contrast", usage="Set the case beside a near miss."
            ),
            AnchorUsageEntry(slot_id="confront", usage=""),
            AnchorUsageEntry(slot_id="check", usage="Return to the objective."),
        ],
        sections=[
            TeachingPlanSection(
                slot_id=slot,
                blocks=[
                    TeachingPlanBlock(
                        id=f"{slot}-b1",
                        position=0,
                        intent="orient" if slot == "orient" else "explain",
                        brief="Brief for test",
                        evidence_refs=["lesson.objective"],
                        evidence="Evidence",
                    )
                ],
            )
            for slot in ("orient", "explain", "contrast", "confront", "check")
        ],
    )

    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "explain"},
        excluded_intents=set(),
        typical_by_slot={slot.slot_id: {"orient", "explain"} for slot in packet.slots},
    )

    assert not any(issue.code == "ANCHOR_USAGE_SLOT_MISMATCH" for issue in report.issues)


def test_anchor_usage_slot_mismatch_rejected() -> None:
    expected = ("orient", "explain", "confront", "check")
    packet = _slot_order_packet(expected)
    plan = _slot_order_plan(expected)
    # Swap two anchor entries; sections stay correct, so this isolates the
    # anchor_usage slot identity/order validator.
    plan.anchor_usage = [
        plan.anchor_usage[0],
        plan.anchor_usage[1],
        plan.anchor_usage[3],
        plan.anchor_usage[2],
    ]

    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "explain"},
        excluded_intents=set(),
        typical_by_slot={slot: {"orient", "explain"} for slot in expected},
    )
    assert any(issue.code == "ANCHOR_USAGE_SLOT_MISMATCH" for issue in report.issues)


def test_assessment_intent_requires_approved_source_when_items_exist() -> None:
    packet = _slot_order_packet(("orient", "check"))
    plan = _slot_order_plan(("orient", "check"))
    plan.sections[1].blocks[0].intent = "check-understanding"

    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "check-understanding"},
        excluded_intents=set(),
        typical_by_slot={"orient": {"orient"}, "check": {"check-understanding"}},
        assessment_intents={"check-understanding"},
    )

    assert any(
        issue.code == "ASSESSMENT_SOURCE_REQUIRED" for issue in report.issues
    )
