from __future__ import annotations

from v3_blueprint.models import (
    AnchorPlan,
    AnswerKeyPlan,
    BlueprintMetadata,
    ComponentPlan,
    LessonModePlan,
    ProductionBlueprint,
    QuestionPlanItem,
    RepairFocus,
    SectionPlan as BlueprintSection,
    VisualFrameInstruction,
    VisualInstruction,
    VisualStrategyPlan,
    VoicePlan,
)
from v3_blueprint.planning.models import (
    BlueprintAssemblyBlocked,
    SectionBrief,
    StructuralPlan,
)

VISUAL_CAPABLE_COMPONENTS = {
    "diagram-block",
    "diagram-series",
    "diagram-compare",
    "worked-example-card",
    "timeline-block",
}


def _find_visual_component_id(section_plan) -> str | None:
    """Return the first visual-capable component slug in this section."""
    for comp in section_plan.components:
        if comp.slug in VISUAL_CAPABLE_COMPONENTS:
            return comp.slug
    return None


def assemble_blueprint(
    plan: StructuralPlan,
    briefs: list[SectionBrief],
    *,
    subject: str = "General",
    title: str = "Generated Lesson",
    resource_type: str = "lesson",
) -> ProductionBlueprint:
    failed = [brief for brief in briefs if getattr(brief, "_failed", False)]
    brief_by_section_id = {brief.section_id: brief for brief in briefs}
    failed_section_ids = {brief.section_id for brief in failed}
    print(
        f"\n[ASSEMBLER] briefs={len(briefs)}"
        f" failed={[brief.section_id for brief in failed]}",
        flush=True,
    )

    sections: list[BlueprintSection] = []
    included_section_ids: set[str] = set()
    for section_plan in plan.sections:
        brief = brief_by_section_id.get(section_plan.id)
        if brief is None or section_plan.id in failed_section_ids:
            continue

        component_briefs = {
            component_brief.component_id: component_brief
            for component_brief in brief.components
        }
        components: list[ComponentPlan] = []
        for comp_plan in section_plan.components:
            comp_brief = component_briefs.get(comp_plan.slug)
            if comp_brief is None:
                continue
            components.append(ComponentPlan(
                component=comp_plan.slug,
                content_intent=comp_brief.content_intent,
            ))

        sections.append(BlueprintSection(
            section_id=section_plan.id,
            title=section_plan.title,
            role=section_plan.role,
            visual_required=section_plan.visual_required,
            components=components,
        ))
        included_section_ids.add(section_plan.id)

    if not sections:
        blocked_sections = [
            section.id
            for section in plan.sections
            if section.id not in included_section_ids
        ]
        print(
            f"\n[ASSEMBLER BLOCKED] failed_sections={blocked_sections}",
            flush=True,
        )
        raise BlueprintAssemblyBlocked(failed_sections=blocked_sections)

    question_plan = _assemble_question_plan(
        plan,
        briefs,
        included_section_ids,
    )
    visual_strategy = _assemble_visual_strategy(
        plan,
        briefs,
        included_section_ids,
    )
    print(
        f"\n[ASSEMBLER OK] sections={len(sections)}"
        f" questions={len(question_plan)}"
        f" visuals={len(visual_strategy.visuals)}",
        flush=True,
    )
    return ProductionBlueprint(
        metadata=_build_metadata(title=title, subject=subject),
        lesson=LessonModePlan(
            lesson_mode=plan.lesson_mode,
            resource_type=resource_type if resource_type else "lesson",
        ),
        voice=VoicePlan.model_validate(
            {"register": plan.voice.register_name, "tone": plan.voice.tone}
        ),
        anchor=AnchorPlan(reuse_scope=plan.anchor.reuse_scope),
        prior_knowledge=list(plan.prior_knowledge),
        repair_focus=(
            RepairFocus(
                fault_line=plan.repair_focus.fault_line,
                what_not_to_teach=list(plan.repair_focus.what_not_to_teach),
            )
            if plan.repair_focus is not None
            else None
        ),
        sections=sections,
        question_plan=question_plan,
        visual_strategy=visual_strategy,
        answer_key=AnswerKeyPlan(style=plan.answer_key_style),
    )


def _build_metadata(*, title: str, subject: str) -> BlueprintMetadata:
    return BlueprintMetadata(
        version="3.0",
        title=title,
        subject=subject,
    )


def _assemble_question_plan(
    plan: StructuralPlan,
    briefs: list[SectionBrief],
    included_section_ids: set[str],
) -> list[QuestionPlanItem]:
    brief_by_section_id = {brief.section_id: brief for brief in briefs}

    assembled: list[QuestionPlanItem] = []
    for question in plan.question_plan:
        if question.section_id not in included_section_ids:
            continue
        section_brief = brief_by_section_id.get(question.section_id)
        if section_brief is None:
            continue
        question_briefs = {
            question_brief.question_id: question_brief
            for question_brief in section_brief.question_briefs
        }
        question_brief = question_briefs.get(question.question_id)
        if question_brief is None:
            continue
        assembled.append(QuestionPlanItem(
            question_id=question.question_id,
            section_id=question.section_id,
            temperature=question.temperature,
            diagram_required=question.diagram_required,
            prompt=question_brief.prompt_text,
            expected_answer=question_brief.expected_answer,
        ))
    return assembled


def _assemble_visual_strategy(
    plan: StructuralPlan,
    briefs: list[SectionBrief],
    included_section_ids: set[str],
) -> VisualStrategyPlan:
    visuals: list[VisualInstruction] = []
    brief_by_section_id = {brief.section_id: brief for brief in briefs}
    for section_plan in plan.sections:
        if (
            section_plan.id not in included_section_ids
            or not section_plan.visual_required
        ):
            continue
        brief = brief_by_section_id.get(section_plan.id)
        if brief is None or brief.visual_strategy is None:
            continue

        vs = brief.visual_strategy
        component_id = _find_visual_component_id(section_plan)
        must_show = ", ".join(vs.must_show)
        must_not_show = ", ".join(vs.must_not_show)
        strategy = (
            f"{vs.subject} "
            f"(job: {vs.visual_job}; "
            f"anchor: {vs.anchor_link}; "
            f"style: {vs.visual_style or 'illustration'}; "
            f"must_show: {must_show or 'none'}; "
            f"must_not_show: {must_not_show or 'none'})"
        )
        frame_instructions = [
            VisualFrameInstruction(
                description=frame.description,
                must_show=frame.must_show,
            )
            for frame in vs.frames
        ]
        visuals.append(VisualInstruction(
            section_id=section_plan.id,
            component_id=component_id or "diagram-block",
            subject=vs.subject,
            visual_job=vs.visual_job,
            type_hint=vs.type_hint,
            anchor_link=vs.anchor_link,
            visual_style=vs.visual_style,
            must_show=vs.must_show,
            must_not_show=vs.must_not_show,
            source_question_ids=vs.source_question_ids,
            frames=frame_instructions,
            strategy=strategy,
            density=vs.type_hint,
        ))
    return VisualStrategyPlan(visuals=visuals)


__all__ = [
    "assemble_blueprint",
]
