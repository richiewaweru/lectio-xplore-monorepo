"""Pipeline-neutral generation input contracts.

These models are shared by planning and execution.  They intentionally live
outside the retired Studio package so Component Lectio does not depend on a
legacy HTTP/runtime module.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from v3_blueprint.models import LessonMode, ProductionBlueprint, ResourceType


class GenerationInputForm(BaseModel):
    model_config = {"extra": "forbid"}

    grade_level: str
    subject: str
    duration_minutes: int = Field(ge=15, le=90)
    resource_type: ResourceType = "lesson"
    topic: str
    subtopics: list[str] = Field(default_factory=list)
    prior_knowledge: str = ""
    outcome: str
    struggle: str = ""
    learner_level: Literal["below_grade", "on_grade", "above_grade", "mixed"] = "on_grade"
    reading_level: Literal["below_grade", "on_grade", "above_grade", "mixed"] = "on_grade"
    language_support: Literal["none", "some_ell", "many_ell"] = "none"
    prior_knowledge_level: Literal["new_topic", "some_background", "reviewing"] = "new_topic"
    free_text: str = ""


class GenerationSignalSummary(BaseModel):
    model_config = {"extra": "forbid"}

    topic: str
    subtopic: str | None = None
    prior_knowledge: list[str] = Field(default_factory=list)
    learner_needs: list[str] = Field(default_factory=list)
    teacher_goal: str
    inferred_lesson_mode: LessonMode
    lesson_mode_confidence: Literal["low", "high"]


class ProductionBlueprintEnvelope(BaseModel):
    """Structured blueprint output shared by planning adapters."""

    model_config = {"extra": "forbid"}

    blueprint: ProductionBlueprint


__all__ = [
    "GenerationInputForm",
    "GenerationSignalSummary",
    "ProductionBlueprintEnvelope",
]
