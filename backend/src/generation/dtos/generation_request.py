from pydantic import BaseModel, Field, field_validator, model_validator

from planning.dtos import GenerationSpec
from pipeline.types.requests import GenerationMode


class GenerationRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    context: str = Field(..., max_length=10000)
    mode: GenerationMode = GenerationMode.BALANCED
    template_id: str
    preset_id: str
    section_count: int = Field(default=4, ge=1, le=8)
    generation_spec: GenerationSpec | None = None

    @field_validator("subject", "context", "template_id", "preset_id")
    @classmethod
    def _trim_required_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _validate_required_text(self) -> "GenerationRequest":
        for field_name in ("subject", "context", "template_id", "preset_id"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must not be empty.")
        return self


class GenerationAcceptedResponse(BaseModel):
    generation_id: str
    status: str
    events_url: str
    document_url: str
    report_url: str
