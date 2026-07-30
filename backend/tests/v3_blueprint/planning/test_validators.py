from __future__ import annotations

from contracts.lectio import get_component_card, get_planner_index
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentBrief,
    ComponentSlot,
    LessonIntent,
    QPlanItem,
    SectionBrief,
    SectionPlan,
    StructuralPlan,
    VisualFrameBrief,
    VisualStrategySpec,
    VoiceSpec,
)
from v3_blueprint.planning.validators import validate_section_brief, validate_structural_plan


def _available_component_slugs() -> list[str]:
    planner = get_planner_index()
    component_ids = planner.get("component_ids")
    if isinstance(component_ids, list) and component_ids:
        return [slug for slug in component_ids if isinstance(slug, str)]
    slugs: list[str] = []
    phase_map = planner.get("phase_map")
    if isinstance(phase_map, dict):
        for phase in phase_map.values():
            if isinstance(phase, dict):
                phase_components = phase.get("components")
                if isinstance(phase_components, list):
                    slugs.extend([slug for slug in phase_components if isinstance(slug, str)])
    return slugs


def _first_two_distinct_slugs() -> tuple[str, str]:
    slugs = _available_component_slugs()
    seen: list[str] = []
    for slug in slugs:
        if get_component_card(slug) is None:
            continue
        if slug not in seen:
            seen.append(slug)
        if len(seen) == 2:
            return seen[0], seen[1]
    raise AssertionError("Need at least two valid component slugs in registry")


def _base_plan_with_components(*, components: list[ComponentSlot]) -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="By the end of this lesson the student can compare simple fractions.",
            structure_rationale="Concrete-first sequence for novice learners.",
        ),
        anchor=AnchorSpec(
            example="splitting a pizza into 8 equal slices",
            reuse_scope="used in intro and explain",
        ),
        voice=VoiceSpec(register_name="simple", tone="encouraging"),
        prior_knowledge=["equal sharing"],
        sections=[
            SectionPlan(
                id="intro",
                title="Intro",
                role="intro",
                visual_required=False,
                transition_note=None,
                components=components,
            )
        ],
        question_plan=[
            QPlanItem(
                question_id="q1",
                section_id="intro",
                temperature="warm",
                diagram_required=False,
            )
        ],
        answer_key_style="brief_explanations",
    )


def test_validate_structural_plan_catches_unknown_slug() -> None:
    plan = _base_plan_with_components(
        components=[ComponentSlot(slug="definitely-not-a-real-slug", purpose="test")]
    )
    errors = validate_structural_plan(plan)
    assert any("unknown slug" in error for error in errors)


def test_validate_structural_plan_catches_duplicate_section_field(monkeypatch) -> None:
    slug_a, slug_b = _first_two_distinct_slugs()

    def _fake_get_component_card(slug: str):
        if slug in {slug_a, slug_b}:
            return {"section_field": "same_field"}
        return get_component_card(slug)

    monkeypatch.setattr("v3_blueprint.planning.validators.get_component_card", _fake_get_component_card)

    plan = _base_plan_with_components(
        components=[
            ComponentSlot(slug=slug_a, purpose="first"),
            ComponentSlot(slug=slug_b, purpose="second"),
        ]
    )
    errors = validate_structural_plan(plan)
    assert any(
        "share section_field" in error and "same_field" in error
        for error in errors
    )


def test_validate_structural_plan_catches_role_outside_resource_spec() -> None:
    plan = _base_plan_with_components(
        components=[ComponentSlot(slug="hook-hero", purpose="surface anchor")]
    )
    plan.sections[0].role = "invalid_role"
    errors = validate_structural_plan(
        plan,
        {
            "spec": {
                "required_roles": ["intro", "practice"],
                "optional_roles": ["summary"],
            }
        },
    )
    assert any("which is not in the active resource spec roles" in error for error in errors)


def test_validate_structural_plan_catches_role_outside_real_spec_dump_shape() -> None:
    from resource_specs.loader import get_spec

    plan = _base_plan_with_components(
        components=[ComponentSlot(slug="hook-hero", purpose="surface anchor")]
    )
    plan.sections[0].role = "model"
    errors = validate_structural_plan(
        plan,
        {"spec": get_spec("worksheet").model_dump(mode="json")},
    )
    assert any("which is not in the active resource spec roles" in error for error in errors)


def test_validate_section_brief_catches_dropped_component() -> None:
    slug_a, slug_b = _first_two_distinct_slugs()
    section = SectionPlan(
        id="model",
        title="Model",
        role="model",
        visual_required=False,
        transition_note=None,
        components=[
            ComponentSlot(slug=slug_a, purpose="a"),
            ComponentSlot(slug=slug_b, purpose="b"),
        ],
    )
    brief = SectionBrief(
        section_id="model",
        components=[ComponentBrief(component_id=slug_a, content_intent="one brief only")],
        question_briefs=[],
        visual_strategy=None,
    )
    errors = validate_section_brief(brief, section, [])
    assert any("missing briefs for planned components" in error for error in errors)


