"""Phase 02: Stage 1 intent plans use lesson grammar without component choice."""

from __future__ import annotations

from resource_specs.loader import get_primary_spec
from v3_blueprint.planning.models import (
    AnchorSpec,
    IntentPlan,
    IntentSectionPlan,
    LessonIntent,
    Misconception,
    ConceptCard,
    QPlanItem,
    intent_plan_to_structural_plan,
)
from v3_blueprint.planning.structural_planner import (
    _intent_resource_spec_payload,
    build_stage1_system_prompt,
    build_stage1_user_message,
)
from v3_blueprint.planning.validators import validate_structural_plan
from learn.generation.contracts import GenerationInputForm as V3InputForm
from learn.generation.contracts import GenerationSignalSummary as V3SignalSummary


LESSON_ROLES = ("orient", "build", "model", "practice", "close")


def _lesson_resource_spec() -> dict:
    spec = get_primary_spec()
    return {
        "resource_type": "lesson",
        "depth": "standard",
        "spec": spec.model_dump(mode="json"),
        "rendered": "lesson roles only",
    }


def _intent_plan_for_subject(
    *,
    subject: str,
    topic: str,
    goal: str,
    anchor: str,
    misconception: str,
) -> IntentPlan:
    card_id = f"{subject}.{topic}.core"
    sections = [
        IntentSectionPlan(
            id="orient",
            title=f"Open {topic}",
            role="orient",
            purpose=f"Create felt need around {anchor} before teaching {topic}.",
            must_establish=[f"students recognize the {topic} problem"],
            misconception_focus=[],
            card_id=None,
            visual_required=False,
            transition_note=None,
        ),
        IntentSectionPlan(
            id="build",
            title=f"Define {topic}",
            role="build",
            purpose=f"Make the key {topic} idea precise using {anchor}.",
            must_establish=[f"core {topic} definition"],
            misconception_focus=["M1"],
            card_id=card_id,
            visual_required=subject in {"science", "math"},
            transition_note=f"Move from the opening conflict into the {topic} definition.",
        ),
        IntentSectionPlan(
            id="model",
            title=f"Model {topic}",
            role="model",
            purpose=f"Walk through the method on {anchor} before independent work.",
            must_establish=["worked method on the shared anchor"],
            misconception_focus=["M1"],
            card_id=card_id,
            visual_required=False,
            transition_note="Apply the definition to a guided walkthrough.",
        ),
        IntentSectionPlan(
            id="practice",
            title=f"Practice {topic}",
            role="practice",
            purpose=f"Let students apply {topic} with warm-to-cold items tied to {anchor}.",
            must_establish=["independent application attempt"],
            misconception_focus=[],
            card_id=card_id,
            visual_required=False,
            transition_note="Release responsibility after the model.",
        ),
        IntentSectionPlan(
            id="close",
            title=f"Check {topic}",
            role="close",
            purpose=f"Consolidate {topic} and check retention without reteaching.",
            must_establish=["retention check complete"],
            misconception_focus=[],
            card_id=None,
            visual_required=False,
            transition_note="Close the arc after practice.",
        ),
    ]
    return IntentPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal=goal,
            structure_rationale=f"General lesson arc fits first exposure to {topic}.",
        ),
        anchor=AnchorSpec(
            example=anchor,
            reuse_scope="orient through close",
        ),
        prior_knowledge=["grade-appropriate prior knowledge"],
        repair_focus=None,
        cards=[
            ConceptCard(
                id=card_id,
                title=topic.title(),
                objective=goal.replace("By the end of this lesson the student can ", ""),
                misconceptions=[
                    Misconception(id="M1", description=misconception, source="drafted")
                ],
                no_known_misconceptions=False,
                opens_by=f"returning to {anchor}",
            )
        ],
        sections=sections,
        question_plan=[
            QPlanItem(
                question_id="q1",
                section_id="practice",
                temperature="warm",
                diagram_required=False,
            )
        ],
        answer_key_style="brief_explanations",
    )


SUBJECT_FIXTURES = [
    {
        "subject": "math",
        "topic": "ratios",
        "goal": "By the end of this lesson the student can compare two ratios using a shared whole.",
        "anchor": "mixing 2 cups juice with 3 cups water",
        "misconception": "ratios can be compared by looking at only one part",
    },
    {
        "subject": "science",
        "topic": "plants-light",
        "goal": "By the end of this lesson the student can explain why plants need light to make food.",
        "anchor": "two identical seedlings, one in light and one in a cupboard",
        "misconception": "plants get their food from soil nutrients alone",
    },
    {
        "subject": "history",
        "topic": "trade-routes",
        "goal": "By the end of this lesson the student can explain how a trade route changed local power.",
        "anchor": "caravans crossing a desert oasis town",
        "misconception": "trade only moved goods, never ideas or power",
    },
    {
        "subject": "english",
        "topic": "theme",
        "goal": "By the end of this lesson the student can state a theme supported by two text details.",
        "anchor": "a short story about a lost library book",
        "misconception": "theme is the same as the plot summary",
    },
]


def test_same_general_lesson_spec_across_four_subjects() -> None:
    resource_spec = _lesson_resource_spec()
    for fixture in SUBJECT_FIXTURES:
        intent = _intent_plan_for_subject(**fixture)
        plan = intent_plan_to_structural_plan(intent)
        assert [section.role for section in plan.sections] == list(LESSON_ROLES)
        assert all(not section.components for section in plan.sections)
        assert all(section.purpose.strip() for section in plan.sections)
        errors = validate_structural_plan(plan, resource_spec)
        assert errors == [], (fixture["subject"], errors)


def test_intent_adapter_leaves_components_empty() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)
    assert plan.sections[1].purpose.startswith("Make the key")
    assert plan.sections[1].must_establish
    assert plan.sections[1].misconception_focus == ["M1"]
    assert plan.sections[1].components == []


def test_stage1_user_message_strips_component_catalogue() -> None:
    resource_spec = _lesson_resource_spec()
    stripped = _intent_resource_spec_payload(resource_spec)
    assert "preferred_components" not in str(stripped)
    assert "allowed_components" not in str(stripped)

    form = V3InputForm(
        grade_level="Grade 6",
        subject="Mathematics",
        duration_minutes=40,
        resource_type="lesson",
        topic="Ratios",
        subtopics=[],
        prior_knowledge="",
        outcome="Students can compare ratios.",
        struggle="",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="none",
        prior_knowledge_level="new_topic",
        free_text="",
    )
    signals = V3SignalSummary(
        topic="Ratios",
        teacher_goal="Students can compare ratios.",
        inferred_lesson_mode="first_exposure",
        lesson_mode_confidence="high",
    )
    message = build_stage1_user_message(
        signals=signals,
        form=form,
        resource_spec=resource_spec,
    )
    assert "ACTIVE RESOURCE SPEC ROLES" in message
    assert "orient" in message and "close" in message
    assert "preferred_components" not in message
    assert "hook-hero" not in message


def test_stage1_prompt_forbids_component_choice() -> None:
    prompt = build_stage1_system_prompt()
    assert "Never name Lectio component slugs" in prompt
    assert "components" in prompt.lower()  # hard rule saying not to emit them
    assert "AVAILABLE COMPONENTS" not in prompt


def test_intent_purpose_rejecting_component_names() -> None:
    resource_spec = _lesson_resource_spec()
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)
    plan.sections[0].purpose = "Use hook-hero to open the lesson"
    errors = validate_structural_plan(plan, resource_spec)
    assert any("must not name Lectio components" in error for error in errors)
