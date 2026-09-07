"""Production semantic component selector (narrowed candidates only).

Heuristic selection remains for tests, fixtures, and Studio rollback.
This module never falls back to the heuristic after a semantic failure.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from resource_specs.component_candidates import RoleCandidateSet
from v3_blueprint.planning.canonical_plan import (
    SelectionValidationError,
    SelectorChoice,
    validate_selector_choice,
)

ChooseFn = Callable[[dict[str, Any]], Awaitable[SelectorChoice] | SelectorChoice]


def lesson_context_from_inputs(
    *,
    form: Any | None = None,
    signals: Any | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if form is not None:
        context.update(
            {
                "subject": getattr(form, "subject", None),
                "grade_level": getattr(form, "grade_level", None),
                "learner_level": getattr(form, "learner_level", None),
                "topic": getattr(form, "topic", None),
                "outcome": getattr(form, "outcome", None),
            }
        )
    if signals is not None:
        context.update(
            {
                "topic": getattr(signals, "topic", None) or context.get("topic"),
                "teacher_goal": getattr(signals, "teacher_goal", None),
                "inferred_lesson_mode": getattr(signals, "inferred_lesson_mode", None),
            }
        )
    return {key: value for key, value in context.items() if value not in (None, "")}


def candidates_from_selector_context(context: Mapping[str, Any]) -> RoleCandidateSet:
    allowed = context.get("allowed_components") or []
    ids = tuple(
        str(card["component_id"])
        for card in allowed
        if isinstance(card, dict) and isinstance(card.get("component_id"), str)
    )
    return RoleCandidateSet(
        role=str(context.get("role") or ""),
        resource_type="lesson",
        template_id="guided-concept-path",
        preferred=ids,
        allowed=ids,
        candidates=ids,
        component_budget=dict(context.get("component_budget") or {}),
        max_per_section=dict(context.get("max_per_section") or {}),
        excluded={},
    )


async def select_with_validation_and_repair(
    context: dict[str, Any],
    *,
    choose: ChooseFn,
    candidates: RoleCandidateSet | None = None,
    remaining_budget: Mapping[str, int] | None = None,
) -> SelectorChoice:
    """Attempt → validate → one constrained repair with exact errors → validate again."""
    import inspect

    candidate_set = candidates or candidates_from_selector_context(context)
    budget = remaining_budget or context.get("component_budget") or candidate_set.component_budget

    async def _call(payload: dict[str, Any]) -> SelectorChoice:
        result = choose(payload)
        if inspect.isawaitable(result):
            return await result
        return result

    choice = await _call(context)
    errors = validate_selector_choice(
        choice,
        candidates=candidate_set,
        remaining_budget=budget,
    )
    if not errors:
        return choice

    repair_payload = {
        **context,
        "validation_errors": errors,
        "repair": True,
        "instruction": (
            "Your previous selection was invalid. Repair using only allowed_components. "
            "Do not change the section purpose. Do not pick a different pedagogical role."
        ),
    }
    choice = await _call(repair_payload)
    errors = validate_selector_choice(
        choice,
        candidates=candidate_set,
        remaining_budget=budget,
    )
    if errors:
        raise SelectionValidationError(errors)
    return choice


async def run_lectio_semantic_selector(
    context: dict[str, Any],
    *,
    choose: ChooseFn | None = None,
    trace_id: str | None = None,
) -> SelectorChoice:
    """Production selector: LLM (or injected choose) + one validation repair. No heuristic."""
    payload = dict(context)
    if trace_id:
        payload["trace_id"] = trace_id
    return await select_with_validation_and_repair(
        payload,
        choose=choose or _default_llm_choose,
    )


async def _default_llm_choose(context: dict[str, Any]) -> SelectorChoice:
    from curriculum.agents import run_component_selector

    trace_id = context.get("trace_id") if isinstance(context.get("trace_id"), str) else None
    payload = {key: value for key, value in context.items() if key != "trace_id"}
    selection = await run_component_selector(payload, trace_id=trace_id)
    return SelectorChoice.model_validate(selection.model_dump())
