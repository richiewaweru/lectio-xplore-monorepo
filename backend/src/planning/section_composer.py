from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from planning.llm_config import (
    PLANNING_BRIEF_INTERPRETER_CALLER,
    get_planning_slot,
)
from planning.models import (
    NormalizedBrief,
    PlanningSectionPlan,
    PlanningSectionRole,
    PlanningTemplateContract,
    SectionGenerationNotes,
)

logger = logging.getLogger(__name__)
_ROLE_COMPONENT_FALLBACKS: dict[PlanningSectionRole, tuple[str, ...]] = {
    "intro": ("hook-hero", "callout-block", "key-fact"),
    "explain": ("explanation-block", "definition-card", "worked-example-card"),
    "practice": ("practice-stack", "student-textbox", "short-answer", "fill-in-blank"),
    "summary": ("summary-block", "what-next-bridge", "reflection-prompt"),
    "process": ("process-steps", "worked-example-card", "explanation-block"),
    "compare": ("comparison-grid", "definition-family", "insight-strip", "explanation-block"),
    "timeline": ("timeline-block", "reflection-prompt", "explanation-block"),
    "visual": ("diagram-block", "diagram-series", "diagram-compare", "explanation-block"),
    "discover": ("simulation-block", "diagram-block", "callout-block", "explanation-block"),
}

_ROLE_TITLE_STEMS: dict[PlanningSectionRole, str] = {
    "intro": "Start with the central idea",
    "explain": "Build the explanation",
    "practice": "Put the idea to work",
    "summary": "Close and connect forward",
    "process": "Walk through the method",
    "compare": "Keep the distinctions visible",
    "timeline": "Follow the sequence",
    "visual": "Let the visual lead",
    "discover": "Explore before formalising",
}


class _SectionRolePlan(BaseModel):
    roles: list[PlanningSectionRole] = Field(default_factory=list)


def _allowed_roles_for_contract(contract: PlanningTemplateContract) -> list[PlanningSectionRole]:
    return list(contract.section_role_defaults.keys())


def _pick_role(
    allowed_roles: set[PlanningSectionRole],
    *candidates: PlanningSectionRole,
) -> PlanningSectionRole:
    for candidate in candidates:
        if candidate in allowed_roles:
            return candidate

    for candidate in allowed_roles:
        if candidate not in {"intro", "summary"}:
            return candidate

    return "explain"


def _section_count(brief: NormalizedBrief, contract: PlanningTemplateContract) -> int:
    if brief.brief.constraints.keep_short:
        return 3

    count = 4
    if brief.scope_warning:
        count += 1
    if brief.brief.constraints.more_practice:
        count += 1
    if contract.intent in {"teach-procedure", "teach-sequence", "compare-ideas"}:
        count += 1
    return max(3, min(5, count))


def _role_sequence(
    contract: PlanningTemplateContract,
    count: int,
    more_practice: bool,
) -> list[PlanningSectionRole]:
    allowed_roles = set(_allowed_roles_for_contract(contract))
    if contract.intent == "compare-ideas":
        preferred_roles: tuple[PlanningSectionRole, ...] = ("compare", "discover", "explain", "practice")
    elif contract.intent == "teach-sequence":
        preferred_roles = ("timeline", "discover", "explain", "practice")
    elif contract.intent == "teach-procedure":
        preferred_roles = ("process", "discover", "explain", "practice")
    elif contract.intent == "explain-visually":
        preferred_roles = ("visual", "discover", "explain", "practice")
    else:
        preferred_roles = ("discover", "explain", "practice")

    core_role = _pick_role(allowed_roles, *preferred_roles)
    explain_role = _pick_role(allowed_roles, "explain", core_role, "practice")
    practice_role = _pick_role(allowed_roles, "practice", explain_role, core_role)

    if count <= 3:
        return ["intro", core_role, "summary"]

    if count == 4:
        if more_practice:
            return ["intro", core_role, practice_role, "summary"]
        if core_role == explain_role:
            return ["intro", core_role, practice_role, "summary"]
        return ["intro", core_role, explain_role, "summary"]

    if core_role == explain_role:
        return ["intro", explain_role, explain_role, practice_role, "summary"]
    return ["intro", core_role, explain_role, practice_role, "summary"]


def _role_components(
    contract: PlanningTemplateContract,
    role: PlanningSectionRole,
) -> list[str]:
    direct = contract.section_role_defaults.get(role)
    if direct:
        return direct[:]
    fallback = _ROLE_COMPONENT_FALLBACKS.get(role, ())
    pool = {*(contract.always_present or []), *(contract.available_components or [])}
    return [component for component in fallback if component in pool]


def _remaining_budget(contract: PlanningTemplateContract) -> dict[str, int | None]:
    available = {*(contract.always_present or []), *(contract.available_components or [])}
    return {
        component: contract.component_budget.get(component)
        for component in available
    }


def _select_components_for_role(
    contract: PlanningTemplateContract,
    role: PlanningSectionRole,
    remaining_budget: dict[str, int | None],
) -> list[str]:
    selected: list[str] = []
    per_section_counts: dict[str, int] = {}
    candidates = _role_components(contract, role)

    for component in candidates:
        if component not in contract.available_components and component not in contract.always_present:
            continue
        remaining = remaining_budget.get(component)
        if remaining is not None and remaining <= 0:
            continue
        limit = contract.max_per_section.get(component)
        if limit is not None and per_section_counts.get(component, 0) >= limit:
            continue
        selected.append(component)
        per_section_counts[component] = per_section_counts.get(component, 0) + 1
        if remaining is not None:
            remaining_budget[component] = remaining - 1

    return selected


