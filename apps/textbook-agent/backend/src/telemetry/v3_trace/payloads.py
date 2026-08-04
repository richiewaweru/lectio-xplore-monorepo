from __future__ import annotations

from pydantic import BaseModel, Field


class BlueprintGeneratedPayload(BaseModel):
    blueprint_id: str
    title: str
    subject: str
    template_id: str
    lens_ids: list[str]
    lesson_mode: str
    section_count: int
    question_count: int
    has_anchor: bool


class BlueprintAdjustedPayload(BaseModel):
    blueprint_id: str
    adjustment_summary: str
    new_section_count: int
    new_question_count: int


class GenerationStartedPayload(BaseModel):
    generation_id: str
    blueprint_id: str
    template_id: str


class SectionCompletedPayload(BaseModel):
    section_id: str
    section_title: str
    ok: bool
    component_count: int
    warnings: list[str] = Field(default_factory=list)


class SectionFailedPayload(BaseModel):
    section_id: str
    section_title: str
    node: str
    error_type: str
    error_summary: str
    attempt: int


class VisualCompletedPayload(BaseModel):
    section_id: str
    mode: str
    frame_count: int
    ok: bool
    provider: str = "xai"


class VisualFailedPayload(BaseModel):
    section_id: str
    mode: str
    error_summary: str
    attempt: int


class QuestionsCompletedPayload(BaseModel):
    section_id: str
    question_count: int
    ok: bool


class AnswerKeyCompletedPayload(BaseModel):
    style: str
    question_count: int
    ok: bool


class CoherenceIssue(BaseModel):
    category: str
    severity: str
    message: str
    executor: str


class CoherenceReviewedPayload(BaseModel):
    status: str
    blocking_count: int
    major_count: int
    minor_count: int
    issues: list[CoherenceIssue]


class RepairAttemptedPayload(BaseModel):
    target_id: str
    executor: str
    attempt: int
    ok: bool
    target_type: str
    reason: str


class RepairEscalatedPayload(BaseModel):
    target_id: str
    reason: str
    attempts: int


class NodeLLMSummary(BaseModel):
    calls: int
    tokens_in: int = 0
    tokens_out: int = 0
    thinking_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms_total: int = 0


class GenerationCompletedPayload(BaseModel):
    status: str
    sections_ready: int
    sections_failed: int
    duration_seconds: float
    total_cost_usd: float
    llm_summary: dict[str, NodeLLMSummary]


class GenerationFailedPayload(BaseModel):
    error_type: str
    error_summary: str
    last_successful_phase: str
    sections_ready: int
    sections_failed: int
    duration_seconds: float
    llm_summary: dict[str, NodeLLMSummary]
