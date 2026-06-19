from __future__ import annotations

from v3_blueprint.compiler import BlueprintCompiler
from v3_execution.component_aliases import canonical_component_id

from generation.v3_studio.dtos import (
    BlueprintPreviewDTO,
    V3AnchorExampleDTO,
    V3ComponentPlanDTO,
    V3InputForm,
    V3LearnerContextDTO,
    V3QuestionPlanDTO,
    V3SectionPlanItemDTO,
)
from v3_blueprint.models import ProductionBlueprint


def _teacher_label_from_slug(slug: str) -> str:
    return slug.replace("_", " ").strip().title() or slug


def blueprint_to_preview_dto(
    *,
    blueprint_id: str,
    blueprint: ProductionBlueprint,
    template_id: str = "guided-concept-path",
    form: V3InputForm | None = None,
) -> BlueprintPreviewDTO:
    BlueprintCompiler().compile_all(blueprint)

    register_summary_parts = [
        blueprint.voice.register_name.replace("_", " ").title(),
    ]
    if blueprint.voice.tone:
        register_summary_parts.append(blueprint.voice.tone.replace("_", " ").title())
    register_summary = " · ".join(register_summary_parts)

    support_summary: list[str] = []
    if form is not None:
        if form.language_support != "none":
            support_summary.append(f"Language support: {form.language_support.replace('_', ' ')}")
        if form.reading_level != "on_grade":
            support_summary.append(f"Reading level: {form.reading_level.replace('_', ' ')}")
        if form.learner_level != "on_grade":
            support_summary.append(f"Learner level: {form.learner_level.replace('_', ' ')}")
        if form.prior_knowledge_level != "some_background":
            support_summary.append(
                f"Prior knowledge: {form.prior_knowledge_level.replace('_', ' ')}"
            )
        for need in form.support_needs[:4]:
            support_summary.append(f"Support need: {need}")
        for pref in form.learning_preferences[:4]:
            support_summary.append(f"Preference: {pref.replace('_', ' ')}")

    section_plan: list[V3SectionPlanItemDTO] = []
    for order, sec in enumerate(blueprint.sections):
        learning_intent = "; ".join(c.content_intent for c in sec.components) or sec.title
        comps: list[V3ComponentPlanDTO] = []
        for c in sec.components:
            cid = canonical_component_id(c.component)
            comps.append(
                V3ComponentPlanDTO(
                    component_id=cid,
                    teacher_label=_teacher_label_from_slug(c.component),
                    content_intent=c.content_intent,
                )
            )
        section_plan.append(
            V3SectionPlanItemDTO(
                id=sec.section_id,
                title=sec.title,
                order=order,
                learning_intent=learning_intent,
                components=comps,
                visual_required=sec.visual_required,
            )
        )

    question_plan: list[V3QuestionPlanDTO] = []
    for q in blueprint.question_plan:
        question_plan.append(
            V3QuestionPlanDTO(
                id=q.question_id,
                difficulty=q.temperature,
                expected_answer=q.expected_answer,
                diagram_required=q.diagram_required,
                attaches_to_section_id=q.section_id,
                prompt=q.prompt,
            )
        )

    anchor: V3AnchorExampleDTO | None = None
    if blueprint.prior_knowledge:
        facts = {f"fact_{i}": pk for i, pk in enumerate(blueprint.prior_knowledge)}
        anchor = V3AnchorExampleDTO(
            label="Lesson anchors",
            facts=facts,
            correct_result=blueprint.question_plan[0].expected_answer
            if blueprint.question_plan
            else None,
            reuse_scope=blueprint.anchor.reuse_scope,
        )

    learner_context: V3LearnerContextDTO | None = None
    if form is not None:
        learner_context = V3LearnerContextDTO(
            grade_level=form.grade_level,
            subject=form.subject,
            duration_minutes=form.duration_minutes,
            lesson_mode=form.lesson_mode,
            learner_level=form.learner_level,
            reading_level=form.reading_level,
            language_support=form.language_support,
            prior_knowledge_level=form.prior_knowledge_level,
            support_needs=list(form.support_needs),
            prior_knowledge=form.prior_knowledge,
        )

    return BlueprintPreviewDTO(
        blueprint_id=blueprint_id,
        resource_type=blueprint.lesson.resource_type,
        title=blueprint.metadata.title,
        template_id=template_id,
        anchor=anchor,
        section_plan=section_plan,
        question_plan=question_plan,
        register_summary=register_summary,
        support_summary=support_summary[:8],
        learner_context=learner_context,
    )


__all__ = ["blueprint_to_preview_dto"]
