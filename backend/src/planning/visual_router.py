from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

import core.events as core_events
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from planning.llm_config import (
    PLANNING_BRIEF_INTERPRETER_CALLER,
    get_planning_slot,
)
from planning.models import (
    NormalizedBrief,
    PlanningSectionPlan,
    PlanningTemplateContract,
    PlanningVisualIntent,
    PlanningVisualMode,
    VisualPolicy,
)
from pipeline.types.requests import BlockVisualPlacement

logger = logging.getLogger(__name__)
_SPATIAL_HINTS = {
    "biology",
    "chemistry",
    "ecosystem",
    "cell",
    "atom",
    "heart",
    "anatomy",
    "river",
    "map",
    "planet",
    "cycle",
    "photosynthesis",
    "geography",
    "architecture",
    "geology",
    "organ",
    "molecule",
    "skeleton",
    "volcano",
    "ocean",
    "continent",
    "mountain",
    "weather",
    "circuit",
    "engine",
    "building",
    "bridge",
    "solar",
    "galaxy",
}

_GRAPH_HINTS = {
    "graph",
    "plot",
    "axes",
    "axis",
    "coordinate",
    "gradient",
    "slope",
    "derivative",
    "integral",
    "function",
    "equation",
    "curve",
    "tangent",
    "linear",
    "quadratic",
    "parabola",
    "intercept",
    "asymptote",
    "vector",
    "force",
    "velocity",
    "acceleration",
    "displacement",
    "distance",
    "frequency",
    "wavelength",
    "amplitude",
    "probability",
    "distribution",
    "histogram",
    "scatter",
    "correlation",
    "regression",
    "demand",
    "supply",
    "elasticity",
    "marginal",
    "revenue",
    "cost",
    "profit",
}


class _SectionVisualDecision(BaseModel):
    section_id: str
    required: bool = False
    intent: PlanningVisualIntent | None = None
    mode: PlanningVisualMode | None = None


class _VisualRoutingPlan(BaseModel):
    sections: list[_SectionVisualDecision] = Field(default_factory=list)


def _classify_spatial(brief: NormalizedBrief) -> bool:
    return any(keyword in _SPATIAL_HINTS for keyword in brief.keyword_profile)


def _classify_graph(brief: NormalizedBrief) -> bool:
    return any(keyword in _GRAPH_HINTS for keyword in brief.keyword_profile)


def _visual_intent(section: PlanningSectionPlan) -> PlanningVisualIntent:
    if section.role == "process":
        return "demonstrate_process"
    if section.role == "compare":
        return "compare_variants"
    if section.role in {"visual", "discover"}:
        return "show_realism"
    return "explain_structure"


def _visual_mode(brief: NormalizedBrief, intent: str) -> PlanningVisualMode:
    if intent in {"show_realism", "demonstrate_process", "compare_variants"}:
        return "image"
    if _classify_spatial(brief):
        return "image"
    if _classify_graph(brief):
        return "image"
    return "svg"


def _derive_visual_placements(
    *,
    section: PlanningSectionPlan,
    contract: PlanningTemplateContract,
    intent: PlanningVisualIntent,
    should_visualize: bool,
) -> list[BlockVisualPlacement]:
    if not should_visualize:
        return []

    available = set(contract.available_components)
    selected = set(section.selected_components)

    if "diagram-compare" in selected or (
        intent == "compare_variants" and "diagram-compare" in available
    ):
        return [
            BlockVisualPlacement(
                block="explanation",
                slot_type="diagram_compare",
                hint="Use an explanation-adjacent comparison visual.",
            )
        ]

    if "diagram-series" in selected or (
        intent == "demonstrate_process" and "diagram-series" in available
    ):
        return [
            BlockVisualPlacement(
                block="explanation",
                slot_type="diagram_series",
                hint="Use an explanation-adjacent sequence visual.",
            )
        ]

    if "diagram-block" in selected or "diagram-block" in available:
        return [
            BlockVisualPlacement(
                block="explanation",
                slot_type="diagram",
                hint="Use an explanation-adjacent diagram.",
            )
        ]

    return []


def _system_prompt() -> str:
    return "\n".join(
        [
            "You decide visual intent for planned lesson sections.",
            "Only set visuals when they help comprehension and the template supports them.",
            "Return valid JSON only.",
            "Schema fields:",
            "- sections [{ section_id, required, intent, mode }]",
            "If required is false, intent and mode may be null.",
        ]
    )


