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
        visual_strategy=VisualStrategySpec(
            subject="A paper strip split into equal parts",
            visual_job="introduce the anchor visually",
            type_hint="diagram",
            anchor_link="Use the same strip from the hook.",
            visual_style="diagram_precision",
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
    assert blueprint.question_plan == []
    assert blueprint.visual_strategy.visuals == []


def test_assemble_blueprint_ignores_extra_briefs_and_leaves_items_to_pack() -> None:
    plan = _sample_plan()
    orient_brief = SectionBrief(
        section_id="orient",
        components=[
            ComponentBrief(component_id="hook-hero", content_intent="Planned orient brief."),
            ComponentBrief(component_id="invented-component", content_intent="Ignore this."),
        ],
    )
    model_brief = SectionBrief(
        section_id="model",
        components=[
            ComponentBrief(
                component_id="worked-example-card",
                content_intent="Planned model brief.",
            )
        ],
        visual_strategy=VisualStrategySpec(
            subject="A paper strip comparison",
            visual_job="model equivalent partitions",
            type_hint="diagram",
            anchor_link="same paper strip",
        ),
    )

    blueprint = assemble_blueprint(plan, [orient_brief, model_brief])

    assert [component.component for component in blueprint.sections[0].components] == ["hook-hero"]
    assert blueprint.question_plan == []
    assert [visual.section_id for visual in blueprint.visual_strategy.visuals] == ["model"]


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


def test_assemble_blueprint_blocks_partial_failure_when_ship_with_holes_disabled() -> None:
    plan = _sample_plan()
    orient = SectionBrief(section_id="orient", components=[], question_briefs=[], visual_strategy=None)
    model_failed = SectionBrief(section_id="model", components=[], question_briefs=[], visual_strategy=None)
    model_failed._failed = True

    with pytest.raises(BlueprintAssemblyBlocked) as exc:
        assemble_blueprint(plan, [orient, model_failed], ship_with_holes=False)

    assert exc.value.failed_sections == ["model"]
