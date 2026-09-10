"""Phase H — Print document realization aligned to shared primitives."""

from __future__ import annotations

from pathlib import Path

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from document.composition import DOCUMENT_PRIMITIVE_KINDS
from document.heuristics import choose_document_primitive
from print.generation.document_form_map import to_print_object
from print.generation.document_realizer import (
    produce_print_document_plan_from_teaching,
    realize_print_document,
    realize_print_to_page_forms,
)
from print.generation.task_treatments import (
    PRINT_TASK_TREATMENTS,
    print_treatment_for_learner_action,
)

_REALIZER_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "print"
    / "generation"
    / "document_realizer.py"
)


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
        teaching_plan_id="tp-print-align",
        revision=1,
        arc="Align Print realization to shared document primitives.",
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                specific_purpose="core",
                blocks=list(blocks),
            )
        ],
    )


def test_shared_primitives_map_to_print_objects() -> None:
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
            intent="compare",
            brief="Compare mitosis and meiosis side by side.",
            evidence="Key differences named.",
            evidence_refs=[],
        ),
        TeachingPlanBlock(
            id="s1-b3",
            position=2,
            intent="illustrate",
            brief="Show the chloroplast structure.",
            evidence="Labeled figure.",
            evidence_refs=[],
        ),
    )
    composition = realize_print_document(plan)
    assert all(d.lane == "document" for d in composition.decisions)
    assert all(d.kind in DOCUMENT_PRIMITIVE_KINDS for d in composition.decisions)

    page_forms = realize_print_to_page_forms(composition)
    assert [f["print_object"] for f in page_forms] == [
        to_print_object(d.kind)  # type: ignore[arg-type]
        for d in composition.decisions
    ]
    assert page_forms[0]["print_object"] == "prose"
    assert page_forms[1]["print_object"] == "table"
    assert page_forms[2]["print_object"] == "figure"

    produced = produce_print_document_plan_from_teaching(plan)
    assert produced["print_objects"] == [f["print_object"] for f in page_forms]
    # Same teaching meaning → same shared primitive choice as heuristics.
    for block, decision in zip(plan.sections[0].blocks, composition.decisions):
        expected_kind, _ = choose_document_primitive(block)
        assert decision.kind == expected_kind


def test_learner_task_maps_to_print_treatment() -> None:
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
        TeachingPlanBlock(
            id="s1-b3",
            position=2,
            intent="demonstrate",
            brief="Work the sample calculation.",
            evidence="Correct worked steps.",
            evidence_refs=[],
            learner_action=_action("enter-number"),
        ),
    )
    assert print_treatment_for_learner_action("select-one") == "choices"
    assert print_treatment_for_learner_action("order-items") == "questions"
    assert (
        print_treatment_for_learner_action("enter-number", intent="demonstrate")
        == "worked-example"
    )

    page_forms = realize_print_to_page_forms(plan)
    objects = [f["print_object"] for f in page_forms]
    assert objects == ["choices", "questions", "worked-example"]
    assert all(f["lane"] == "print_task" for f in page_forms)
    assert set(objects) <= PRINT_TASK_TREATMENTS


def test_document_realizer_has_no_learn_imports() -> None:
    source = _REALIZER_PATH.read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    ]
    assert all("learn." not in line for line in import_lines)
    assert "from learn" not in source
    assert "import learn" not in source
