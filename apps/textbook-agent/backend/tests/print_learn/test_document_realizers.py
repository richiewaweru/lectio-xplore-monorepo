"""Unit tests for the Print document realizer (Phase E / correction Wave 1).

Learn no longer realizes ordinary document form from a Teaching Plan
heuristic: ``learn.generation.document_realizer`` was retired in P10E
because the SharedLessonDocument Learn adapter copies ordinary content and
maps TaskAnchors deterministically. Print's realizer is unaffected and still
covered here.
"""

from __future__ import annotations

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from document.models import DOCUMENT_PRIMITIVE_KINDS
from learn.interactions.registry import RETAINED_INTERACTIONS, RETIRED_ORDINARY_CONTENT_IDS
from print.generation.document_realizer import realize_print_document
from print.generation.task_treatments import PRINT_TASK_TREATMENTS


def _action(
    action: str,
    *,
    target: str = "the concept",
    purpose: str = "check understanding",
    expected_evidence: str = "correct response",
    difficulty: str = "guided",
) -> LearnerActionBrief:
    return LearnerActionBrief(
        action=action,
        target=target,
        purpose=purpose,
        expected_evidence=expected_evidence,
        difficulty=difficulty,  # type: ignore[arg-type]
    )


def _plan(*blocks: TeachingPlanBlock) -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id="tp-doc-realize",
        revision=1,
        arc="Realize document forms from teaching meaning.",
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                specific_purpose="core",
                blocks=list(blocks),
            )
        ],
    )


def test_prose_only_blocks_emit_document_primitives() -> None:
    plan = _plan(
        TeachingPlanBlock(
            id="s1-b1",
            position=0,
            intent="explain",
            brief="Explain photosynthesis in plain language.",
            evidence="Student can restate the idea.",
            evidence_refs=[],
        ),
        TeachingPlanBlock(
            id="s1-b2",
            position=1,
            intent="define",
            brief="Define chloroplast.",
            evidence="Accurate definition.",
            evidence_refs=[],
        ),
    )
    print_plan = realize_print_document(plan)

    assert print_plan.path == "print"
    assert {d.lane for d in print_plan.decisions} == {"document"}
    assert all(d.kind in DOCUMENT_PRIMITIVE_KINDS for d in print_plan.decisions)
    assert all(d.kind == "paragraph" for d in print_plan.decisions)


def test_compare_intent_maps_to_table() -> None:
    plan = _plan(
        TeachingPlanBlock(
            id="s1-b1",
            position=0,
            intent="compare",
            brief="Compare mitosis and meiosis side by side.",
            evidence="Key differences named.",
            evidence_refs=[],
        )
    )
    assert realize_print_document(plan).decisions[0].kind == "table"


def test_print_path_never_emits_learn_interaction_ids() -> None:
    plan = _plan(
        TeachingPlanBlock(
            id="s1-b1",
            position=0,
            intent="check",
            brief="Choose the best definition.",
            evidence="Correct option.",
            evidence_refs=[],
            learner_action=_action("select-one"),
        ),
        TeachingPlanBlock(
            id="s1-b2",
            position=1,
            intent="practice",
            brief="Order the steps.",
            evidence="Correct order.",
            evidence_refs=[],
            learner_action=_action("order-items"),
        ),
    )
    print_plan = realize_print_document(plan)
    emitted = {d.kind for d in print_plan.decisions}
    assert emitted.isdisjoint(RETAINED_INTERACTIONS)
    assert emitted.isdisjoint(RETIRED_ORDINARY_CONTENT_IDS)
    assert all(d.lane != "learn_interaction" for d in print_plan.decisions)
    assert "choices" in emitted
    assert "questions" in emitted
    assert emitted <= (DOCUMENT_PRIMITIVE_KINDS | PRINT_TASK_TREATMENTS)
