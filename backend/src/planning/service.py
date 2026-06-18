from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any
from uuid import uuid4

from pydantic_ai import Agent

from planning.fallback import build_fallback_spec
from planning.dtos import BriefRequest, GenerationSpec
from planning.models import (
    PlanningGenerationSpec,
    PlanningTemplateContract,
    StudioBriefRequest,
    TemplateAlternative,
    TemplateDecision,
)
from planning.normalizer import normalize_brief
from planning.prompt_builder import refine_plan_text
from planning.section_composer import compose_sections
from planning.template_scorer import choose_template
from planning.visual_router import route_visuals
from core.entities.student_profile import TeacherProfile


PlanningEvent = dict[str, object]
PlanningEmitter = Callable[[PlanningEvent], Awaitable[None] | None]
logger = logging.getLogger(__name__)
_LIVE_PRESET_ID = "blue-classroom"
_DEFAULT_TEMPLATE_ID = "guided-concept-path"


def _transition_anchor(section) -> str:
    return section.focus_note or section.objective or section.rationale or section.title


def _default_transition_note(previous_section, current_section) -> str | None:
    if previous_section is None:
        return None

    previous_anchor = _transition_anchor(previous_section) or previous_section.title
    current_anchor = current_section.objective or current_section.focus_note or current_section.rationale
    if current_anchor:
        current_anchor = current_anchor[0].lower() + current_anchor[1:]
    else:
        current_anchor = f"moves into the {current_section.role} role"
    return f"The previous section established {previous_anchor}; this section now {current_anchor}."


def _ensure_transition_notes(sections):
    previous_section = None
    for section in sections:
        if section.transition_note is None:
            section.transition_note = _default_transition_note(previous_section, section)
        previous_section = section
    return sections


def _forced_template_decision(
    *,
    forced_contract: PlanningTemplateContract,
    recommended_contract: PlanningTemplateContract,
    recommended_decision: TemplateDecision,
) -> TemplateDecision:
    if forced_contract.id == recommended_contract.id:
        return TemplateDecision(
            chosen_id=forced_contract.id,
            chosen_name=forced_contract.name,
            rationale=f"Teacher selected {forced_contract.name} during review, and it remains the best fit for this brief.",
            fit_score=recommended_decision.fit_score,
            alternatives=recommended_decision.alternatives,
        )

    carried_alternatives = [
        alternative
        for alternative in recommended_decision.alternatives
        if alternative.template_id != forced_contract.id
    ]
    return TemplateDecision(
        chosen_id=forced_contract.id,
        chosen_name=forced_contract.name,
        rationale=(
            f"Teacher selected {forced_contract.name} during review, so it overrides the "
            f"top recommendation of {recommended_contract.name}."
        ),
        fit_score=1.0,
        alternatives=[
            TemplateAlternative(
                template_id=recommended_contract.id,
                template_name=recommended_contract.name,
                fit_score=recommended_decision.fit_score,
                why_not_chosen=(
                    f"Top fit for the brief, but the teacher kept {forced_contract.name}."
                ),
            ),
            *carried_alternatives[:2],
        ],
    )


class PlanningService:
    async def plan(
        self,
        brief: StudioBriefRequest,
        *,
        contracts: list[PlanningTemplateContract],
        model: Any,
        run_llm_fn: Callable[..., Awaitable[Any]],
        generation_id: str = "",
        emit: PlanningEmitter | None = None,
    ) -> PlanningGenerationSpec:
        forced_contract: PlanningTemplateContract | None = None
        if brief.forced_template_id:
            forced_contract = next(
                (c for c in contracts if c.id == brief.forced_template_id), None
            )
            if forced_contract is None:
                raise ValueError(
                    f"Forced template '{brief.forced_template_id}' not in live-safe catalog."
                )

        normalized = await normalize_brief(
            brief,
            model=model,
            run_llm_fn=run_llm_fn,
            generation_id=generation_id,
        )
        recommended_contract, recommended_decision = choose_template(normalized, contracts)
        if forced_contract is not None:
            decision = _forced_template_decision(
                forced_contract=forced_contract,
                recommended_contract=recommended_contract,
                recommended_decision=recommended_decision,
            )
            selected_contract = forced_contract
        else:
            selected_contract, decision = recommended_contract, recommended_decision
        early_rationale = decision.rationale

        if emit is not None:
            maybe_result = emit(
                {
                    "event": "template_selected",
                    "data": {
                        "template_decision": decision.model_dump(mode="json"),
                        "lesson_rationale": early_rationale,
                        "warning": normalized.scope_warning,
                    },
                }
            )
            if maybe_result is not None:
                await maybe_result

        sections = await compose_sections(
            normalized,
            selected_contract,
            model=model,
            run_llm_fn=run_llm_fn,
            generation_id=generation_id,
        )
        sections = _ensure_transition_notes(sections)
        sections = await route_visuals(
            normalized,
            selected_contract,
            sections,
            model=model,
            run_llm_fn=run_llm_fn,
            generation_id=generation_id,
        )
        sections = _ensure_transition_notes(sections)

        if emit is not None:
            for section in sections:
                maybe_result = emit(
                    {
                        "event": "section_planned",
                        "data": {"section": section.model_dump(mode="json")},
                    }
                )
                if maybe_result is not None:
                    await maybe_result

        refined = await refine_plan_text(
            brief=normalized,
            contract=selected_contract,
            sections=sections,
            model=model,
            run_llm_fn=run_llm_fn,
            generation_id=generation_id,
        )
        if refined is not None:
            for section, refined_section in zip(sections, refined.sections, strict=True):
                section.title = refined_section.title
                section.rationale = refined_section.rationale
                section.transition_note = refined_section.transition_note
                section.terms_to_define = list(refined_section.terms_to_define)
                section.terms_assumed = list(refined_section.terms_assumed)
                section.practice_target = refined_section.practice_target
            sections = _ensure_transition_notes(sections)
            lesson_rationale = refined.lesson_rationale
            warning = refined.warning or normalized.scope_warning
        else:
            sections = _ensure_transition_notes(sections)
            lesson_rationale = early_rationale
            warning = normalized.scope_warning

        return PlanningGenerationSpec(
            id=generation_id or uuid4().hex,
            template_id=selected_contract.id,
            mode=brief.mode,
            template_decision=decision,
            lesson_rationale=lesson_rationale,
            directives=normalized.directives,
            committed_budgets=selected_contract.component_budget,
            sections=sections,
            warning=warning,
            source_brief_id=brief.source_brief_id(),
            source_brief=brief,
            status="draft",
        )

    def fallback(
        self,
        brief: StudioBriefRequest,
        *,
        contracts: list[PlanningTemplateContract],
    ) -> PlanningGenerationSpec:
        chosen = next(
            (contract for contract in contracts if contract.id == "guided-concept-path"),
            contracts[0],
        )
        return build_fallback_spec(brief=brief, contract=chosen)


