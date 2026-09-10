"""Unit tests for Print/Learn document realizers (Phase E)."""

from __future__ import annotations

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from document.composition import (
    DOCUMENT_PRIMITIVE_KINDS,
    LEGACY_LEARN_COMPONENT_IDS,
    LEARN_RETAINED_INTERACTIONS,
    PRINT_ONLY_LAYOUT_OBJECTS,
    PRINT_TASK_OBJECTS,
)
from learn.generation.document_realizer import realize_learn_document
from print.generation.document_realizer import realize_print_document


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
    learn_plan = realize_learn_document(plan)

    assert print_plan.path == "print"
    assert learn_plan.path == "learn"
    assert {d.lane for d in print_plan.decisions} == {"document"}
    assert {d.lane for d in learn_plan.decisions} == {"document"}
    assert all(d.kind in DOCUMENT_PRIMITIVE_KINDS for d in print_plan.decisions)
    assert all(d.kind in DOCUMENT_PRIMITIVE_KINDS for d in learn_plan.decisions)
    assert all(d.kind == "paragraph" for d in print_plan.decisions)
    assert all(d.kind == "paragraph" for d in learn_plan.decisions)


def test_order_items_maps_to_learn_sequence_interaction() -> None:
    plan = _plan(
        TeachingPlanBlock(
            id="s1-b1",
            position=0,
            intent="practice",
            brief="Put the water cycle stages in order.",
            evidence="Correct sequence.",
            evidence_refs=[],
            learner_action=_action("order-items", target="water-cycle stages"),
        )
    )
    learn_plan = realize_learn_document(plan)
    kinds = [d.kind for d in learn_plan.decisions]
    lanes = [d.lane for d in learn_plan.decisions]
    assert "sequence" in kinds
    assert "learn_interaction" in lanes
    interaction = next(d for d in learn_plan.decisions if d.lane == "learn_interaction")
    assert interaction.kind == "sequence"
    assert interaction.teaching_block_id == "s1-b1"
    assert interaction.kind in LEARN_RETAINED_INTERACTIONS


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
    assert realize_learn_document(plan).decisions[0].kind == "table"


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
    assert emitted.isdisjoint(LEARN_RETAINED_INTERACTIONS)
    assert emitted.isdisjoint(LEGACY_LEARN_COMPONENT_IDS)
    assert all(d.lane != "learn_interaction" for d in print_plan.decisions)
    assert "choices" in emitted
    assert "questions" in emitted
    assert emitted <= (DOCUMENT_PRIMITIVE_KINDS | PRINT_TASK_OBJECTS)


def test_learn_path_never_emits_print_only_objects() -> None:
    plan = _plan(
        TeachingPlanBlock(
            id="s1-b1",
            position=0,
            intent="explain",
            brief="Explain the idea.",
            evidence="Restatement.",
            evidence_refs=[],
        ),
        TeachingPlanBlock(
            id="s1-b2",
            position=1,
            intent="check",
            brief="Select all that apply.",
            evidence="Correct set.",
            evidence_refs=[],
            learner_action=_action("select-many"),
        ),
    )
    learn_plan = realize_learn_document(plan)
    emitted = {d.kind for d in learn_plan.decisions}
    assert emitted.isdisjoint(PRINT_ONLY_LAYOUT_OBJECTS)
    assert emitted.isdisjoint(PRINT_TASK_OBJECTS)
    assert "ruled_lines" not in emitted
    assert "multi-select" in emitted
    assert all(d.kind != "ExplanationBlock" for d in learn_plan.decisions)
    assert all(d.kind not in LEGACY_LEARN_COMPONENT_IDS for d in learn_plan.decisions)