def _user_prompt(
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    sections: list[PlanningSectionPlan],
) -> str:
    section_lines = "\n".join(
        f"- id={section.id} role={section.role} components={', '.join(section.selected_components) or 'none'} objective={section.objective or 'n/a'}"
        for section in sections
    )
    return "\n".join(
        [
            f"Intent: {brief.brief.intent}",
            f"Topic type: {brief.resolved_topic_type}",
            f"Learning outcome: {brief.resolved_learning_outcome}",
            f"Use visuals: {brief.brief.constraints.use_visuals}",
            f"Print first: {brief.brief.constraints.print_first}",
            f"Keyword profile: {', '.join(brief.keyword_profile) or 'none'}",
            f"Template: {contract.name} ({contract.intent})",
            f"Available components: {', '.join(contract.available_components) or 'none'}",
            "Sections:",
            section_lines,
        ]
    )


def _fallback_decision(
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    section: PlanningSectionPlan,
    *,
    visual_supported: set[str],
) -> _SectionVisualDecision:
    should_visualize = bool(
        visual_supported
        and (
            set(section.selected_components).intersection(visual_supported)
            or brief.brief.constraints.use_visuals
            or section.role in {"visual", "process", "compare", "discover"}
        )
    )
    intent = _visual_intent(section)
    mode = _visual_mode(brief, intent)
    return _SectionVisualDecision(
        section_id=section.id,
        required=should_visualize,
        intent=intent if should_visualize else None,
        mode=mode if should_visualize else None,
    )


async def _resolve_with_llm(
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    sections: list[PlanningSectionPlan],
    *,
    model: Any | None,
    run_llm_fn: Callable[..., Awaitable[Any]] | None,
    generation_id: str,
) -> dict[str, _SectionVisualDecision] | None:
    if model is None or run_llm_fn is None:
        return None

    agent = Agent(
        model=model,
        output_type=_VisualRoutingPlan,
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
                raise ValueError("Planning visual router returned an unexpected section count.")
            decisions = {section.section_id: section for section in output.sections}
            if len(decisions) != len(sections):
                raise ValueError("Planning visual router returned duplicate section ids.")
            missing_ids = [section.id for section in sections if section.id not in decisions]
            if missing_ids:
                raise ValueError(f"Planning visual router missed sections: {missing_ids!r}")
            for decision in decisions.values():
                if decision.required and (decision.intent is None or decision.mode is None):
                    raise ValueError("Planning visual router omitted intent or mode for a required visual.")
            return decisions
        except Exception as exc:
            logger.warning("Planning visual router attempt %s failed: %s", attempt + 1, exc)

    return None


async def route_visuals(
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    sections: list[PlanningSectionPlan],
    *,
    model: Any | None = None,
    run_llm_fn: Callable[..., Awaitable[Any]] | None = None,
    generation_id: str = "",
) -> list[PlanningSectionPlan]:
    visual_components = {"diagram-block", "diagram-series", "diagram-compare", "simulation-block"}
    visual_supported = visual_components.intersection(contract.available_components)
    llm_decisions = await _resolve_with_llm(
        brief,
        contract,
        sections,
        model=model,
        run_llm_fn=run_llm_fn,
        generation_id=generation_id,
    )

    for section in sections:
        decision = (
            llm_decisions.get(section.id)
            if llm_decisions is not None
            else _fallback_decision(brief, contract, section, visual_supported=visual_supported)
        )
        intent = decision.intent or _visual_intent(section)
        mode = decision.mode or _visual_mode(brief, intent)
        placements = _derive_visual_placements(
            section=section,
            contract=contract,
            intent=intent,
            should_visualize=bool(decision.required and visual_supported),
        )
        section.visual_placements = placements
        section.visual_policy = VisualPolicy(
            required=bool(placements),
            intent=intent if placements else None,
            mode=mode if placements else None,
            goal={
                "demonstrate_process": "Show the sequence or method clearly enough that the learner can follow each step.",
                "compare_variants": "Put the alternatives in view so the learner can spot the difference that matters.",
                "show_realism": "Ground the section in a realistic visual anchor the learner can point at.",
                "explain_structure": "Show the important structure or relationship the section is describing.",
            }[intent]
            if placements
            else None,
            style_notes=(
                "Clean structural diagram, labeled nodes, clear arrows."
                if mode == "svg"
                else "Classroom-friendly educational image, accurate labels, no decorative clutter."
            )
            if placements
            else None,
        )
        if generation_id:
            core_events.event_bus.publish(
                generation_id,
                {
                    "type": "visual_placements_committed",
                    "generation_id": generation_id,
                    "section_id": section.id,
                    "placements_count": len(placements),
                    "placements_summary": [
                        f"{placement.block}:{placement.slot_type}:{placement.sizing}"
                        for placement in placements
                    ],
                },
            )

    return sections
