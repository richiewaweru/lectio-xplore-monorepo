from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SectionSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    intent: str
    preferred_components: list[str] = Field(default_factory=list)
    allowed_components: list[str] = Field(default_factory=list)
    forbidden_components: list[str] = Field(default_factory=list)
    max_count: int = 1
    placement: str | None = None
    only_when_support: str | None = None


class SectionsSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    required: list[SectionSpec] = Field(default_factory=list)
    optional: list[SectionSpec] = Field(default_factory=list)


class DepthVariant(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sections: str
    min_sections: int
    max_sections: int
    time_minutes: str
    questions: str
    note: str | None = None
    warning: str | None = None


class SupportModification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    adds_section: dict | None = None
    adds_component: dict | None = None
    ensures_role: str | None = None
    ensures_component: dict | None = None
    modifies_role: str | None = None
    modifies_all_sections: dict | None = None
    intent_note: str | None = None
    preferred_components: list[str] = Field(default_factory=list)
    placement: str | None = None
    note: str | None = None
    only_when_support: str | None = None


class VisualPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    quick: int
    standard: int
    deep: int
    allow_diagrams: bool
    allow_images: bool
    note: str | None = None


class TextPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    density: str
    max_reading_load: str
    note: str | None = None


class ResourceSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    label: str
    version: str
    intent: str
    when_to_use: list[str] = Field(default_factory=list)
    never_use_when: list[str] = Field(default_factory=list)
    allowed_outcomes: list[str] = Field(default_factory=list)
    depth: dict[str, DepthVariant]
    sections: SectionsSpec
    forbidden_components: list[str] = Field(default_factory=list)
    supports: dict[str, SupportModification] = Field(default_factory=dict)
    visuals: VisualPolicy
    text: TextPolicy
    validation: list[str] = Field(default_factory=list)

    def all_allowed_components_for_role(self, role: str) -> set[str]:
        for section in [*self.sections.required, *self.sections.optional]:
            if section.role == role:
                return set(section.preferred_components) | set(section.allowed_components)
        return set()

    def forbidden_for_role(self, role: str) -> set[str]:
        role_forbidden: set[str] = set()
        for section in [*self.sections.required, *self.sections.optional]:
            if section.role == role:
                role_forbidden = set(section.forbidden_components)
        return role_forbidden | set(self.forbidden_components)

    def depth_limit(self, depth: str) -> DepthVariant:
        return self.depth[depth]
