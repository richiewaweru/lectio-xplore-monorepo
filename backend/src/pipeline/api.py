from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_validator

from pipeline.state import NodeFailureDetail
from pipeline.types.requests import (
    GenerationMode as PipelineMode,
    PipelineRequest as PipelineCommand,
)
from pipeline.types.section_content import SectionContent

if TYPE_CHECKING:
    from pipeline.state import QCReport

GradeBand = Literal["primary", "secondary", "advanced"]


class PipelineIssue(BaseModel):
    block: str
    severity: Literal["blocking", "warning"]
    message: str


class PipelineSectionReport(BaseModel):
    section_id: str
    passed: bool
    issues: list[PipelineIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_qc_report(cls, report: QCReport) -> PipelineSectionReport:
        """Convert an internal QCReport (issues: list[dict]) to the API model."""
        return cls(
            section_id=report.section_id,
            passed=report.passed,
            issues=[
                PipelineIssue(
                    block=issue.get("block", "unknown"),
                    severity=issue.get("severity", "warning"),
                    message=issue.get("message", ""),
                )
                for issue in report.issues
            ],
            warnings=list(report.warnings),
        )


class PipelineErrorInfo(BaseModel):
    node: str
    message: str
    section_id: str | None = None
    recoverable: bool = True


class PipelineSectionManifestItem(BaseModel):
    section_id: str
    title: str
    position: int


class FailedSectionEntry(BaseModel):
    section_id: str
    title: str
    position: int
    focus: str | None = None
    bridges_from: str | None = None
    bridges_to: str | None = None
    needs_diagram: bool = False
    visual_placements_count: int = 0
    needs_worked_example: bool = False
    failed_at_node: str
    error_type: str
    error_summary: str
    attempt_count: int = 0
    can_retry: bool = False
    missing_components: list[str] = Field(default_factory=list)
    failure_detail: NodeFailureDetail | None = None


class PipelinePartialSectionEntry(BaseModel):
    section_id: str
    template_id: str
    content: SectionContent
    status: str = "partial"
    visual_mode: Literal["svg", "image"] | None = None
    pending_assets: list[str] = Field(default_factory=list)
    updated_at: datetime

    @field_validator("updated_at", mode="before")
    @classmethod
    def _normalize_updated_at(cls, value: datetime | str) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class PipelineDocument(BaseModel):
    generation_id: str
    subject: str
    context: str
    mode: PipelineMode = PipelineMode.BALANCED
    template_id: str
    preset_id: str
    status: Literal["pending", "running", "partial", "completed", "failed"] = "pending"
    section_manifest: list[PipelineSectionManifestItem] = Field(default_factory=list)
    sections: list[SectionContent] = Field(default_factory=list)
    partial_sections: list[PipelinePartialSectionEntry] = Field(default_factory=list)
    failed_sections: list[FailedSectionEntry] = Field(default_factory=list)
    qc_reports: list[PipelineSectionReport] = Field(default_factory=list)
    quality_passed: bool | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @field_validator("created_at", "updated_at", "completed_at", mode="before")
    @classmethod
    def _normalize_utc(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class PipelineResult(BaseModel):
    document: PipelineDocument
    completed_nodes: list[str] = Field(default_factory=list)
    errors: list[PipelineErrorInfo] = Field(default_factory=list)
    generation_time_seconds: float


__all__ = [
    "FailedSectionEntry",
    "GradeBand",
    "PipelineCommand",
    "PipelineDocument",
    "PipelineErrorInfo",
    "PipelineIssue",
    "PipelinePartialSectionEntry",
    "PipelineResult",
    "PipelineSectionManifestItem",
    "PipelineSectionReport",
]
