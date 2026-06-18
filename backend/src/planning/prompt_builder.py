from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai import Agent

from planning.llm_config import (
    PLANNING_BRIEF_INTERPRETER_CALLER,
    get_planning_slot,
)
from planning.models import (
    NormalizedBrief,
    PlanningRefinementOutput,
    PlanningSectionPlan,
    PlanningTemplateContract,
)

logger = logging.getLogger(__name__)


def _system_prompt() -> str:
    return "\n".join(
        [
            "You refine lesson-plan text only.",
            "You will receive a fixed lesson structure.",
            "Do not change section count, section order, role, components, or visual policy.",
            "Return valid JSON only.",
            "For each section, write a concise title, one-sentence rationale, and one transition_note.",
            "The first section must have transition_note = null.",
            "For later sections, transition_note must say what the prior section established and what this section now does with it.",
            "Also assign terms_to_define, terms_assumed, and practice_target per section.",
            "Each key term should be defined in exactly one section via terms_to_define.",
            "Later sections that reuse earlier terms should list them in terms_assumed.",
            "practice_target must state what the practice in that section should test.",
            "Write a short lesson rationale for the teacher and an optional warning.",
        ]
    )


def _user_prompt(
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    sections: list[PlanningSectionPlan],
) -> str:
    section_lines = "\n".join(
        (
            f"- order={section.order} role={section.role} "
            f"components={', '.join(section.selected_components) or 'none'} "
            f"objective={section.objective or 'n/a'} "
            f"focus_note={section.focus_note or 'n/a'} "
            f"current_transition_note={section.transition_note or 'null'} "
            f"current_terms_to_define={', '.join(section.terms_to_define) or 'none'} "
            f"current_terms_assumed={', '.join(section.terms_assumed) or 'none'} "
            f"current_practice_target={section.practice_target or 'none'}"
        )
        for section in sections
    )
    return "\n".join(
        [
            f"Intent: {brief.brief.intent}",
            f"Audience: {brief.brief.audience}",
            f"Prior knowledge: {brief.brief.prior_knowledge or 'none'}",
            f"Extra context: {brief.brief.extra_context or 'none'}",
            f"Template: {contract.name}",
            "Sections:",
            section_lines,
            (
                "Return JSON with keys: lesson_rationale, warning, "
                "sections[{title, rationale, transition_note, terms_to_define, terms_assumed, practice_target}]."
            ),
        ]
    )


async def refine_plan_text(
    *,
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    sections: list[PlanningSectionPlan],
    model: Any,
    run_llm_fn: Callable[..., Awaitable[Any]],
    generation_id: str = "",
) -> PlanningRefinementOutput | None:
    agent = Agent(
        model=model,
        output_type=PlanningRefinementOutput,
        system_prompt=_system_prompt(),
    )
    user_prompt = _user_prompt(brief, contract, sections)

    for attempt in range(2):
        try:
            result = await run_llm_fn(
                trace_id=generation_id,
                caller=PLANNING_BRIEF_INTERPRETER_CALLER,
                agent=agent,
                model=model,
                user_prompt=user_prompt,
                slot=get_planning_slot(PLANNING_BRIEF_INTERPRETER_CALLER),
            )
            output = result.output
            if output is None or len(output.sections) != len(sections):
                raise ValueError("Planning refinement returned an unexpected section count.")
            for refined_section in output.sections:
                if not refined_section.title or not refined_section.title.strip():
                    raise ValueError("Refined section has empty title.")
            if output.sections and output.sections[0].transition_note not in (None, ""):
                raise ValueError("The first refined section must not emit a transition note.")
            if len(output.sections) != len(sections):
                raise ValueError("Planning refinement must preserve section count.")
            return output
        except Exception as exc:
            logger.warning("Planning refinement attempt %s failed: %s", attempt + 1, exc)

    return None
