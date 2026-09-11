"""Composition bridge: shared composer → Print FormPlan."""

from __future__ import annotations

import asyncio

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from document.composer import heuristic_compose_document_plan
from print.generation.composition_bridge import (
    composition_to_form_plan,
    build_print_production_from_composition,
)


def _plan() -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id="tp-bridge",
        revision=1,
        arc="Bridge composition to FormPlan.",
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                specific_purpose="core",
                blocks=[
                    TeachingPlanBlock(
                        id="s1-b1",
                        position=0,
                        intent="explain",
                        brief="Explain stomata briefly.",
                        evidence="Restatement.",
                        evidence_refs=[],
                    ),
                    TeachingPlanBlock(
                        id="s1-b2",
                        position=1,
                        intent="check",
                        brief="Choose the best definition.",
                        evidence="Correct option.",
                        evidence_refs=[],
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            target="stomata",
                            purpose="check",
                            expected_evidence="correct choice",
                            difficulty="guided",  # type: ignore[arg-type]
                        ),
                    ),
                ],
            )
        ],
    )


def test_composition_to_form_plan_maps_primitives_and_tasks() -> None:
    plan = _plan()
    document_plan = heuristic_compose_document_plan(plan, path="print")
    # Layer happens inside build_print_production_from_composition; exercise map via async.
    form_plan, snapshot, composition = asyncio.run(
        build_print_production_from_composition(
            teaching_plan=plan,
            provider=None,
            allow_heuristic_fallback=True,
        )
    )
    assert form_plan.sections[0].forms[0].object in {"prose", "heading", "list", "figure", "table", "aside"}
    assert form_plan.sections[0].forms[1].object == "choices"
    assert composition.path == "print"
    assert snapshot.decisions[1].form_id == "choices"
    # No catalogue LLM choose — objects come from composition / treatments.
    assert all(d.reason for d in form_plan.sections[0].forms)


def test_composition_to_form_plan_rejects_unknown_block() -> None:
    plan = _plan()
    empty = heuristic_compose_document_plan(plan, path="print")
    empty.decisions.clear()
    try:
        composition_to_form_plan(plan, empty)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "missing decision" in str(exc)
