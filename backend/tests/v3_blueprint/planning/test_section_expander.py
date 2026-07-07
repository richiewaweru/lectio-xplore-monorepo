from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.types import ModelFamily, ModelSpec
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning import section_expander
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentBrief,
    ComponentSlot,
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
        inferred_lesson_mode="first_exposure",
        lesson_mode_confidence="high",
    )


def _form() -> V3InputForm:
    return V3InputForm(
        grade_level="Grade 6",
        subject="Math",
        duration_minutes=45,
        resource_type="lesson",
        topic="Equivalent fractions",
        subtopics=["pizza slices"],
        prior_knowledge="equal sharing",
        outcome="Students can identify and generate equivalent fractions.",
        struggle="Some learners still mix up numerator and denominator.",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="none",
        prior_knowledge_level="some_background",
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
            reuse_scope="intro then explain then practice",
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
                components=[ComponentSlot(slug="hook-hero", purpose="surface anchor")],
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


def _brief() -> SectionBrief:
    return SectionBrief(
        section_id="intro",
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
            family=ModelFamily.ANTHROPIC,
        )

    mock_cache_point.assert_called_once_with()
    assert content[-1] is cache_point


def test_prefix_user_content_omits_cache_point_for_openai_compatible() -> None:
    signals = _signals()
    form = _form()
    plan = _plan()

    with patch.object(section_expander, "CachePoint") as mock_cache_point:
        content = section_expander._prefix_user_content(
            signals=signals,
            form=form,
            resource_spec={"resource_type": "lesson"},
            plan=plan,
            family=ModelFamily.OPENAI_COMPATIBLE,
        )

    mock_cache_point.assert_not_called()
    assert len(content) == 4


def test_stage2_uses_helper_backstop_without_node_level_cap() -> None:
    assert not hasattr(section_expander, "STAGE2_MAX_TOKENS")


@pytest.mark.asyncio
async def test_call_stage2_section_omits_extended_cache_beta_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-v4-pro")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    signals = _signals()
    form = _form()
    plan = _plan()
    section = plan.sections[0]
    brief = _brief()

    with (
        patch.object(section_expander, "Agent", return_value=MagicMock(name="agent")) as _agent,
        patch.object(section_expander, "get_v3_model", return_value="model-name"),
        patch.object(
            section_expander,
            "get_v3_spec",
            return_value=ModelSpec(
                family=ModelFamily.OPENAI_COMPATIBLE,
                model_name="deepseek-v4-pro",
                base_url="https://api.deepseek.com",
            ),
        ),
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
        "openai_reasoning_effort": "medium",
        "extra_body": {"thinking": {"type": "enabled"}},
        "max_tokens": 120000,
    }
    assert len(call_kwargs["user_prompt"]) == 5