def _placeholder_title(role: PlanningSectionRole, order: int) -> str:
    stem = _ROLE_TITLE_STEMS.get(role, f"Section {order}")
    return stem if len(stem.split()) <= 8 else f"{role.replace('-', ' ').title()} {order}"


def _objective(role: PlanningSectionRole, intent: str) -> str:
    mapping = {
        "intro": "Frame the lesson so the teacher and learners know what this section is trying to unlock.",
        "explain": "Build the core explanation with enough clarity for the target audience.",
        "practice": "Give the learner a chance to use the idea directly.",
        "summary": "Close the section arc and point toward what comes next.",
        "process": "Make the method feel sequential and repeatable.",
        "compare": "Keep distinctions visible so the learner can classify confidently.",
        "timeline": "Use chronology to show how one step leads to the next.",
        "visual": "Let the visual anchor lead the understanding before extra prose adds detail.",
        "discover": "Use guided exploration to reveal the pattern before formalising it.",
    }
    return mapping.get(role, f"Support the lesson's {intent} intent.")


def _generation_notes(role: PlanningSectionRole) -> SectionGenerationNotes | None:
    if role == "practice":
        return SectionGenerationNotes(brevity_override="tight")
    if role == "summary":
        return SectionGenerationNotes(
            brevity_override="tight",
            tone_override="clear and conclusive",
        )
    return None


def _system_prompt() -> str:
    return "\n".join(
        [
            "You arrange a short lesson section flow for Teacher Studio.",
            "Keep the section count fixed.",
            "Return only valid JSON.",
            "Schema fields:",
            "- roles: ordered list of section roles",
            "Use only the allowed roles provided in the user prompt.",
            "The first role should usually be intro and the final role should be summary.",
        ]
    )


def _user_prompt(
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    *,
    count: int,
) -> str:
    available_roles = _allowed_roles_for_contract(contract)
    return "\n".join(
        [
            f"Intent: {brief.brief.intent}",
            f"Topic type: {brief.resolved_topic_type}",
            f"Learning outcome: {brief.resolved_learning_outcome}",
            f"Template: {contract.name} ({contract.intent})",
            f"Requested section count: {count}",
            f"More practice: {brief.brief.constraints.more_practice}",
            f"Use visuals: {brief.brief.constraints.use_visuals}",
            f"Keep short: {brief.brief.constraints.keep_short}",
            f"Template role defaults: {contract.section_role_defaults}",
            f"Allowed roles: {', '.join(available_roles)}",
            "Choose the most suitable ordered role sequence for this lesson.",
        ]
    )


def _roles_are_usable(
    roles: list[PlanningSectionRole],
    *,
    count: int,
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
) -> bool:
    allowed_roles = set(_allowed_roles_for_contract(contract))
    if len(roles) != count:
        return False
    if not roles or roles[0] != "intro" or roles[-1] != "summary":
        return False
    if any(role not in allowed_roles for role in roles):
        return False
    if count > 3 and brief.brief.constraints.more_practice and "practice" not in roles:
        return False
    if brief.resolved_topic_type == "process" and not any(
        role in {"process", "timeline"} for role in roles
    ):
        return False
    return True


async def _resolve_roles_with_llm(
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    *,
    count: int,
    model: Any | None,
    run_llm_fn: Callable[..., Awaitable[Any]] | None,
    generation_id: str,
) -> list[PlanningSectionRole] | None:
    if model is None or run_llm_fn is None:
        return None

    agent = Agent(
        model=model,
        output_type=_SectionRolePlan,
        system_prompt=_system_prompt(),
    )
    user_prompt = _user_prompt(brief, contract, count=count)

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
            if output is None or not _roles_are_usable(
                output.roles,
                count=count,
                brief=brief,
                contract=contract,
            ):
                raise ValueError("Planning section composer returned an unusable role sequence.")
            return output.roles
        except Exception as exc:
            logger.warning("Planning section composer attempt %s failed: %s", attempt + 1, exc)

    return None


async def compose_sections(
    brief: NormalizedBrief,
    contract: PlanningTemplateContract,
    *,
    model: Any | None = None,
    run_llm_fn: Callable[..., Awaitable[Any]] | None = None,
    generation_id: str = "",
) -> list[PlanningSectionPlan]:
    remaining_budget = _remaining_budget(contract)
    count = _section_count(brief, contract)
    fallback_roles = _role_sequence(
        contract,
        count,
        brief.brief.constraints.more_practice,
    )
    roles = await _resolve_roles_with_llm(
        brief,
        contract,
        count=count,
        model=model,
        run_llm_fn=run_llm_fn,
        generation_id=generation_id,
    )
    if roles is None:
        roles = fallback_roles

    sections: list[PlanningSectionPlan] = []
    for index, role in enumerate(roles, start=1):
        sections.append(
            PlanningSectionPlan(
                id=f"section-{uuid4().hex[:8]}",
                order=index,
                role=role,
                title=_placeholder_title(role, index),
                objective=_objective(role, contract.intent),
                selected_components=_select_components_for_role(contract, role, remaining_budget),
                generation_notes=_generation_notes(role),
                rationale=f"This section uses the {role} role to support the chosen {contract.name} lesson shape.",
            )
        )

    return sections
