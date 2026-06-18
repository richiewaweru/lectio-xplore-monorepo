from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pipeline.types.requests import GenerationMode


class Generation(BaseModel):
    id: str
    user_id: str
    subject: str
    context: str = ""
    mode: GenerationMode = GenerationMode.BALANCED
    status: Literal["pending", "running", "partial", "completed", "failed"] = "pending"
    document_path: str | None = None
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
    planning_spec_json: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    last_heartbeat: datetime | None = None

    @field_validator("created_at", "completed_at", "last_heartbeat", mode="before")
    @classmethod
    def _normalize_utc(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
