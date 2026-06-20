from __future__ import annotations

from typing import Any

import pytest

from generation.v3_studio.agents import extract_signals
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary


def _example_form(**overrides: Any) -> V3InputForm:
    payload = {
        "grade_level": "Grade 7",
        "subject": "Mathematics",
        "duration_minutes": 50,
        "topic": "Compound area",
        "subtopics": ["L-shapes", "Decompose into rectangles"],
        "prior_knowledge": "Rectangle area",
        "lesson_mode": "first_exposure",
        "intended_outcome": "understand",
        "learner_level": "on_grade",
        "reading_level": "on_grade",
        "language_support": "some_ell",
        "prior_knowledge_level": "some_background",
        "support_needs": ["visuals", "worked_examples"],
        "learning_preferences": ["step_by_step"],
        "free_text": "Use real-world floorplan examples if possible.",
    }
    payload.update(overrides)
    return V3InputForm(**payload)


@pytest.mark.asyncio
async def test_extract_signals_includes_structured_form_in_user_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_run_llm(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return type(
            "Result",
            (),
            {
                "output": V3SignalSummary(
                    topic="Compound area",
                    subtopic=None,
                    prior_knowledge=[],
                    learner_needs=[],
                    teacher_goal="Learners can decompose shapes to find area.",
                    inferred_resource_type="lesson",
                    confidence="high",
                )
            },
        )()

    monkeypatch.setattr("generation.v3_studio.agents.run_llm", fake_run_llm)

    form = _example_form()
    _ = await extract_signals(form, trace_id="tid-test")

    user_prompt = str(captured.get("user_prompt", ""))
    assert "Grade level: Grade 7" in user_prompt
    assert "Topic: Compound area" in user_prompt
    assert "Subtopics: L-shapes, Decompose into rectangles" in user_prompt
    assert "Lesson mode: first_exposure" in user_prompt
    assert "Learning preferences: step_by_step" in user_prompt




