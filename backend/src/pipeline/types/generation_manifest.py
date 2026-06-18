from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GenerationFieldContract(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    component_id: str
    field_name: str
    required: bool = False
    external: bool = False
    schema: dict = Field(default_factory=dict)
    capacity: dict = Field(default_factory=dict)
    generation_hint: str | None = None


class SectionGenerationManifest(BaseModel):
    template_id: str
    section_id: str
    required_fields: list[GenerationFieldContract] = Field(default_factory=list)
    optional_fields: list[GenerationFieldContract] = Field(default_factory=list)
    external_fields: list[GenerationFieldContract] = Field(default_factory=list)

    def active_text_fields(self) -> list[GenerationFieldContract]:
        return [*self.required_fields, *self.optional_fields]
