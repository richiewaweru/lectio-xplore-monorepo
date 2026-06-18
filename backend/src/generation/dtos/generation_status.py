from pydantic import BaseModel, Field

from pipeline.api import PipelineDocument
from telemetry.dtos.generation_report import (
    GenerationPlannerTrace,
    GenerationReport,
    GenerationReportOutlineSection,
)


class GenerationHistoryItem(BaseModel):
    id: str
    subject: str
    mode: str
    status: str
    error_type: str | None = None
    error_code: str | None = None
    requested_template_id: str
    resolved_template_id: str | None = None
    requested_preset_id: str
    resolved_preset_id: str | None = None
    section_count: int | None = None
    quality_passed: bool | None = None
    generation_time_seconds: float | None = None
    created_at: str | None = None
    completed_at: str | None = None


class GenerationDetail(BaseModel):
    id: str
    subject: str
    context: str
    mode: str
    status: str
    error: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    requested_template_id: str
    resolved_template_id: str | None = None
    requested_preset_id: str
    resolved_preset_id: str | None = None
    section_count: int | None = None
    quality_passed: bool | None = None
    generation_time_seconds: float | None = None
    created_at: str | None = None
    completed_at: str | None = None
    document_path: str | None = None
    report_url: str | None = None
    runtime_curriculum_outline: list[GenerationReportOutlineSection] = Field(
        default_factory=list
    )
    planner_trace: GenerationPlannerTrace | None = None


class GenerationListResponse(BaseModel):
    items: list[GenerationHistoryItem] = Field(default_factory=list)


class GenerationDocumentResponse(BaseModel):
    document: PipelineDocument


class GenerationReportResponse(BaseModel):
    report: GenerationReport

