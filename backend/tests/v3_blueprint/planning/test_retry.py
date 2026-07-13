from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning import retry
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentBrief,
    ComponentSlot,
    LessonIntent,
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
        outcome="Students can identify equivalent fractions.",
        struggle="Some learners mix up numerator and denominator.",
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
            goal="Students identify equivalent fractions.",
            structure_rationale="Use a concrete-first sequence.",
        ),
        anchor=AnchorSpec(
            example="pizza slices",
            reuse_scope="reused in each section",
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
                components=[ComponentSlot(slug="hook-hero", purpose="introduce")],
            ),
            SectionPlan(
                id="practice",
                title="Practice",
                role="practice",
                visual_required=False,
                transition_note="Build from the hook.",
                components=[ComponentSlot(slug="practice-stack", purpose="practice")],
            ),
        ],
        question_plan=[],
        answer_key_style="brief_explanations",
    )


def _brief(section_id: str, component_id: str, content_intent: str) -> SectionBrief:
    return SectionBrief(
        section_id=section_id,
        components=[ComponentBrief(component_id=component_id, content_intent=content_intent)],
    )


def test_component_purpose_length_is_guidance_not_schema_failure() -> None:
    long_purpose = (
        "List procedure: isolate the variable, flip the inequality when multiplying "
        "or dividing by a negative value, then graph the solution."
    )

    component = ComponentSlot(slug="worked-example-card", purpose=long_purpose)

    assert len(long_purpose) > 80
    assert component.purpose == long_purpose
    purpose_schema = ComponentSlot.model_json_schema()["properties"]["purpose"]
    assert "maxLength" not in purpose_schema


@pytest.mark.asyncio
async def test_run_stage1_retries_current_output_validation_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    call_stage1 = AsyncMock(
        side_effect=[
            UnexpectedModelBehavior("Exceeded maximum retries (1) for output validation"),
            plan,
        ]
    )
    persist_plan = AsyncMock()
    monkeypatch.setattr(retry, "_call_stage1", call_stage1)
    monkeypatch.setattr(retry, "persist_structural_plan", persist_plan)

    result = await retry.run_stage1_with_retry(
        _signals(),
        _form(),
        {},
        generation_id="generation-1",
    )

    assert result is plan
    assert call_stage1.await_count == 2
    assert call_stage1.await_args_list[0].kwargs["previous_errors"] is None
    assert call_stage1.await_args_list[1].kwargs["previous_errors"] == [
        "Stage 1 structured output could not be validated: "
        "Exceeded maximum retries (1) for output validation"
    ]
    persist_plan.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_stage2_retries_only_failed_section_and_preserves_long_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    long_content = "Preserve this complete downstream instruction. " * 30
    responses = [
        _brief("intro", "hook-hero", "Introduce the pizza anchor."),
        SectionBrief(section_id="practice", components=[]),
        _brief("practice", "practice-stack", long_content),
    ]
    prior_brief_snapshots: list[list[str]] = []

    async def call_stage2(**kwargs):
        prior_brief_snapshots.append(
            [brief.section_id for brief in kwargs["prior_briefs"]]
        )
        return responses.pop(0)

    mock_call_stage2 = AsyncMock(side_effect=call_stage2)
    monkeypatch.setattr(retry, "_call_stage2_section", mock_call_stage2)
    monkeypatch.setattr(retry, "_load_component_cards_for_section", lambda section: {})

    briefs = await retry.run_stage2(
        plan,
        _signals(),
        _form(),
        {},
    )

    assert mock_call_stage2.await_count == 3
    assert briefs[0].components[0].content_intent == "Introduce the pizza anchor."
    assert briefs[1].components[0].content_intent == long_content
    assert len(briefs[1].components[0].content_intent) > 1_000
    assert prior_brief_snapshots == [[], ["intro"], ["intro"]]


@pytest.mark.asyncio
async def test_structured_output_validation_exhaustion_returns_failed_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    section = plan.sections[0]
    call_stage2 = AsyncMock(
        side_effect=[
            UnexpectedModelBehavior("Exceeded maximum retries (1) for output validation"),
            UnexpectedModelBehavior("Exceeded maximum retries (1) for output validation"),
        ]
    )
    monkeypatch.setattr(retry, "_call_stage2_section", call_stage2)
    monkeypatch.setattr(retry, "_load_component_cards_for_section", lambda section: {})

    brief = await retry._run_section_with_retry(
        plan=plan,
        section=section,
        prior_briefs=[],
        signals=_signals(),
        form=_form(),
        resource_spec={},
        emit_event=None,
        generation_id=None,
    )

    assert call_stage2.await_count == 2
    assert brief._failed is True
    assert brief._errors == [
        "Stage 2 structured output could not be validated: "
        "Exceeded maximum retries (1) for output validation"
    ]


@pytest.mark.asyncio
async def test_non_validation_unexpected_model_behavior_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    monkeypatch.setattr(
        retry,
        "_call_stage2_section",
        AsyncMock(side_effect=UnexpectedModelBehavior("Provider returned an unexpected response")),
    )
    monkeypatch.setattr(retry, "_load_component_cards_for_section", lambda section: {})

    with pytest.raises(UnexpectedModelBehavior, match="Provider returned an unexpected response"):
        await retry._run_section_with_retry(
            plan=plan,
            section=plan.sections[0],
            prior_briefs=[],
            signals=_signals(),
            form=_form(),
            resource_spec={},
            emit_event=None,
            generation_id=None,
        )
