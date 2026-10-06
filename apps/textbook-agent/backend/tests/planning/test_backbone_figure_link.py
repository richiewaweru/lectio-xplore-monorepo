"""Backbone figures are linked to the plan block that owns their questions."""

from __future__ import annotations

from application.unit_lesson.teaching_planner import _repair_missing_figure_visuals
from curriculum.teaching_plan.models import LearnerActionBrief, VisualSpec
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
from print.generation.whole_lesson.teaching_plan import (
    AnchorUsageEntry,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from print.generation.whole_lesson.validation import (
    HARD_PLAN_ISSUE_CODES,
    validate_teaching_plan,
)

SLOTS = ("orient", "check")

BACKBONE = {
    "anchor": {"id": "anchor-1", "story": "A garden bed.", "data": {}, "figure_ids": ["fig-a"]},
    "variants": [],
    "figures": [
        {
            "id": "fig-a",
            "purpose": "See the dimensions of the bed.",
            "must_show": ["a rectangle with sides marked"],
            "labels_required": ["9 m", "4 m"],
            "data": {"width": 9, "height": 4, "points": [[0, 0], [9, 0]]},
        },
        {
            "id": "fig-b",
            "purpose": "See the real garden.",
            "must_show": ["a vegetable garden bed"],
            "labels_required": [],
            "data": {},
            "mode": "image",
        },
        {
            "id": "fig-c",
            "purpose": "Compare the plots.",
            "must_show": [],
            "labels_required": [],
            "data": {},
        },
    ],
}


def _packet(refs: dict[str, dict] | None = None, *, backbone: bool = True) -> ImmutableLessonPacket:
    packet = ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="l-fig",
            subject="Maths",
            grade_level="Grade 6",
            objective="Find the area of a rectangle.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[ScopeEntry(id="must-1", statement="Area is length times width.")],
            terminology=["area", "rectangle"],
        ),
        anchor=AnchorRecord(id="anchor-1", description="A garden bed"),
        approved_items=[
            ApprovedItemRef(id="q1", card_id="c1", stem="Area?", correct_key="A"),
            ApprovedItemRef(id="q2", card_id="c1", stem="Perimeter?", correct_key="B"),
        ],
        slots=[SlotRecord(slot_id=s) for s in SLOTS],
        limits=LessonLimits(),
    )
    if not backbone:
        return packet
    return packet.model_copy(
        update={
            "backbone": BACKBONE,
            "item_backbone_refs": refs
            if refs is not None
            else {
                "q1": {"target": "anchor-1", "figure_id": "fig-a"},
                "q2": {"target": "anchor-1", "figure_id": None},
            },
        }
    )


def _plan(sources: list[str], visual: VisualSpec | None = None) -> TeachingPlan:
    def block(slot: str) -> TeachingPlanBlock:
        owns = slot == "check"
        return TeachingPlanBlock(
            id=f"{slot}-b1",
            position=0,
            intent="check-understanding" if owns else "orient",
            brief=(
                f"In {slot}, reuse the garden bed and the term area so learners "
                "see how the rectangle sides give the area."
            ),
            evidence_refs=["lesson.objective", "must-1", "anchor.anchor-1"],
            evidence="Objective and must-establish force area as length times width.",
            source_question_ids=list(sources) if owns else [],
            task_mode="assessment" if owns else "none",
            learner_action=(
                LearnerActionBrief(
                    action="enter-number",
                    target="area of the bed",
                    purpose="Apply the area rule.",
                    expected_evidence="Gives the correct area.",
                    difficulty="independent",
                )
                if owns
                else None
            ),
            visual=visual if owns else None,
        )

    return TeachingPlan(
        arc="Uses the garden bed to establish area, then checks it on the same bed.",
        anchor_usage=[AnchorUsageEntry(slot_id=s, usage="use") for s in SLOTS],
        sections=[TeachingPlanSection(slot_id=s, blocks=[block(s)]) for s in SLOTS],
    )


def _codes(plan: TeachingPlan, packet: ImmutableLessonPacket) -> list[str]:
    report = validate_teaching_plan(
        plan,
        packet,
        permitted_intents={"orient", "check-understanding"},
        excluded_intents=set(),
        typical_by_slot={"orient": {"orient"}, "check": {"check-understanding"}},
        assessment_intents={"check-understanding"},
    )
    return [issue.code for issue in report.issues]


def _check_visual(plan: TeachingPlan) -> VisualSpec | None:
    return plan.sections[1].blocks[0].visual


def test_new_codes_are_hard() -> None:
    assert {"FIGURE_REF_UNKNOWN", "FIGURE_REF_MISSING"} <= HARD_PLAN_ISSUE_CODES


def test_repair_creates_diagram_visual_from_backbone_figure() -> None:
    plan, packet = _plan(["q1"]), _packet()
    changes = _repair_missing_figure_visuals(plan, packet)
    assert changes == [{"block_id": "check-b1", "figure_id": "fig-a", "action": "created_visual"}]
    visual = _check_visual(plan)
    assert visual is not None
    assert (visual.figure_ref, visual.mode) == ("fig-a", "diagram")
    assert visual.purpose == "See the dimensions of the bed."
    assert visual.must_show == ["a rectangle with sides marked"]
    assert visual.labels_required == ["9 m", "4 m"]
    codes = _codes(plan, packet)
    assert "FIGURE_REF_MISSING" not in codes and "VISUAL_SPEC_INVALID" not in codes


