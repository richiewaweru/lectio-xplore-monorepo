from __future__ import annotations

from contracts.lectio import get_section_field_for_component

_FALLBACK_ALIAS_MAP: dict[str, str] = {
    # Amara blueprint
    "concept_intro": "explanation-block",
    "worked_example": "worked-example-card",
    "guided_questions": "practice-stack",
    "key_takeaways": "summary-block",
    # David blueprint
    "retrieval_prompt_set": "quiz-check",
    "problem_set": "practice-stack",
    # Priya blueprint
    "misconception_probe": "interview-anchor",
    "area_model_sequence": "diagram-series",
    "focused_questions": "practice-stack",
    "quick_check": "quiz-check",
    # James blueprint
    "context_overview": "hook-hero",
    "stage_explanations": "explanation-block",
    "diagram_series": "diagram-series",
    "short_questions": "practice-stack",
    "recap": "summary-block",
}


def canonical_component_id(component: str) -> str:
    if get_section_field_for_component(component):
        return component
    return _FALLBACK_ALIAS_MAP.get(component, "explanation-block")


__all__ = ["canonical_component_id"]
