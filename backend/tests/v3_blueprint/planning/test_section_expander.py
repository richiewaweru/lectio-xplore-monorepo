from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning import section_expander
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentBrief,
    ComponentSlot,
    LensEffect,
    LessonIntent,
    QPlanItem,
    SectionBrief,
    SectionPlan,
    StructuralPlan,
    VoiceSpec,
)


def _signals() -> V3SignalSummary:
    return V3SignalSummary(
        topic="Fractions",
        subtopic="Equivalent fractions",
        prior_knowledge=["equal sharing"],
        learner_needs=[],
        teacher_goal="Build confidence",
        inferred_resource_type="lesson",
        confidence="medium",
        missing_signals=[],
    )


def _form() -> V3InputForm:
    return V3InputForm(
        grade_level="Grade 6",
        subject="Math",
        duration_minutes=45,
        topic="Equivalent fractions",
        subtopics=["pizza slices"],
        prior_knowledge="equal sharing",
        lesson_mode="first_exposure",
        lesson_mode_other="",
        intended_outcome="understand",
        intended_outcome_other="",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="none",
        prior_knowledge_level="some_background",
        support_needs=[],
        learning_preferences=[],
        free_text="",
    )


def _plan() -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="By the end students can identify equivalent fractions.",
            structure_rationale="Concrete-first structure for novice learners.",
        ),
        anchor=AnchorSpec(
            example="splitting a pizza into 8 equal slices",
            reuse_scope="orient then model then practice",
        ),
        applied_lenses=[LensEffect(lens_id="concrete_first", effects=["anchor first"])],
        voice=VoiceSpec(register_name="simple", tone="encouraging"),
        prior_knowledge=["equal sharing"],
        sections=[
            SectionPlan(
                id="orient",
                title="Orient",
                role="orient",
                visual_required=False,
                transition_note=None,
                components=[ComponentSlot(slug="hook-hero", purpose="surface anchor")],
            )
        ],
        question_plan=[
            QPlanItem(
                question_id="q1",
                section_id="orient",
                temperature="warm",
                diagram_required=False,
            )
        ],
        answer_key_style="brief_explanations",
    )


def _brief() -> SectionBrief:
    return SectionBrief(
        section_id="orient",
        components=[ComponentBrief(component_id="hook-hero", content_intent="Use the pizza anchor.")],
        question_briefs=[],
        visual_strategy=None,
    )


def test_prefix_user_content_uses_default_cache_point_without_ttl() -> None:
    signals = _signals()
    form = _form()
    plan = _plan()
    cache_point = object()

    with patch.object(section_expander, "CachePoint", return_value=cache_point) as mock_cache_point:
        content = section_expander._prefix_user_content(
            signals=signals,
            form=form,
            resource_spec={"resource_type": "lesson"},
            plan=plan,
        )

    mock_cache_point.assert_called_once_with()
    assert content[-1] is cache_point


@pytest.mark.asyncio
async def test_call_stage2_section_omits_extended_cache_beta_header() -> None:
    signals = _signals()
    form = _form()
    plan = _plan()
    section = plan.sections[0]
    brief = _brief()

    with (
        patch.object(section_expander, "Agent", return_value=MagicMock(name="agent")) as _agent,
        patch.object(section_expander, "get_v3_model", return_value="model-name"),
        patch.object(section_expander, "get_v3_spec", return_value={"spec": "value"}),
        patch.object(section_expander, "get_v3_slot", return_value="slot-name"),
        patch.object(section_expander, "run_llm", new=AsyncMock(return_value=SimpleNamespace(output=brief))) as mock_run_llm,
    ):
        result = await section_expander._call_stage2_section(
            plan=plan,
            section=section,
            prior_briefs=[],
            component_cards={"hook-hero": {"capacity": 1}},
            signals=signals,
            form=form,
            resource_spec={"resource_type": "lesson"},
            generation_id="gen-123",
            trace_id="trace-123",
        )

    assert result == brief
    call_kwargs = mock_run_llm.await_args.kwargs
    assert call_kwargs["model_settings"] == {
        "anthropic_thinking": section_expander.STAGE2_THINKING,
        "max_tokens": section_expander.STAGE2_MAX_TOKENS,
    }
