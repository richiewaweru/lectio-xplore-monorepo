from __future__ import annotations

from v3_blueprint.models import (
    AnchorPlan,
    AnswerKeyPlan,
    AppliedLens,
    BlueprintMetadata,
    ComponentPlan,
    LessonModePlan,
    ProductionBlueprint,
    QuestionPlanItem,
    RepairFocus,
    SectionPlan as BlueprintSection,
    VisualInstruction,
    VisualStrategyPlan,
    VoicePlan,
)
from v3_blueprint.planning.models import (
    BlueprintAssemblyBlocked,
    QuestionBrief,
    SectionBrief,
    StructuralPlan,
)


def assemble_blueprint(
    plan: StructuralPlan,
    briefs: list[SectionBrief],
    *,
    subject: str = "General",
    title: str = "Generated Lesson",
    resource_type: str = "lesson",
) -> ProductionBlueprint:
    # GATE — block if any section failed
    failed = [b for b in briefs if getattr(b, "_failed", False)]
    print(
        f"\n[ASSEMBLER] briefs={len(briefs)}"
        f" failed={[b.section_id for b in failed]}",
        flush=True,
    )
    if failed:
        print(
            f"\n[ASSEMBLER BLOCKED] failed_sections="
            f"{[b.section_id for b in failed]}",
            flush=True,
        )
        raise BlueprintAssemblyBlocked(
            failed_sections=[b.section_id for b in failed]
        )

    # Assemble sections
    sections: list[BlueprintSection] = []
    for section_plan, brief in zip(plan.sections, briefs):
        components: list[ComponentPlan] = []
        for comp_plan, comp_brief in zip(
            section_plan.components, brief.components
        ):
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

    question_plan = _assemble_question_plan(plan, briefs)
    visual_strategy = _assemble_visual_strategy(plan, briefs)
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
        applied_lenses=[
            AppliedLens(
                lens_id=lens.lens_id,
                effects=lens.effects,
            )
            for lens in plan.applied_lenses
        ],
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
) -> list[QuestionPlanItem]:
    # Index Stage 2 question briefs by question_id
    q_briefs: dict[str, QuestionBrief] = {
        qb.question_id: qb
        for brief in briefs
        for qb in brief.question_briefs
    }

    assembled: list[QuestionPlanItem] = []
    for q in plan.question_plan:
        if q.question_id not in q_briefs:
            raise ValueError(
                f"question_id '{q.question_id}' from Stage 1 plan has no "
                f"matching brief from Stage 2. Assembly cannot proceed."
            )
        qb = q_briefs[q.question_id]
        assembled.append(QuestionPlanItem(
            question_id=q.question_id,
            section_id=q.section_id,
            temperature=q.temperature,
            diagram_required=q.diagram_required,
            prompt=qb.prompt_text,
            expected_answer=qb.expected_answer,
        ))
    return assembled


def _assemble_visual_strategy(
    plan: StructuralPlan,
    briefs: list[SectionBrief],
) -> VisualStrategyPlan:
    visuals: list[VisualInstruction] = []
    for section_plan, brief in zip(plan.sections, briefs):
        if brief.visual_strategy is not None:
            must_show = ", ".join(brief.visual_strategy.must_show)
            must_not_show = ", ".join(brief.visual_strategy.must_not_show)
            strategy = (
                f"{brief.visual_strategy.subject} "
                f"(anchor: {brief.visual_strategy.anchor_link}; "
                f"must_show: {must_show or 'none'}; "
                f"must_not_show: {must_not_show or 'none'})"
            )
            visuals.append(VisualInstruction(
                section_id=section_plan.id,
                strategy=strategy,
                density=brief.visual_strategy.type_hint,
            ))
    return VisualStrategyPlan(visuals=visuals)


__all__ = [
    "assemble_blueprint",
]
