"""
pipeline.types.requests

Input types for the generation pipeline.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class GenerationMode(str, Enum):
    DRAFT = "draft"
    BALANCED = "balanced"
    STRICT = "strict"


class PipelineRequest(BaseModel):
    subject: str
    context: str = Field(validation_alias=AliasChoices("context", "topic"))
    grade_band: str
    template_id: str
    preset_id: str
    learner_fit: str = "general"
    section_count: int = 4
    mode: GenerationMode = GenerationMode.BALANCED
    generation_id: str | None = None
    section_plans: list["SectionPlan"] | None = None

    @property
    def topic(self) -> str:
        return self.context

    def max_rerenders(self) -> int:
        if self.mode == GenerationMode.DRAFT:
            return 1
        if self.mode == GenerationMode.STRICT:
            return 3
        return 2

    def interactions_enabled(self) -> bool:
        return self.mode != GenerationMode.DRAFT


class SectionVisualPolicy(BaseModel):
    required: bool = False
    intent: Literal[
        "explain_structure",
        "show_realism",
        "demonstrate_process",
        "compare_variants",
    ] | None = None
    mode: Literal["image", "svg"] | None = None
    goal: str | None = None
    style_notes: str | None = None
    simulation_intent: str | None = None


class BlockVisualPlacement(BaseModel):
    block: Literal["hook", "explanation", "practice", "worked_example"]
    slot_type: Literal["diagram", "diagram_series", "diagram_compare"] = "diagram"
    sizing: Literal["full", "compact"] = "full"
    hint: str = ""
    problem_indices: list[int] | None = None


def count_visual_placements(
    section_or_placements: object | list[BlockVisualPlacement] | None,
) -> int:
    placements = getattr(section_or_placements, "visual_placements", section_or_placements)
    return len(placements or [])


def needs_diagram_from_placements(
    section_or_placements: object | list[BlockVisualPlacement] | None,
) -> bool:
    return count_visual_placements(section_or_placements) > 0


class SectionPlan(BaseModel):
    """One entry in the curriculum outline produced by curriculum_planner."""

    section_id: str
    title: str
    position: int
    focus: str
    role: Literal[
        "intro",
        "develop",
        "practice",
        "synthesis",
        "explain",
        "summary",
        "process",
        "compare",
        "timeline",
        "visual",
        "discover",
    ] = "develop"
    bridges_from: str | None = None
    bridges_to: str | None = None
    needs_diagram: bool = False
    needs_worked_example: bool = False
    required_components: list[str] = Field(default_factory=list)
    optional_components: list[str] = Field(default_factory=list)
    interaction_policy: Literal["required", "allowed", "disabled"] = "allowed"
    diagram_policy: Literal["required", "allowed", "disabled"] = "allowed"
    visual_policy: SectionVisualPolicy | None = None
    enrichment_enabled: bool = True
    continuity_notes: str | None = None
    terms_to_define: list[str] = Field(default_factory=list)
    terms_assumed: list[str] = Field(default_factory=list)
    practice_target: str | None = None
    visual_placements: list[BlockVisualPlacement] = Field(default_factory=list)
