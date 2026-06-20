from __future__ import annotations

from contracts.lectio import get_component_card, get_planner_index
from v3_blueprint.planning.models import (
    AnchorSpec,
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


def test_validate_section_brief_catches_added_component() -> None:
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
    assert any("unexpected components not in plan" in error for error in errors)


def test_validate_section_brief_catches_visual_strategy_on_non_visual_section() -> None:
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
        question_briefs=[
            QuestionBrief(
                question_id="q1",
                prompt_text="What is 1/2?",
                expected_answer="Half",
            )
        ],
        visual_strategy=VisualStrategySpec(
            subject="fraction circles",
            type_hint="diagram",
            anchor_link="pizza slices",
            must_show=["equal parts"],
            must_not_show=["decorative clutter"],
        ),
    )
    errors = validate_section_brief(brief, section, [])
    assert any("visual_strategy returned but visual_required is false" in error for error in errors)
