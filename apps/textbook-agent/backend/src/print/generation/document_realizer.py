"""Print document realizer — Teaching Plan → compact composition plan.

Ordinary content uses shared document primitives; learner tasks that require a
response become Print-only task treatments (print/generation/task_treatments).
"""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composition import CompositionDecision, CompositionPlan
from document.heuristics import choose_document_primitive
from document.models import DOCUMENT_PRIMITIVE_KINDS
from print.generation.document_form_map import to_print_object
from print.generation.task_treatments import (
    PRINT_TASK_TREATMENTS,
    print_treatment_for_learner_action,
)

# Local denylist of retired ordinary-component ids from the old Learn package.
# Keep Print free of product imports into the Learn domain.
_RETIRED_LEARN_ORDINARY_IDS: frozenset[str] = frozenset(
    {
        "ExplanationBlock",
        "section-header",
        "hook-hero",
        "explanation-block",
        "definition-card",
        "key-fact",
        "callout-block",
        "process-steps",
        "worked-example-card",
        "summary-block",
        "timeline-block",
        "diagram-compare",
        "quiz-check",
        "fill-in-blank",
        "diagram-block",
    }
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


def _decide_block(
    block: TeachingPlanBlock,
    *,
    section_id: str | None,
) -> CompositionDecision:
    action = _action_for(block)
    intent = (block.intent or "").strip().lower().replace("_", "-")
    treatment = print_treatment_for_learner_action(action, intent=intent)
    if treatment is not None:
        return CompositionDecision(
            teaching_block_id=block.id,
            kind=treatment,
            lane="print_task",
            reason=f"learner_action {action!r} → Print task {treatment!r}",
            section_id=section_id,
        )

    kind, reason = choose_document_primitive(block)
    return CompositionDecision(
        teaching_block_id=block.id,
        kind=kind,
        lane="document",
        reason=reason,
        section_id=section_id,
    )


def realize_print_document(
    teaching_plan: TeachingPlan | Mapping[str, Any],
) -> CompositionPlan:
    """Build an ordered Print composition plan from an approved Teaching Plan.

    Deterministic heuristic fallback. Production prefers the LLM composer when
    a provider is available (see document.composer).
    """
    plan = _as_plan(teaching_plan)
    decisions: list[CompositionDecision] = []
    for section in plan.sections:
        section_id = str(section.slot_id or "")
        for block in section.blocks:
            decisions.append(_decide_block(block, section_id=section_id or None))

    for decision in decisions:
        if decision.kind in _RETIRED_LEARN_ORDINARY_IDS:
            raise ValueError(
                f"Print realizer emitted legacy Learn component id {decision.kind!r}"
            )
        if decision.lane == "document" and decision.kind not in DOCUMENT_PRIMITIVE_KINDS:
            raise ValueError(f"illegal document kind on Print plan: {decision.kind!r}")
        if decision.lane == "print_task" and decision.kind not in PRINT_TASK_TREATMENTS:
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
    """Document-path plan: composition decisions + Print object mapping."""
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
