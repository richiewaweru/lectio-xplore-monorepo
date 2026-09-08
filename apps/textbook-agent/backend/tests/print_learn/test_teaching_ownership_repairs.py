"""Teaching-stage ownership: no silent order-items / no pool.pop assessment guess."""

from __future__ import annotations

from types import SimpleNamespace

from print.generation.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    ScopeEntry,
    SlotRecord,
)
from print.generation.whole_lesson.teaching_agent import (
    _assessment_item_compatible_with_block,
    _missing_order_learner_action_errors,
    _repair_incompatible_assessment_sources,
    _repair_missing_assessment_sources,
)
from print.generation.whole_lesson.teaching_plan import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)


def _packet(
    *,
    objective: str = "Explain photosynthesis.",
    items: list[ApprovedItemRef] | None = None,
) -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="l-own",
            subject="Science",
            grade_level="Grade 4",
            objective=objective,
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        anchor=AnchorRecord(
            id="anchor-light",
            description="Sunlight powers the leaf.",
        ),
        scope=ScopeContract(
            must_establish=[
                ScopeEntry(id="m1", statement="Chlorophyll absorbs light energy."),
            ],
            terminology=["chlorophyll", "light"],
        ),
        slots=[
            SlotRecord(
                slot_id="practice",
                purpose="Check understanding",
                typical_intents=["check-understanding", "sequence"],
            ),
        ],
        approved_items=list(items or []),
        limits=LessonLimits(),
    )


def _plan(*blocks: TeachingPlanBlock, arc: str = "Arc") -> TeachingPlan:
    return TeachingPlan(
        arc=arc,
        teaching_plan_id="tp-own",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="practice",
                specific_purpose="Practice",
                blocks=list(blocks),
            )
        ],
    )


def test_missing_order_action_emits_repair_not_silent_sequence() -> None:
    packet = _packet(objective="Order the stages of the life cycle.")
    plan = _plan(
        TeachingPlanBlock(
            id="b1",
            position=0,
            intent="sequence",
            brief="Put the life-cycle stages in order using chlorophyll vocabulary.",
            evidence="Learner reconstructs order",
            source_question_ids=[],
            learner_action=None,
        ),
        arc="Life cycle stages in order",
    )
    errors = _missing_order_learner_action_errors(plan, packet)
    assert errors
    assert all("TEACHING_MISSING_ORDER_ACTION" in err for err in errors)
    # Must not mutate the plan with a fabricated order-items action.
    assert plan.sections[0].blocks[0].learner_action is None


def test_order_action_present_is_not_an_error() -> None:
    packet = _packet(objective="Order the stages of the life cycle.")
    plan = _plan(
        TeachingPlanBlock(
            id="b1",
            position=0,
            intent="sequence",
            brief="Order egg larva pupa adult with owned terms chlorophyll.",
            evidence="Order reconstructed",
            source_question_ids=[],
            learner_action=LearnerActionBrief(
                action="order-items",
                support_level="independent",
                evidence="Order reconstructed",
                source_item_ids=[],
            ),
        )
    )
    assert _missing_order_learner_action_errors(plan, packet) == []


def test_incompatible_assessment_sources_are_cleared() -> None:
    packet = _packet(
        items=[
            ApprovedItemRef(
                id="mc-1",
                card_id="c1",
                stem="Where does plant mass come from?",
                options=[{"key": "A", "text": "Soil"}, {"key": "B", "text": "Air"}],
                correct_key="B",
            )
        ]
    )
    # Explain typically does not support choices — binding must be cleared.
    plan = _plan(
        TeachingPlanBlock(
            id="b-explain",
            position=0,
            intent="explain",
            brief="Explain chlorophyll absorbs light.",
            evidence="Can explain",
            source_question_ids=["mc-1"],
        )
    )
    _repair_incompatible_assessment_sources(plan, packet)
    assert plan.sections[0].blocks[0].source_question_ids == []


def test_assessment_bind_requires_concept_overlap_not_pop0() -> None:
    related = ApprovedItemRef(
        id="mc-related",
        card_id="c1",
        stem="Chlorophyll absorbs light energy in the leaf.",
        options=[{"key": "A", "text": "True"}, {"key": "B", "text": "False"}],
        correct_key="A",
    )
    unrelated = ApprovedItemRef(
        id="mc-unrelated",
        card_id="c2",
        stem="Which planet is largest in the solar system?",
        options=[{"key": "A", "text": "Jupiter"}, {"key": "B", "text": "Mars"}],
        correct_key="A",
    )
    # Put unrelated first so a naive pop(0) would bind the wrong item.
    packet = _packet(items=[unrelated, related])
    block = TeachingPlanBlock(
        id="b-check",
        position=0,
        intent="check-understanding",
        brief="Check that chlorophyll absorbs light.",
        evidence="Selects the chlorophyll fact",
        source_question_ids=[],
    )
    plan = _plan(block)
    errors = _repair_missing_assessment_sources(
        plan, packet, {"check-understanding", "practise-guided"}
    )
    assert errors == []
    assert block.source_question_ids == ["mc-related"]


def test_assessment_missing_compatible_source_requests_repair() -> None:
    unrelated = ApprovedItemRef(
        id="mc-unrelated",
        card_id="c2",
        stem="Which planet is largest in the solar system?",
        options=[{"key": "A", "text": "Jupiter"}, {"key": "B", "text": "Mars"}],
        correct_key="A",
    )
    packet = _packet(items=[unrelated])
    block = TeachingPlanBlock(
        id="b-check",
        position=0,
        intent="check-understanding",
        brief="Check that chlorophyll absorbs light.",
        evidence="Selects the chlorophyll fact",
        source_question_ids=[],
    )
    plan = _plan(block)
    errors = _repair_missing_assessment_sources(plan, packet, {"check-understanding"})
    assert any("TEACHING_MISSING_ASSESSMENT_OWNERSHIP" in err for err in errors)
    assert block.source_question_ids == []


def test_compatibility_helper_rejects_kind_mismatch() -> None:
    packet = _packet()
    block = TeachingPlanBlock(
        id="b1",
        position=0,
        intent="explain",
        brief="Explain chlorophyll.",
        evidence="Explains",
        source_question_ids=[],
    )
    item = SimpleNamespace(
        id="mc-1",
        stem="Chlorophyll absorbs light",
        options=[{"key": "A", "text": "Yes"}],
        correct_key="A",
    )
    assert (
        _assessment_item_compatible_with_block(block=block, item=item, packet=packet)
        is False
    )
