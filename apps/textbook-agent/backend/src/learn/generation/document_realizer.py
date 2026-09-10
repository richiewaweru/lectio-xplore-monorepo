"""Learn document realizer — Teaching Plan → compact composition plan (Phase E).

Deterministic heuristics only. Passive content uses shared document primitives.
A retained interaction is added only when learner_action requires a response.
"""

from __future__ import annotations

from typing import Any, Mapping

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composition import (
    ACTION_TO_LEARN_INTERACTION,
    DOCUMENT_PRIMITIVE_KINDS,
    LEGACY_LEARN_COMPONENT_IDS,
    LEARN_RETAINED_INTERACTIONS,
    PASSIVE_LEARNER_ACTIONS,
    PRINT_ONLY_LAYOUT_OBJECTS,
    CompositionDecision,
    CompositionPlan,
)
from document.heuristics import choose_document_primitive


def _as_plan(plan: TeachingPlan | Mapping[str, Any]) -> TeachingPlan:
    if isinstance(plan, TeachingPlan):
        return plan
    return TeachingPlan.model_validate(plan)


def _action_for(block: TeachingPlanBlock) -> str | None:
    if block.learner_action is None:
        return None
    return str(block.learner_action.action or "").strip() or None


def _decide_block(block: TeachingPlanBlock) -> list[CompositionDecision]:
    """Return document decision, plus optional interaction when response is required."""
    action = _action_for(block)
    kind, reason = choose_document_primitive(block)
    decisions = [
        CompositionDecision(
            teaching_block_id=block.id,
            kind=kind,
            lane="document",
            reason=reason,
        )
    ]

    if not action or action in PASSIVE_LEARNER_ACTIONS:
        return decisions

    interaction = ACTION_TO_LEARN_INTERACTION.get(action)
    if interaction is None:
        # Unknown response action: keep document form only; do not invent UI.
        return decisions

    decisions.append(
        CompositionDecision(
            teaching_block_id=block.id,
            kind=interaction,
            lane="learn_interaction",
            reason=f"learner_action {action!r} → retained interaction {interaction!r}",
        )
    )
    return decisions


def realize_learn_document(
    teaching_plan: TeachingPlan | Mapping[str, Any],
) -> CompositionPlan:
    """Build an ordered Learn composition plan from an approved Teaching Plan."""
    plan = _as_plan(teaching_plan)
    decisions: list[CompositionDecision] = []
    for section in plan.sections:
        for block in section.blocks:
            decisions.extend(_decide_block(block))

    for decision in decisions:
        if decision.kind in LEGACY_LEARN_COMPONENT_IDS:
            raise ValueError(
                f"Learn realizer emitted legacy component id {decision.kind!r}"
            )
        if decision.kind in PRINT_ONLY_LAYOUT_OBJECTS:
            raise ValueError(
                f"Learn realizer emitted Print-only object {decision.kind!r}"
            )
        if decision.lane == "document" and decision.kind not in DOCUMENT_PRIMITIVE_KINDS:
            raise ValueError(f"illegal document kind on Learn plan: {decision.kind!r}")
        if (
            decision.lane == "learn_interaction"
            and decision.kind not in LEARN_RETAINED_INTERACTIONS
        ):
            raise ValueError(f"illegal Learn interaction: {decision.kind!r}")
        if decision.lane == "print_task":
            raise ValueError("Learn composition plan must not include Print task objects")

    return CompositionPlan(
        path="learn",
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=plan.revision,
        decisions=decisions,
    )


__all__ = ["realize_learn_document"]
