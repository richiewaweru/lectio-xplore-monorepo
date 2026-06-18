from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DiagramPlan(BaseModel):
    enabled: bool
    reasoning: str
    mode: Literal["svg", "image"] | None = None
    required_targets: list[str] = Field(default_factory=list)
    diagram_type: str | None = None
    compare_before_label: str | None = None
    compare_after_label: str | None = None
    focus_area: str | None = None
    key_concepts: list[str] = Field(default_factory=list)
    visual_guidance: str | None = None

    # Fallback context (when diagram replaces an interaction)
    fallback_from_interaction: bool = False
    interaction_intent: str | None = None
    interaction_elements: list[str] = Field(default_factory=list)


class InteractionPlan(BaseModel):
    enabled: bool
    reasoning: str
    interaction_type: str | None = None
    anchor_block: str | None = None

    # Pedagogical design (populated by LLM composition planner)
    manipulable_element: str | None = None
    response_element: str | None = None
    pedagogical_payoff: str | None = None
    complexity: str = "simple"
    estimated_time_minutes: int = 3


class CompositionPlan(BaseModel):
    diagram: DiagramPlan
    interaction: InteractionPlan
    interactions: list[InteractionPlan] = Field(default_factory=list)
    confidence: str = "high"
    reasoning: str = ""
    notes: str | None = None

    @model_validator(mode="after")
    def _sync_interaction_fields(self) -> "CompositionPlan":
        """Keep singular `interaction` and plural `interactions` in sync."""
        if self.interactions and not self.interaction.enabled:
            # interactions list is the source of truth
            self.interaction = self.interactions[0]
        elif self.interaction.enabled and not self.interactions:
            # singular is set but list is empty — populate list
            self.interactions = [self.interaction]
        return self
