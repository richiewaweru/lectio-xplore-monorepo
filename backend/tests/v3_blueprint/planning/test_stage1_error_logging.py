from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning import retry, structural_planner
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    LessonIntent,
    QPlanItem,
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


@pytest.mark.asyncio
async def test_call_stage1_prints_traceback_and_reraises() -> None:
    signals = _signals()
    form = _form()
    error = RuntimeError("llm blew up")

    with (
        patch.object(structural_planner, "run_llm", new=AsyncMock(side_effect=error)),
        patch("builtins.print") as mock_print,
    ):
        with pytest.raises(RuntimeError, match="llm blew up"):
            await structural_planner._call_stage1(
                signals,
                form,
                {"resource_type": "lesson"},
                generation_id="gen-123",
            )

    mock_print.assert_called_once()
    printed = mock_print.call_args.args[0]
    assert "[_CALL_STAGE1 ERROR]" in printed
    assert "generation_id=gen-123" in printed
    assert "type=RuntimeError" in printed
    assert "message=llm blew up" in printed
    assert mock_print.call_args.kwargs["flush"] is True


@pytest.mark.asyncio
async def test_run_stage1_with_retry_prints_attempt_exception_and_reraises() -> None:
    signals = _signals()
    form = _form()
    error = ValueError("bad stage1")

    with (
        patch.object(retry, "_call_stage1", new=AsyncMock(side_effect=error)),
        patch("builtins.print") as mock_print,
    ):
        with pytest.raises(ValueError, match="bad stage1"):
            await retry.run_stage1_with_retry(
                signals,
                form,
                {"resource_type": "lesson"},
                generation_id="gen-456",
                trace_id="trace-456",
            )

    mock_print.assert_called_once()
    printed = mock_print.call_args.args[0]
    assert "[STAGE1 ATTEMPT 1 EXCEPTION]" in printed
    assert "generation_id=gen-456" in printed
    assert "type=ValueError" in printed
    assert mock_print.call_args.kwargs["flush"] is True


@pytest.mark.asyncio
async def test_call_stage1_rejects_role_outside_active_resource_spec() -> None:
    signals = _signals()
    form = _form()
    invalid_plan = StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="By the end students can compare fractions.",
            structure_rationale="Concrete-first structure for novice learners.",
        ),
        anchor=AnchorSpec(
            example="splitting a pizza into 8 equal slices",
            reuse_scope="used in intro and practice",
        ),
        voice=VoiceSpec(register_name="simple", tone="encouraging"),
        prior_knowledge=["equal sharing"],
        sections=[
            SectionPlan(
                id="intro",
                title="Intro",
                role="invalid_role",
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

    with patch.object(
        structural_planner,
        "run_llm",
        new=AsyncMock(return_value=type("Result", (), {"output": invalid_plan})()),
    ):
        with pytest.raises(ValueError, match="which is not in the active resource spec roles"):
            await structural_planner._call_stage1(
                signals,
                form,
                {
                    "resource_type": "lesson",
                    "spec": {
                        "required_roles": ["intro", "practice"],
                        "optional_roles": ["summary"],
                    },
                },
                generation_id="gen-role-guard",
            )
