from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Generated blocks (proposal 2 Step 1)


class GeneratedComponentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    section_id: str
    component_id: str
    section_field: str
    position: int
    data: dict[str, Any]
    source_work_order_id: str


class GeneratedQuestionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    section_id: str
    difficulty: str
    data: dict[str, Any]
    expected_answer: str
    expected_working: str | None = None
    diagram_required: bool = False
    source_work_order_id: str


VisualMode = Literal["diagram", "diagram_series", "diagram_compare", "image", "simulation"]
VisualStyle = Literal["diagram_precision", "illustration"]
_VISUAL_STYLES = {"diagram_precision", "illustration"}


class GeneratedVisualBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visual_id: str
    attaches_to: str
    frame_index: int | None = None
    mode: VisualMode
    image_url: str | None = None
    html_content: str | None = None
    fallback_image_url: str | None = None
    caption: str | None = None
    alt_text: str | None = None
    source_work_order_id: str
    component_id: str | None = None
    parent_visual_id: str | None = None
    status: Literal["ready", "failed", "omitted_quality", "flagged_quality"] = "ready"
    error_message: str | None = None
    qc_reasons: list[str] = Field(default_factory=list)
    qc_correction_hint: str | None = None


AnswerKeyStyle = Literal["answers_only", "brief_explanations", "full_working"]


class GeneratedAnswerKeyBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_key_id: str
    style: AnswerKeyStyle
    entries: list[dict[str, Any]]
    source_work_order_id: str


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: str
    blueprint_id: str
    component_blocks: list[GeneratedComponentBlock] = Field(default_factory=list)
    question_blocks: list[GeneratedQuestionBlock] = Field(default_factory=list)
    visual_blocks: list[GeneratedVisualBlock] = Field(default_factory=list)
    answer_key: GeneratedAnswerKeyBlock | None = None
    warnings: list[str] = Field(default_factory=list)


# --- Executor outcome wrapper


class ExecutorOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    blocks: list[Any] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    retried: bool = False


# --- Work orders consumed by executors


class RegisterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = "balanced"
    sentence_length: str = "moderate"
    vocabulary_policy: str = "tiered_support"
    tone: str = "instructional_clear"
    avoid: list[str] = Field(default_factory=list)


class LearnerProfileSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_summary: str = "Mixed class"
    reading_load: str = "moderate"
    language_support: str = "baseline"
    pacing: str = "standard"


class SourceOfTruthEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    text: str
    unit_tokens: list[str] = Field(default_factory=list)


class Correction(BaseModel):
    """Teacher correction as typed data — countable, displayable, removable."""

    model_config = ConfigDict(extra="forbid")

    text: str
    created_at: str
    applied_in_generation: str | None = None


