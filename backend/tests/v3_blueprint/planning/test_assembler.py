from __future__ import annotations

import pytest

from v3_blueprint.planning.assembler import assemble_blueprint
from v3_blueprint.planning.models import (
    AnchorSpec,
    BlueprintAssemblyBlocked,
    ComponentBrief,
    ComponentSlot,
    LessonIntent,
    QPlanItem,
    QuestionBrief,
    SectionBrief,
    SectionPlan,
    StructuralPlan,
    VisualStrategySpec,
    VoiceSpec,
)


def _sample_plan() -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="Students identify equivalent fractions.",
            structure_rationale="Move from anchor to guided practice.",
        ),
        anchor=AnchorSpec(
            example="folding a paper strip into equal parts",
            reuse_scope="reused across model and practice",
        ),
        voice=VoiceSpec(register_name="simple", tone="encouraging"),
        prior_knowledge=["equal parts"],
        sections=[
            SectionPlan(
                id="orient",
                title="Orient",
                role="orient",
                visual_required=False,
                transition_note=None,
                components=[ComponentSlot(slug="hook-hero", purpose="Open the lesson")],
            ),
            SectionPlan(
                id="model",
                title="Model",
                role="model",
                visual_required=True,
                transition_note="Show the method after the hook.",
                components=[
                    ComponentSlot(
                        slug="worked-example-card",
                        purpose="Model the method",
                    )
                ],
            ),
        ],
        question_plan=[
            QPlanItem(
                question_id="q-orient",
                section_id="orient",
                temperature="warm",
                diagram_required=False,
            ),
            QPlanItem(
                question_id="q-model",
                section_id="model",
                temperature="cold",
                diagram_required=True,
            ),
        ],
        answer_key_style="brief_explanations",
    )


def test_assemble_blueprint_keeps_renderable_sections_in_plan_order() -> None:
    plan = _sample_plan()
    orient_brief = SectionBrief(
        section_id="orient",
        components=[
            ComponentBrief(
                component_id="hook-hero",
                content_intent="Introduce the anchor example.",
            )
        ],
        question_briefs=[
            QuestionBrief(
                question_id="q-orient",
                prompt_text="What stays the same when the strip is folded differently?",
                expected_answer="The whole stays the same size.",
            )
        ],
        visual_strategy=VisualStrategySpec(
            subject="A paper strip split into equal parts",
            type_hint="diagram",
            anchor_link="Use the same strip from the hook.",
            must_show=["equal partitions"],
            must_not_show=["unequal parts"],
        ),
    )
    failed_brief = SectionBrief(
        section_id="model",
        components=[],
        question_briefs=[],
        visual_strategy=None,
    )
    failed_brief._failed = True
    failed_brief._errors = ["writer timeout"]

    blueprint = assemble_blueprint(
        plan,
        [orient_brief, failed_brief],
        subject="Math",
        title="Equivalent Fractions",
        resource_type="lesson",
    )

    assert [section.section_id for section in blueprint.sections] == ["orient"]
    assert [question.question_id for question in blueprint.question_plan] == ["q-orient"]
    assert [visual.section_id for visual in blueprint.visual_strategy.visuals] == ["orient"]


def test_assemble_blueprint_blocks_when_no_sections_are_renderable() -> None:
    plan = _sample_plan()
    orient_failed = SectionBrief(
        section_id="orient",
        components=[],
        question_briefs=[],
        visual_strategy=None,
    )
    model_failed = SectionBrief(
        section_id="model",
        components=[],
        question_briefs=[],
        visual_strategy=None,
    )
    orient_failed._failed = True
    model_failed._failed = True

    with pytest.raises(BlueprintAssemblyBlocked) as exc:
        assemble_blueprint(plan, [orient_failed, model_failed])

    assert exc.value.failed_sections == ["orient", "model"]
