from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning import retry, structural_planner


def _signals() -> V3SignalSummary:
    return V3SignalSummary(
        topic="Fractions",
        subtopic="Equivalent fractions",
        prior_knowledge=["equal sharing"],
        learner_needs=[],
        teacher_goal="Build confidence",
        inferred_resource_type="lesson",
        confidence="medium",
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
