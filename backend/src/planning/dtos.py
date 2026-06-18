from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from pipeline.types.requests import GenerationMode, SectionPlan


class BriefRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=200)
    extra_context: str = Field(default="", max_length=1000)
    mode: GenerationMode = Field(default=GenerationMode.BALANCED)

    @field_validator("intent", "audience", "extra_context")
    @classmethod
    def _trim_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _validate_required_text(self) -> "BriefRequest":
        if not self.intent:
            raise ValueError("intent must not be empty.")
        if not self.audience:
            raise ValueError("audience must not be empty.")
        return self


class GenerationSpec(BaseModel):
    template_id: str = Field(min_length=1)
    preset_id: str = Field(default="blue-classroom", min_length=1)
    mode: GenerationMode = Field(default=GenerationMode.BALANCED)
    section_count: int = Field(ge=2, le=4)
    sections: list[SectionPlan] = Field(min_length=2, max_length=4)
    warning: str | None = None
    rationale: str = Field(min_length=1)
    source_brief: BriefRequest

    @field_validator("template_id", "preset_id", "rationale", "warning")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _validate_alignment(self) -> "GenerationSpec":
        if self.preset_id != "blue-classroom":
            raise ValueError("GenerationSpec must target blue-classroom in phase 1.")
        if self.section_count != len(self.sections):
            raise ValueError("section_count must match the number of sections.")
        if [section.position for section in self.sections] != list(range(1, len(self.sections) + 1)):
            raise ValueError("Section positions must be sequential starting at 1.")
        for section in self.sections:
            if len(section.title.split()) > 8:
                raise ValueError("Section titles must be eight words or fewer.")
        return self
