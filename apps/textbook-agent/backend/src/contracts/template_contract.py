"""
contracts.template_contract

The subset of Lectio's TemplateContract that the pipeline needs.
Read from backend/contracts/{template_id}.json â€” produced by
npm run export-contracts in the Lectio library.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GenerationGuidance(BaseModel):
    tone: str
    pacing: str
    chunking: str
    emphasis: str
    avoid: list[str]


class TemplateContractSummary(BaseModel):
    id: str
    name: str
    family: str
    intent: str
    tagline: str
    reading_style: str | None = None
    tags: list[str] = Field(default_factory=list)
    lesson_flow: list[str] = Field(default_factory=list)
    required_components: list[str] = Field(default_factory=list)
    optional_components: list[str] = Field(default_factory=list)
    always_present: list[str] = Field(default_factory=list)
    available_components: list[str] = Field(default_factory=list)
    contextually_present: list[str] = Field(default_factory=list)
    component_budget: dict[str, int] = Field(default_factory=dict)
    max_per_section: dict[str, int] = Field(default_factory=dict)
    default_behaviours: dict[str, str] = Field(default_factory=dict)
    section_role_defaults: dict[str, list[str]] = Field(default_factory=dict)
    generation_guidance: GenerationGuidance
    best_for: list[str] = Field(default_factory=list)
    not_ideal_for: list[str] = Field(default_factory=list)
    learner_fit: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    interaction_level: str
    layout_notes: list[str] = Field(default_factory=list)
    responsive_rules: list[str] = Field(default_factory=list)
    print_rules: list[str] = Field(default_factory=list)
    why_this_template_exists: str = ""
    allowed_presets: list[str] = Field(default_factory=list)


class TemplatePresetSummary(BaseModel):
    id: str
    name: str
    palette: str
    typography: str
    density: str
    surface_style: str

