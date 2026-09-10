"""Print document realizer — Teaching Plan → compact composition plan (Phase E/H).

Deterministic heuristics only. Ordinary content uses shared document primitives;
learner tasks that require a response become Print-only task treatments.
"""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composition import (
    DOCUMENT_PRIMITIVE_KINDS,
    LEGACY_LEARN_COMPONENT_IDS,
    PRINT_TASK_OBJECTS,
    CompositionDecision,
    CompositionPlan,
)
from document.heuristics import choose_document_primitive
from print.generation.document_form_map import to_print_object
from print.generation.task_treatments import (
    PRINT_TASK_TREATMENTS,
    print_treatment_for_learner_action,
)


class PrintPageForm(TypedDict):
    """One teaching block mapped to a Print catalogue / page object id."""

    teaching_block_id: str
    print_object: str
    lane: str
    reason: str


def _as_plan(plan: TeachingPlan | Mapping[str, Any]) -> TeachingPlan:
    if isinstance(plan, TeachingPlan):
        return plan
    return TeachingPlan.model_validate(plan)


def _as_composition(
    plan: CompositionPlan | TeachingPlan | Mapping[str, Any],
) -> CompositionPlan:
    if isinstance(plan, CompositionPlan):
        return plan
    if isinstance(plan, TeachingPlan):
        return realize_print_document(plan)
    if isinstance(plan, Mapping) and plan.get("path") == "print" and "decisions" in plan:
        return CompositionPlan.model_validate(plan)
    return realize_print_document(plan)


def _action_for(block: TeachingPlanBlock) -> str | None:
    if block.learner_action is None:
        return None
    return str(block.learner_action.action or "").strip() or None


def _decide_block(block: TeachingPlanBlock) -> CompositionDecision:
    action = _action_for(block)
    intent = (block.intent or "").strip().lower().replace("_", "-")
    treatment = print_treatment_for_learner_action(action, intent=intent)
    if treatment is not None:
        return CompositionDecision(
            teaching_block_id=block.id,
            kind=treatment,
            lane="print_task",
            reason=f"learner_action {action!r} → Print task {treatment!r}",
        )

    kind, reason = choose_document_primitive(block)
    return CompositionDecision(
        teaching_block_id=block.id,
        kind=kind,
        lane="document",
        reason=reason,
    )


def realize_print_document(
    teaching_plan: TeachingPlan | Mapping[str, Any],
) -> CompositionPlan:
    """Build an ordered Print composition plan from an approved Teaching Plan."""
    plan = _as_plan(teaching_plan)
    decisions: list[CompositionDecision] = []
    for section in plan.sections:
        for block in section.blocks:
            decisions.append(_decide_block(block))

    for decision in decisions:
        if decision.kind in LEGACY_LEARN_COMPONENT_IDS:
            raise ValueError(
                f"Print realizer emitted legacy Learn component id {decision.kind!r}"
            )
        if decision.lane == "document" and decision.kind not in DOCUMENT_PRIMITIVE_KINDS:
            raise ValueError(f"illegal document kind on Print plan: {decision.kind!r}")
        if decision.lane == "print_task" and decision.kind not in PRINT_TASK_OBJECTS:
            raise ValueError(f"illegal Print task object: {decision.kind!r}")
        if decision.lane == "learn_interaction":
            raise ValueError("Print composition plan must not include Learn interactions")

    return CompositionPlan(
        path="print",
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=plan.revision,
        decisions=decisions,
    )


def realize_print_to_page_forms(
    plan: CompositionPlan | TeachingPlan | Mapping[str, Any],
) -> list[PrintPageForm]:
    """Map composition decisions to Print page/catalogue object ids.

    Ordinary document primitives go through ``document_form_map.to_print_object``;
    Print task treatments (questions / choices / worked-example) pass through.
    """
    composition = _as_composition(plan)
    forms: list[PrintPageForm] = []
    for decision in composition.decisions:
        if decision.lane == "document":
            if decision.kind not in DOCUMENT_PRIMITIVE_KINDS:
                raise ValueError(
                    f"cannot map non-primitive document kind {decision.kind!r}"
                )
            print_object = to_print_object(decision.kind)  # type: ignore[arg-type]
            forms.append(
                {
                    "teaching_block_id": decision.teaching_block_id,
                    "print_object": print_object,
                    "lane": decision.lane,
                    "reason": decision.reason,
                }
            )
            continue
        if decision.lane == "print_task":
            if decision.kind not in PRINT_TASK_TREATMENTS:
                raise ValueError(f"unknown Print task treatment {decision.kind!r}")
            forms.append(
                {
                    "teaching_block_id": decision.teaching_block_id,
                    "print_object": decision.kind,
                    "lane": decision.lane,
                    "reason": decision.reason,
                }
            )
            continue
        raise ValueError(f"unsupported composition lane {decision.lane!r}")
    return forms


def produce_print_document_plan_from_teaching(
    teaching_plan: TeachingPlan | Mapping[str, Any],
) -> dict[str, Any]:
    """Additive document-path plan: composition decisions + Print object mapping.

    Does not replace the whole-lesson PDF FormPlan pipeline — callers that still
    need catalogue selection should use ``build_closed_print_production_plan*``.
    """
    composition = realize_print_document(teaching_plan)
    page_forms = realize_print_to_page_forms(composition)
    return {
        "composition_plan": composition,
        "page_forms": page_forms,
        "print_objects": [form["print_object"] for form in page_forms],
    }


__all__ = [
    "PrintPageForm",
    "produce_print_document_plan_from_teaching",
    "realize_print_document",
    "realize_print_to_page_forms",
]
