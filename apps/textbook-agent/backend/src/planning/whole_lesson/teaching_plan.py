"""Whole-lesson teaching plan schema (proposal §7.1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TeachingPlanBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    position: int = Field(ge=0)
    intent: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    evidence: str = Field(min_length=1)
    departure_reason: str | None = None
    source_question_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Approved assessment-item ownership. Leave empty for a non-assessment "
            "block. A multiple-choice source must be the only ID in this array."
        ),
    )

    @model_validator(mode="after")
    def _normalize_departure(self) -> TeachingPlanBlock:
        if self.departure_reason is not None and not self.departure_reason.strip():
            self.departure_reason = None
        return self


class TeachingPlanSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    specific_purpose: str = ""
    transition: str | None = None
    blocks: list[TeachingPlanBlock] = Field(default_factory=list)


class AnchorUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orient: str = ""
    explain: str = ""
    # The active conceptual first-exposure skeleton may use a contrast slot.
    contrast: str = ""
    confront: str = ""
    check: str = ""


class TeachingPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    anchor_usage: AnchorUsage
    misconception_focus_ids: list[str] = Field(default_factory=list)
    sections: list[TeachingPlanSection] = Field(default_factory=list)
