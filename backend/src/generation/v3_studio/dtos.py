from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from v3_blueprint.models import LessonMode, ProductionBlueprint, ResourceType


class V3InputForm(BaseModel):
    model_config = {"extra": "forbid"}

    # Step 1 - Basics
    grade_level: str  # e.g. "Grade 9"
    subject: str
    duration_minutes: int = Field(ge=15, le=90)
    resource_type: ResourceType = "lesson"

    # Step 2 - Intent
    topic: str  # raw topic text
    subtopics: list[str] = Field(default_factory=list)  # resolved subtopics
    prior_knowledge: str = ""  # what they've already covered
    outcome: str
    struggle: str = ""

    # Step 3 - Tuning
    learner_level: Literal["below_grade", "on_grade", "above_grade", "mixed"] = "on_grade"
    reading_level: Literal["below_grade", "on_grade", "above_grade", "mixed"] = "on_grade"
    language_support: Literal["none", "some_ell", "many_ell"] = "none"
    prior_knowledge_level: Literal["new_topic", "some_background", "reviewing"] = "new_topic"

    # Step 4 - Optional intent
    free_text: str = ""  # anything not captured above


class V3SignalSummary(BaseModel):
    model_config = {"extra": "forbid"}

    topic: str
    subtopic: str | None = None
    prior_knowledge: list[str] = Field(default_factory=list)
    learner_needs: list[str] = Field(default_factory=list)
    teacher_goal: str
    inferred_lesson_mode: LessonMode
    lesson_mode_confidence: Literal["low", "high"]


class V3ComponentPlanDTO(BaseModel):
    model_config = {"extra": "forbid"}

    component_id: str
    teacher_label: str
    content_intent: str


class V3SectionPlanItemDTO(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    title: str
    order: int
    learning_intent: str
    components: list[V3ComponentPlanDTO] = Field(default_factory=list)
    visual_required: bool = False


class V3QuestionPlanDTO(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    difficulty: Literal["warm", "medium", "cold", "transfer"]
    expected_answer: str
    diagram_required: bool
    attaches_to_section_id: str
    prompt: str = ""


class V3AnchorExampleDTO(BaseModel):
    model_config = {"extra": "forbid"}

    label: str
    facts: dict[str, str] = Field(default_factory=dict)
    correct_result: str | None = None
    reuse_scope: str


class V3LearnerContextDTO(BaseModel):
    model_config = {"extra": "forbid"}

    grade_level: str
    subject: str
    duration_minutes: int
    resource_type: ResourceType
    outcome: str
    struggle: str
    inferred_lesson_mode: str | None = None
    learner_level: str
    reading_level: str
    language_support: str
    prior_knowledge_level: str
    prior_knowledge: str


class BlueprintPreviewDTO(BaseModel):
    model_config = {"extra": "forbid"}

    blueprint_id: str
    resource_type: str
    title: str
    template_id: str = "guided-concept-path"
    anchor: V3AnchorExampleDTO | None = None
    section_plan: list[V3SectionPlanItemDTO] = Field(default_factory=list)
    question_plan: list[V3QuestionPlanDTO] = Field(default_factory=list)
    register_summary: str = ""
    support_summary: list[str] = Field(default_factory=list)
    learner_context: V3LearnerContextDTO | None = None


class V3ChunkedPlanStartRequest(BaseModel):
    model_config = {"extra": "forbid"}

    signals: V3SignalSummary
    form: V3InputForm


class V3ChunkedRegenerateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    note: str = ""


class V3ChunkedApproveRequest(BaseModel):
    model_config = {"extra": "forbid"}

    display_title: str | None = Field(default=None, max_length=120)


class V3ChunkedRetrySectionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    section_id: str


class V3ChunkedPlanStateDTO(BaseModel):
    model_config = {"extra": "forbid"}

    generation_id: str
    stage: str
    structural_plan: dict[str, Any] | None = None
    section_briefs: dict[str, Any] = Field(default_factory=dict)
    failed_sections: list[str] = Field(default_factory=list)
    blueprint_id: str | None = None
    execution_started: bool = False
    next_action: str | None = None
    display_title: str | None = None
    inferred_lesson_mode: LessonMode | None = None
    lesson_mode_confidence: Literal["low", "high"] | None = None


class AdjustBlueprintRequest(BaseModel):
    model_config = {"extra": "forbid"}

    blueprint_id: str
    adjustment: str


class V3GenerateStartRequest(BaseModel):
    model_config = {"extra": "forbid"}

    generation_id: str
    blueprint_id: str
    template_id: str = "guided-concept-path"
    blueprint: dict[str, Any] | None = None
    display_title: str | None = Field(default=None, max_length=120)


class V3GenerateStartResponse(BaseModel):
    model_config = {"extra": "forbid"}

    generation_id: str


class V3PdfExportRequest(BaseModel):
    """PDF export for v3 Studio backed by persisted generation documents."""

    model_config = {"extra": "forbid"}

    school_name: str = Field(min_length=1)
    teacher_name: str = Field(min_length=1)
    date: str | None = None
    include_toc: bool = True
    include_answers: bool = True


class V3GenerationHistoryItemDTO(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    subject: str
    title: str
    status: str
    booklet_status: str
    section_count: int
    document_section_count: int
    template_id: str
    created_at: str | None = None
    completed_at: str | None = None


class V3GenerationDetailDTO(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    subject: str
    title: str
    status: str
    booklet_status: str
    template_id: str
    section_count: int
    document_section_count: int
    report_json: dict[str, Any]
    blueprint_id: str | None = None
    planning_artifact: dict[str, Any] | None = None
    created_at: str | None = None
    completed_at: str | None = None


class ProductionBlueprintEnvelope(BaseModel):
    """LLM structured output wrapper."""

    model_config = {"extra": "forbid"}

    blueprint: ProductionBlueprint


__all__ = [
    "AdjustBlueprintRequest",
    "BlueprintPreviewDTO",
    "V3ChunkedApproveRequest",
    "V3ChunkedPlanStartRequest",
    "V3ChunkedPlanStateDTO",
    "V3ChunkedRegenerateRequest",
    "V3ChunkedRetrySectionRequest",
    "ProductionBlueprintEnvelope",
    "V3ComponentPlanDTO",
    "V3GenerateStartRequest",
    "V3GenerateStartResponse",
    "V3GenerationDetailDTO",
    "V3GenerationHistoryItemDTO",
    "V3PdfExportRequest",
    "V3InputForm",
    "V3LearnerContextDTO",
    "V3QuestionPlanDTO",
    "V3SectionPlanItemDTO",
    "V3SignalSummary",
]
