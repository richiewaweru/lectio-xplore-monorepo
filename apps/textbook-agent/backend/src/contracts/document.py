from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from contracts.section_content import SectionContent


class PipelineSectionManifestItem(BaseModel):
    section_id: str
    title: str
    position: int


class PipelineDocument(BaseModel):
    generation_id: str
    subject: str
    context: str
    mode: str = "v3"
    template_id: str
    preset_id: str
    status: Literal["pending", "running", "partial", "completed", "failed"] = "pending"
    section_manifest: list[PipelineSectionManifestItem] = Field(default_factory=list)
    sections: list[SectionContent] = Field(default_factory=list)
    quality_passed: bool | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @field_validator("created_at", "updated_at", "completed_at", mode="before")
    @classmethod
    def _normalize_utc(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