def test_validate_section_brief_allows_additional_component() -> None:
    slug_a, _slug_b = _first_two_distinct_slugs()
    section = SectionPlan(
        id="practice",
        title="Practice",
        role="practice",
        visual_required=False,
        transition_note=None,
        components=[ComponentSlot(slug=slug_a, purpose="only planned")],
    )
    brief = SectionBrief(
        section_id="practice",
        components=[
            ComponentBrief(component_id=slug_a, content_intent="planned"),
            ComponentBrief(component_id="invented-extra", content_intent="not planned"),
        ],
        question_briefs=[],
        visual_strategy=None,
    )
    errors = validate_section_brief(brief, section, [])
    assert errors == []


def test_validate_section_brief_allows_optional_visual_on_non_visual_section() -> None:
    slug_a, _slug_b = _first_two_distinct_slugs()
    section = SectionPlan(
        id="summary",
        title="Summary",
        role="summary",
        visual_required=False,
        transition_note=None,
        components=[ComponentSlot(slug=slug_a, purpose="summary intent")],
    )
    brief = SectionBrief(
        section_id="summary",
        components=[ComponentBrief(component_id=slug_a, content_intent="brief")],
        visual_strategy=VisualStrategySpec(
            subject="fraction circles",
            visual_job="introduce the concept visually",
            type_hint="diagram",
            anchor_link="pizza slices",
            must_show=["equal parts"],
            must_not_show=["decorative clutter"],
        ),
    )
    errors = validate_section_brief(brief, section, [])
    assert errors == []


def test_stage2_models_preserve_long_content_and_ignore_unknown_fields() -> None:
    incident_content = "x" * 304
    long_content = "A complete, coherent writer instruction. " * 30
    payload = {
        "section_id": "practice",
        "section_note": "ignored",
        "components": [
            {
                "component_id": "practice-stack",
                "content_intent": incident_content,
                "difficulty_note": "ignored",
            },
            {
                "component_id": "reflection-prompt",
                "content_intent": long_content,
            },
        ],
        "question_briefs": [
            {
                "question_id": "q1",
                "prompt_text": "What changes?",
                "expected_answer": "The representation changes.",
                "answer_note": "ignored",
            }
        ],
        "visual_strategy": {
            "subject": "Fraction strips",
            "visual_job": "Compare equivalent representations.",
            "type_hint": "diagram",
            "anchor_link": "same strip",
            "visual_note": "ignored",
            "frames": [
                {
                    "description": "One strip divided in halves.",
                    "must_show": ["equal halves"],
                    "frame_note": "ignored",
                }
            ],
        },
    }

    brief = SectionBrief.model_validate(payload)

    assert brief.components[0].content_intent == incident_content
    assert brief.components[1].content_intent == long_content
    assert "section_note" not in brief.model_dump()
    assert "difficulty_note" not in brief.components[0].model_dump()
    assert "question_briefs" not in brief.model_dump()
    assert brief.visual_strategy is not None
    assert "visual_note" not in brief.visual_strategy.model_dump()
    assert "frame_note" not in brief.visual_strategy.frames[0].model_dump()

    section = SectionPlan(
        id="practice",
        title="Practice",
        role="practice",
        visual_required=False,
        transition_note=None,
        components=[
            ComponentSlot(slug="practice-stack", purpose="practice"),
            ComponentSlot(slug="reflection-prompt", purpose="reflect"),
        ],
    )
    question_plan = [
        QPlanItem(question_id="q1", section_id="practice", temperature="warm")
    ]
    assert validate_section_brief(brief, section, question_plan) == []


def test_validate_section_brief_ignores_legacy_question_fields() -> None:
    section = SectionPlan(
        id="practice",
        title="Practice",
        role="practice",
        visual_required=False,
        transition_note=None,
        components=[ComponentSlot(slug="hook-hero", purpose="practice")],
    )
    brief = SectionBrief(
        section_id="practice",
        components=[ComponentBrief(component_id="hook-hero", content_intent="practice")],
        question_briefs=[{"question_id": "legacy"}],
    )
    question_plan = [
        QPlanItem(question_id="q1", section_id="practice", temperature="warm")
    ]

    assert validate_section_brief(brief, section, question_plan) == []


def test_validate_section_brief_does_not_require_assigned_questions() -> None:
    section = SectionPlan(
        id="practice",
        title="Practice",
        role="practice",
        visual_required=False,
        transition_note=None,
        components=[ComponentSlot(slug="hook-hero", purpose="practice")],
    )
    brief = SectionBrief(
        section_id="practice",
        components=[ComponentBrief(component_id="hook-hero", content_intent="practice")],
    )
    question_plan = [
        QPlanItem(question_id="q1", section_id="practice", temperature="warm")
    ]

    assert validate_section_brief(brief, section, question_plan) == []