@dataclass(frozen=True)
class TemplateSummary:
    id: str
    name: str
    intent: str
    learner_fit: list[str]


def _template_lines(templates: list[TemplateSummary]) -> str:
    return "\n".join(
        f"- {template.id} | {template.name} | intent: {template.intent} | learnerFit: {', '.join(template.learner_fit) or 'n/a'}"
        for template in templates
    )


def _build_system_prompt(
    *,
    brief: BriefRequest,
    profile: TeacherProfile | None,
    templates: list[TemplateSummary],
) -> str:
    _ = profile
    return "\n".join(
        [
            "You are the Teacher Studio brief interpreter.",
            f"Current live preset: {_LIVE_PRESET_ID}.",
            "Only choose from the provided live-safe template catalog.",
            "Short-form lessons only. Each section should cover one focused idea.",
            "If the topic would need more than 4 sections to cover adequately, it is too broad - flag this in warning and scope down to what fits in 3-4 sections.",
            "Return only valid JSON matching the schema. No preamble.",
            "Schema fields:",
            "- template_id",
            "- preset_id",
            "- section_count",
            "- sections [{ section_id, position, title, focus, role, required_components, optional_components, interaction_policy, diagram_policy, enrichment_enabled, continuity_notes }]",
            "- warning",
            "- rationale",
            "- source_brief { intent, audience, extra_context }",
            "Brief:",
            f"- intent: {brief.intent}",
            f"- audience: {brief.audience}",
            f"- extra_context: {brief.extra_context or 'none'}",
            "Live-safe templates:",
            _template_lines(templates),
        ]
    )


def _build_user_prompt(brief: BriefRequest) -> str:
    return "\n".join(
        [
            "Plan the brief using the live-safe template catalog.",
            f"Intent: {brief.intent}",
            f"Audience: {brief.audience}",
            f"Extra context: {brief.extra_context or 'none'}",
            "Choose the best template, keep the lesson short-form, and draft 2-4 sections.",
        ]
    )


def _fallback_sections():
    from pipeline.types.requests import SectionPlan

    return [
        SectionPlan(
            section_id="section-1",
            position=1,
            title="Core Idea",
            focus="Introduce the central concept in simple terms.",
            role="intro",
        ),
        SectionPlan(
            section_id="section-2",
            position=2,
            title="Worked Example",
            focus="Show the idea in action with one concrete example.",
            role="develop",
            needs_worked_example=True,
            required_components=["worked_example"],
        ),
        SectionPlan(
            section_id="section-3",
            position=3,
            title="Check Understanding",
            focus="Close with a short check that confirms the learner can explain it back.",
            role="practice",
            required_components=["practice", "what_next"],
        ),
    ]


def _fallback_spec(brief: BriefRequest) -> GenerationSpec:
    return GenerationSpec(
        template_id=_DEFAULT_TEMPLATE_ID,
        preset_id=_LIVE_PRESET_ID,
        mode=brief.mode,
        section_count=3,
        sections=_fallback_sections(),
        warning="Topic is broad. Narrow it to one lesson-sized arc if you want a tighter plan.",
        rationale="guided-concept-path keeps the lesson focused and easy to review.",
        source_brief=brief,
    )


class BriefPlannerService:
    async def plan(
        self,
        brief: BriefRequest,
        *,
        profile: TeacherProfile | None,
        templates: list[TemplateSummary],
        model: Any,
        run_llm_fn: Callable[..., Awaitable[Any]],
        generation_id: str = "",
    ) -> GenerationSpec:
        if not templates:
            raise RuntimeError("No live-safe templates were available for the brief planner.")

        system_prompt = _build_system_prompt(brief=brief, profile=profile, templates=templates)
        user_prompt = _build_user_prompt(brief)
        fallback = _fallback_spec(brief)

        agent = Agent(
            model=model,
            output_type=GenerationSpec,
            system_prompt=system_prompt,
        )

        for attempt in range(2):
            try:
                result = await run_llm_fn(
                    generation_id=generation_id,
                    node="brief_planner",
                    agent=agent,
                    model=model,
                    user_prompt=user_prompt,
                )
                spec = result.output
                if spec is None:
                    raise ValueError("Missing GenerationSpec output.")
                return spec
            except Exception as exc:
                logger.warning("Brief planning attempt %s failed: %s", attempt + 1, exc)
                if attempt == 1:
                    return fallback

        return fallback
