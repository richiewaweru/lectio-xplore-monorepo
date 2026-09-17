"""Composition bridge: shared composer → closed Print FormPlan."""

from __future__ import annotations

import asyncio

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from document.composer import heuristic_compose_document_plan
from print.generation.composition_bridge import (
    build_print_production_from_composition,
    composition_to_form_plan,
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
                            difficulty="guided",
                        ),
                    ),
                ],
            )
        ],
    )


def test_print_bridge_requires_upstream_candidate_map() -> None:
    plan = _plan()
    with pytest.raises(ValueError, match="candidate_map is required"):
        asyncio.run(
            build_print_production_from_composition(
                teaching_plan=plan,
                provider=None,
                allow_heuristic_fallback=True,
            )
        )


def test_composition_stays_inside_exact_ordinary_candidates() -> None:
    plan = _plan()
    plan.sections[0].blocks[1].learner_action = None
    form_plan, snapshot, composition = asyncio.run(
        build_print_production_from_composition(
            teaching_plan=plan,
            provider=None,
            allow_heuristic_fallback=True,
            candidate_map={
                "s1-b1": ["prose"],
                "s1-b2": ["list"],
            },
        )
    )
    assert [item.object for item in form_plan.sections[0].forms] == ["prose", "list"]
    assert snapshot.candidate_map == {"s1-b1": ["prose"], "s1-b2": ["list"]}
    assert composition.path == "print"


def test_composition_keeps_choices_only_when_source_and_candidate_are_bound() -> None:
    plan = _plan()
    plan.sections[0].blocks[1].source_question_ids = ["q-stomata-1"]
    form_plan, snapshot, composition = asyncio.run(
        build_print_production_from_composition(
            teaching_plan=plan,
            provider=None,
            allow_heuristic_fallback=True,
            candidate_map={
                "s1-b1": ["prose"],
                "s1-b2": ["choices"],
            },
        )
    )
    assert form_plan.sections[0].forms[0].object == "prose"
    assert form_plan.sections[0].forms[1].object == "choices"
    assert composition.path == "print"
    assert snapshot.decisions[1].form_id == "choices"
    assert snapshot.candidate_map["s1-b2"] == ["choices"]


def test_composition_maps_formative_response_to_print_treatment_without_source() -> None:
    """Formative shared tasks still need a faithful paper treatment."""
    plan = _plan()
    plan.sections[0].blocks[1].task_mode = "formative"
    form_plan, snapshot, _composition = asyncio.run(
        build_print_production_from_composition(
            teaching_plan=plan,
            provider=None,
            allow_heuristic_fallback=True,
            candidate_map={
                "s1-b1": ["prose"],
                "s1-b2": ["choices"],
            },
        )
    )
    assert form_plan.sections[0].forms[1].object == "choices"
    assert snapshot.decisions[1].form_id == "choices"


def test_print_bridge_rejects_task_outside_closed_candidate_set() -> None:
    plan = _plan()
    plan.sections[0].blocks[1].source_question_ids = ["q-stomata-1"]
    with pytest.raises(ValueError, match="outside the closed candidate set"):
        asyncio.run(
            build_print_production_from_composition(
                teaching_plan=plan,
                provider=None,
                allow_heuristic_fallback=True,
                candidate_map={
                    "s1-b1": ["prose"],
                    "s1-b2": ["prose"],
                },
            )
        )


def test_composition_to_form_plan_rejects_unknown_block() -> None:
    plan = _plan()
    empty = heuristic_compose_document_plan(plan, path="print")
    empty.decisions.clear()
    with pytest.raises(ValueError, match="missing decision"):
        composition_to_form_plan(plan, empty)