def test_validate_section_brief_catches_wrong_section_id() -> None:
    section = SectionPlan(
        id="practice",
        title="Practice",
        role="practice",
        visual_required=False,
        transition_note=None,
        components=[ComponentSlot(slug="hook-hero", purpose="practice")],
    )
    brief = SectionBrief(
        section_id="wrong-section",
        components=[ComponentBrief(component_id="hook-hero", content_intent="practice")],
    )

    errors = validate_section_brief(brief, section, [])

    assert any("does not match assigned section" in error for error in errors)


def test_structural_plan_allows_more_than_two_visual_sections() -> None:
    plan = StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="By the end of this lesson the student can compare simple fractions.",
            structure_rationale="Concrete-first sequence for novice learners.",
        ),
        anchor=AnchorSpec(
            example="splitting a pizza into 8 equal slices",
            reuse_scope="used across the lesson",
        ),
        voice=VoiceSpec(register_name="simple", tone="encouraging"),
        prior_knowledge=["equal sharing"],
        sections=[
            SectionPlan(
                id=f"s{idx}",
                title=f"Section {idx}",
                role="intro",
                visual_required=True,
                transition_note=None if idx == 0 else "build next idea",
                components=[ComponentSlot(slug="hook-hero", purpose="surface idea")],
            )
            for idx in range(4)
        ],
        question_plan=[
            QPlanItem(
                question_id="q1",
                section_id="s0",
                temperature="warm",
                diagram_required=False,
            )
        ],
        answer_key_style="brief_explanations",
    )

    assert len(plan.sections) == 4


def test_validate_section_brief_rejects_series_with_too_few_frames() -> None:
    section = SectionPlan(
        id="model",
        title="Model",
        role="model",
        visual_required=True,
        transition_note=None,
        components=[ComponentSlot(slug="diagram-series", purpose="show progression")],
    )
    brief = SectionBrief(
        section_id="model",
        components=[ComponentBrief(component_id="diagram-series", content_intent="show progression")],
        question_briefs=[],
        visual_strategy=VisualStrategySpec(
            subject="A sequence",
            visual_job="show a stepwise progression",
            type_hint="diagram",
            anchor_link="same anchor",
            must_show=["step markers"],
            must_not_show=[],
            frames=[VisualFrameBrief(description="Only one frame", must_show=["step 1"])],
        ),
    )

    errors = validate_section_brief(brief, section, [])
    assert any("requires >= 2 frames" in error for error in errors)


def test_validate_section_brief_allows_extra_frames_on_non_series_component() -> None:
    section = SectionPlan(
        id="model",
        title="Model",
        role="model",
        visual_required=True,
        transition_note=None,
        components=[ComponentSlot(slug="worked-example-card", purpose="show example")],
    )
    brief = SectionBrief(
        section_id="model",
        components=[ComponentBrief(component_id="worked-example-card", content_intent="show example")],
        question_briefs=[],
        visual_strategy=VisualStrategySpec(
            subject="A worked example",
            visual_job="summarize the example",
            type_hint="diagram",
            anchor_link="same anchor",
            must_show=["labels"],
            must_not_show=[],
            frames=[
                VisualFrameBrief(description="Frame 1", must_show=["label a"]),
                VisualFrameBrief(description="Frame 2", must_show=["label b"]),
            ],
        ),
    )

    errors = validate_section_brief(brief, section, [])
    assert errors == []


def test_validate_section_brief_allows_extra_diagram_series_frames() -> None:
    section = SectionPlan(
        id="model",
        title="Model",
        role="model",
        visual_required=True,
        transition_note=None,
        components=[ComponentSlot(slug="diagram-series", purpose="show progression")],
    )
    brief = SectionBrief(
        section_id="model",
        components=[ComponentBrief(component_id="diagram-series", content_intent="show progression")],
        visual_strategy=VisualStrategySpec(
            subject="A sequence",
            visual_job="show a stepwise progression",
            type_hint="diagram",
            anchor_link="same anchor",
            must_show=["step markers"] * 6,
            frames=[
                VisualFrameBrief(description=f"Frame {index}", must_show=["step"])
                for index in range(3)
            ],
        ),
    )

    assert validate_section_brief(brief, section, []) == []


def test_validate_section_brief_rejects_bad_source_question_ids_and_empty_visual_job() -> None:
    section = SectionPlan(
        id="practice",
        title="Practice",
        role="practice",
        visual_required=True,
        transition_note=None,
        components=[ComponentSlot(slug="diagram-block", purpose="support practice")],
    )
    brief = SectionBrief(
        section_id="practice",
        components=[ComponentBrief(component_id="diagram-block", content_intent="support practice")],
        question_briefs=[],
        visual_strategy=VisualStrategySpec(
            subject="Practice figure",
            visual_job=" ",
            type_hint="diagram",
            anchor_link="same anchor",
            must_show=["shape"],
            must_not_show=[],
            source_question_ids=["q-missing"],
        ),
    )
    question_plan = [
        QPlanItem(
            question_id="q-real",
            section_id="practice",
            temperature="warm",
            diagram_required=True,
        )
    ]

    errors = validate_section_brief(brief, section, question_plan)
    assert any("source_question_ids references questions not in this section" in error for error in errors)
    assert any("visual_strategy.visual_job is empty" in error for error in errors)
