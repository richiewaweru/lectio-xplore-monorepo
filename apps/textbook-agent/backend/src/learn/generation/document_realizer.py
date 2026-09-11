"""Learn document realizer — Teaching Plan → compact composition plan.

Ordinary content uses shared document primitives. A retained interaction is
added only when learner_action requires a response (Learn-owned action map).
"""

from __future__ import annotations

from typing import Any, Mapping

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composition import CompositionDecision, CompositionPlan
from document.heuristics import choose_document_primitive
from document.models import DOCUMENT_PRIMITIVE_KINDS
from learn.interactions.action_map import (
    ACTION_TO_LEARN_INTERACTION,
    PASSIVE_LEARNER_ACTIONS,
)
from learn.interactions.registry import (
    RETAINED_INTERACTIONS,
    RETIRED_ORDINARY_CONTENT_IDS,
)

# Print-owned surfaces that must never appear on Learn composition plans.
# Local denylist — do not import print/ (domain boundary).
_FORBIDDEN_PRINT_SURFACES: frozenset[str] = frozenset(
    {
        "ruled_lines",
        "page_break",
        "answer-key",
        "working-space",
        "questions",
        "choices",
        "worked-example",
    }
)


def _as_plan(plan: TeachingPlan | Mapping[str, Any]) -> TeachingPlan:
    if isinstance(plan, TeachingPlan):
        return plan
    return TeachingPlan.model_validate(plan)


def _action_for(block: TeachingPlanBlock) -> str | None:
    if block.learner_action is None:
        return None
    return str(block.learner_action.action or "").strip() or None


def _decide_block(
    block: TeachingPlanBlock,
    *,
    section_id: str | None,
) -> list[CompositionDecision]:
    """Return document decision, plus optional interaction when response is required."""
    action = _action_for(block)
    kind, reason = choose_document_primitive(block)
    decisions = [
        CompositionDecision(
            teaching_block_id=block.id,
            kind=kind,
            lane="document",
            reason=reason,
            section_id=section_id,
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
            section_id=section_id,
        )
    )
    return decisions


def realize_learn_document(
    teaching_plan: TeachingPlan | Mapping[str, Any],
) -> CompositionPlan:
    """Build an ordered Learn composition plan from an approved Teaching Plan.

    Deterministic heuristic fallback. Production prefers the LLM composer when
    a provider is available (see document.composer).
    """
    plan = _as_plan(teaching_plan)
    decisions: list[CompositionDecision] = []
    for section in plan.sections:
        section_id = str(section.slot_id or "")
        for block in section.blocks:
            decisions.extend(_decide_block(block, section_id=section_id or None))

    for decision in decisions:
        if decision.kind in RETIRED_ORDINARY_CONTENT_IDS:
            raise ValueError(
                f"Learn realizer emitted legacy component id {decision.kind!r}"
            )
        if decision.kind in _FORBIDDEN_PRINT_SURFACES:
            raise ValueError(
                f"Learn realizer emitted Print-only object {decision.kind!r}"
            )
        if decision.lane == "document" and decision.kind not in DOCUMENT_PRIMITIVE_KINDS:
            raise ValueError(f"illegal document kind on Learn plan: {decision.kind!r}")
        if (
            decision.lane == "learn_interaction"
            and decision.kind not in RETAINED_INTERACTIONS
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
