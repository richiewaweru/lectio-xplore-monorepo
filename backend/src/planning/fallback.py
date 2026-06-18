from __future__ import annotations

from uuid import uuid4

from planning.models import (
    GenerationDirectives,
    PlanningGenerationSpec,
    PlanningSectionPlan,
    PlanningTemplateContract,
    StudioBriefRequest,
    TemplateDecision,
)


def _fallback_components(
    contract: PlanningTemplateContract,
    role: str,
    defaults: tuple[str, ...],
) -> list[str]:
    if contract.section_role_defaults.get(role):
        return list(contract.section_role_defaults[role])
    pool = {*(contract.always_present or []), *(contract.available_components or [])}
    return [component for component in defaults if component in pool]


def build_fallback_spec(
    *,
    brief: StudioBriefRequest,
    contract: PlanningTemplateContract,
) -> PlanningGenerationSpec:
    spec_id = uuid4().hex
    return PlanningGenerationSpec(
        id=spec_id,
        template_id=contract.id,
        mode=brief.mode,
        template_decision=TemplateDecision(
            chosen_id=contract.id,
            chosen_name=contract.name,
            rationale=f"{contract.name} is the safest default when planning needs to fall back.",
            fit_score=0.5,
            alternatives=[],
        ),
        lesson_rationale="This fallback keeps the lesson compact and easy to review before generation.",
        directives=GenerationDirectives(
            tone_profile=brief.preferences.tone,
            reading_level=brief.preferences.reading_level,
            explanation_style=brief.preferences.explanation_style,
            example_style=brief.preferences.example_style,
            scaffold_level="medium",
            brevity=brief.preferences.brevity,
        ),
        committed_budgets=contract.component_budget,
        sections=[
            PlanningSectionPlan(
                id="section-intro",
                order=1,
                role="intro",
                title="Introduction",
                objective="Set the lesson up clearly.",
                transition_note=None,
                selected_components=_fallback_components(
                    contract,
                    "intro",
                    ("hook-hero", "callout-block", "key-fact"),
                ),
                rationale="Starts with a focused introduction.",
            ),
            PlanningSectionPlan(
                id="section-explain",
                order=2,
                role="explain",
                title="Explanation",
                objective="Explain the central idea plainly.",
                transition_note=(
                    "The introduction established the lesson focus; this section now explains the central idea plainly."
                ),
                selected_components=_fallback_components(
                    contract,
                    "explain",
                    ("explanation-block", "definition-card", "worked-example-card"),
                ),
                rationale="Provides the core explanation in the middle of the lesson.",
            ),
            PlanningSectionPlan(
                id="section-summary",
                order=3,
                role="summary",
                title="Summary",
                objective="Close the lesson and point to what comes next.",
                transition_note=(
                    "The explanation established the core idea; this section now closes the lesson and points to what comes next."
                ),
                selected_components=_fallback_components(
                    contract,
                    "summary",
                    ("summary-block", "what-next-bridge", "reflection-prompt"),
                ),
                rationale="Closes the arc cleanly.",
            ),
        ],
        warning="Planning used defaults - please review and adjust before generating.",
        source_brief_id=brief.source_brief_id(),
        source_brief=brief,
        status="draft",
    )