def test_repair_creates_image_visual_and_defaults_empty_diagram_must_show() -> None:
    plan = _plan(["q1"])
    packet = _packet({"q1": {"target": "anchor-1", "figure_id": "fig-b"}})
    _repair_missing_figure_visuals(plan, packet)
    visual = _check_visual(plan)
    assert (visual.figure_ref, visual.mode) == ("fig-b", "image")

    plan = _plan(["q1"])
    packet = _packet({"q1": {"target": "anchor-1", "figure_id": "fig-c"}})
    _repair_missing_figure_visuals(plan, packet)
    visual = _check_visual(plan)
    assert visual.must_show == ["Compare the plots."]
    assert "VISUAL_SPEC_INVALID" not in _codes(plan, packet)


def test_repair_links_existing_visual_and_unions_labels() -> None:
    existing = VisualSpec(
        purpose="Notice the sides.",
        must_show=["a rectangle with sides marked", "the area shaded"],
        labels_required=["4 m", "area"],
    )
    plan, packet = _plan(["q1"], existing), _packet()
    changes = _repair_missing_figure_visuals(plan, packet)
    assert changes[0]["action"] == "linked_visual"
    visual = _check_visual(plan)
    assert visual.figure_ref == "fig-a"
    assert visual.purpose == "Notice the sides."
    assert visual.must_show == ["a rectangle with sides marked", "the area shaded"]
    assert visual.labels_required == ["4 m", "area", "9 m"]


def test_repair_ignores_questions_without_figure() -> None:
    plan, packet = _plan(["q2"]), _packet()
    assert _repair_missing_figure_visuals(plan, packet) == []
    assert _check_visual(plan) is None
    assert "FIGURE_REF_MISSING" not in _codes(plan, packet)


def test_conflicting_figure_ref_is_not_repaired_and_fails_hard() -> None:
    visual = VisualSpec(
        figure_ref="fig-b", mode="image", purpose="Garden.", must_show=["a vegetable garden bed"]
    )
    plan, packet = _plan(["q1"], visual), _packet()
    assert _repair_missing_figure_visuals(plan, packet) == []
    assert _check_visual(plan).figure_ref == "fig-b"
    assert "FIGURE_REF_MISSING" in _codes(plan, packet)


def test_two_required_figures_on_one_block_fail_and_are_not_repaired() -> None:
    packet = _packet(
        {
            "q1": {"target": "anchor-1", "figure_id": "fig-a"},
            "q2": {"target": "anchor-1", "figure_id": "fig-b"},
        }
    )
    plan = _plan(["q1", "q2"])
    assert _repair_missing_figure_visuals(plan, packet) == []
    assert _check_visual(plan) is None
    assert "FIGURE_REF_MISSING" in _codes(plan, packet)
    # Even when one of them is linked, the other still fails.
    plan = _plan(["q1", "q2"], VisualSpec(figure_ref="fig-a", purpose="x", must_show=["y"]))
    assert "FIGURE_REF_MISSING" in _codes(plan, packet)


def test_missing_visual_fails_before_repair_and_passes_after() -> None:
    plan, packet = _plan(["q1"]), _packet()
    assert "FIGURE_REF_MISSING" in _codes(plan, packet)
    _repair_missing_figure_visuals(plan, packet)
    assert "FIGURE_REF_MISSING" not in _codes(plan, packet)


def test_unknown_figure_ref_fails_hard() -> None:
    visual = VisualSpec(figure_ref="fig-zzz", purpose="Garden.", must_show=["the area"])
    plan = _plan(["q2"], visual)
    assert "FIGURE_REF_UNKNOWN" in _codes(plan, _packet())
    assert "FIGURE_REF_UNKNOWN" in _codes(plan, _packet(backbone=False))


def test_backbone_labels_pass_grounding_only_with_figure_ref() -> None:
    kwargs = {
        "purpose": "See the dimensions.",
        "must_show": ["the sides"],
        "labels_required": ["9 m", "4 m"],
    }
    packet = _packet({"q1": {"target": "anchor-1", "figure_id": None}})
    without = _plan(["q1"], VisualSpec(**kwargs))
    assert "VISUAL_SPEC_INVALID" in _codes(without, packet)
    linked = _plan(["q1"], VisualSpec(figure_ref="fig-a", **kwargs))
    assert "VISUAL_SPEC_INVALID" not in _codes(linked, packet)


def test_plan_without_backbone_is_unaffected() -> None:
    packet = _packet(backbone=False)
    plan = _plan(["q1"])
    assert _repair_missing_figure_visuals(plan, packet) == []
    assert _check_visual(plan) is None
    codes = _codes(plan, packet)
    assert "FIGURE_REF_MISSING" not in codes and "FIGURE_REF_UNKNOWN" not in codes