class WriterMisconception(BaseModel):
    """Named misconception from the section's concept card — structured, not prose."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str


class WriterSectionComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    teacher_label: str = ""
    content_intent: str
    uses_anchor_id: str | None = None
    corrections: list[Correction] = Field(default_factory=list)


class WriterSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    learning_intent: str
    role: str = ""
    transition_note: str | None = None
    card_id: str | None = None
    anchor_example: str = ""
    anchor_reuse_scope: str = ""
    misconceptions: list[WriterMisconception] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    register_notes: list[str] = Field(default_factory=list)
    components: list[WriterSectionComponent] = Field(default_factory=list)


class SectionWriterWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    work_order_id: str
    section: WriterSection
    register_spec: RegisterSpec = Field(
        default_factory=RegisterSpec,
        alias="register",
        serialization_alias="register",
    )
    learner_profile: LearnerProfileSpec = Field(default_factory=LearnerProfileSpec)
    support_adaptations: list[str] = Field(default_factory=list)
    source_of_truth: list[SourceOfTruthEntry] = Field(default_factory=list)
    consistency_rules: list[str] = Field(default_factory=list)
    component_cards: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Component cards from lectio-content-contract.json keyed by component_id. "
            "Each card contains section_field, field_contracts, component_constraints, "
            "role, cognitive_job, and one compact example. "
            "Used by the section writer prompt and validation layer."
        ),
    )
    template_id: str


class WriterQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    difficulty: str
    diagram_required: bool = False
    skill_target: str = "fluency"
    scaffolding: str = "standard"
    purpose: str = "practice"
    uses_anchor_id: str | None = None
    expected_answer: str
    expected_working: str | None = None
    student_facing_constraints: list[str] = Field(default_factory=list)


class QuestionWriterWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    work_order_id: str
    section_id: str
    questions: list[WriterQuestion] = Field(default_factory=list)
    source_of_truth: list[SourceOfTruthEntry] = Field(default_factory=list)
    register_spec: RegisterSpec = Field(
        default_factory=RegisterSpec,
        alias="register",
        serialization_alias="register",
    )
    consistency_rules: list[str] = Field(default_factory=list)


class VisualFrameSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    must_show: list[str] = Field(default_factory=list)


class VisualPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    attaches_to: str
    component_id: str | None = None
    mode: VisualMode = "diagram"
    visual_style: VisualStyle | None = None
    purpose: str = ""
    must_show: list[str] = Field(default_factory=list)
    must_not_show: list[str] = Field(default_factory=list)
    labels_required: list[str] = Field(default_factory=list)
    uses_anchor_id: str | None = None
    consistency_locks: list[str] = Field(default_factory=list)
    print_requirements: list[str] = Field(default_factory=list)
    frames: list[VisualFrameSpec] = Field(default_factory=list)

    @field_validator("visual_style", mode="before")
    @classmethod
    def normalize_visual_style(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value in _VISUAL_STYLES:
            return value
        return None


VisualDependency = Literal["blueprint_only", "section_text", "question_text"]


class VisualGeneratorWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_order_id: str
    resource_type: str = "lesson"
    dependency: VisualDependency = "blueprint_only"
    visual: VisualPlanItem
    source_of_truth: list[SourceOfTruthEntry] = Field(default_factory=list)


class AnswerKeyPlanSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: AnswerKeyStyle
    include_question_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AnswerKeyExecutorWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_order_id: str
    questions: list[WriterQuestion]
    answer_key_plan: AnswerKeyPlanSpec
    source_of_truth: list[SourceOfTruthEntry] = Field(default_factory=list)


# --- Compiled orders + DraftPack (proposal 2 Step 1b)


class CompiledWorkOrders(BaseModel):
    """Full execution-ready bundle emitted by deterministic compiler."""

    model_config = ConfigDict(extra="forbid")

    generation_id: str
    blueprint_id: str
    template_id: str
    section_orders: list[SectionWriterWorkOrder]
    question_orders: list[QuestionWriterWorkOrder]
    visual_orders: list[VisualGeneratorWorkOrder]
    answer_key_order: AnswerKeyExecutorWorkOrder | None = None


BookletStatus = Literal[
    "streaming_preview",
    "draft_ready",
    "draft_with_warnings",
    "draft_needs_review",
    "final_ready",
    "final_with_warnings",
    "failed_unusable",
]

SectionAssemblyStatus = Literal["complete", "incomplete", "failed"]


class SectionAssemblyDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    status: SectionAssemblyStatus
    renderable: bool
    missing_components: list[str] = Field(default_factory=list)
    missing_visuals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DraftPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: str
    blueprint_id: str
    template_id: str
    subject: str
    status: BookletStatus
    sections: list[dict[str, Any]]
    visual_blocks: list[GeneratedVisualBlock] = Field(default_factory=list)
    answer_key: GeneratedAnswerKeyBlock | None = None
    warnings: list[str] = Field(default_factory=list)
    section_diagnostics: list[SectionAssemblyDiagnostic] = Field(default_factory=list)
    booklet_issues: list[dict[str, Any]] = Field(default_factory=list)

    def to_json_preview(self, *, indent: int | None = None) -> str:
        payload = self.model_dump(mode="json", exclude_none=True)
        kwargs: dict[str, Any] = {}
        if indent is not None:
            kwargs["indent"] = indent
        return json.dumps(payload, sort_keys=False, ensure_ascii=False, **kwargs)


__all__ = [
    "AnswerKeyExecutorWorkOrder",
    "AnswerKeyPlanSpec",
    "AnswerKeyStyle",
    "BookletStatus",
    "CompiledWorkOrders",
    "Correction",
    "WriterMisconception",
    "DraftPack",
    "SectionAssemblyDiagnostic",
    "SectionAssemblyStatus",
    "ExecutionResult",
    "ExecutorOutcome",
    "GeneratedAnswerKeyBlock",
    "GeneratedComponentBlock",
    "GeneratedQuestionBlock",
    "GeneratedVisualBlock",
    "LearnerProfileSpec",
    "QuestionWriterWorkOrder",
    "RegisterSpec",
    "SectionWriterWorkOrder",
    "SourceOfTruthEntry",
    "VisualDependency",
    "VisualFrameSpec",
    "VisualGeneratorWorkOrder",
    "VisualPlanItem",
    "WriterQuestion",
    "WriterSection",
    "WriterSectionComponent",
]
