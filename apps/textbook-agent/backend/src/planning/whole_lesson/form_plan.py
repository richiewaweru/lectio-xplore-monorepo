"""Whole-lesson form plan schema — assigns one object per teaching block."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Placement = Literal["main", "margin", "spanning"]


class FormPlanBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    position: int = Field(ge=0)
    intent: str
    brief: str
    evidence: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    departure_reason: str | None = None
    source_question_ids: list[str] = Field(default_factory=list)
    object: str
    placement: Placement = "main"
    reason: str = ""


class FormPlanSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    title: str = ""
    blocks: list[FormPlanBlock] = Field(default_factory=list)


class FormPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[FormPlanSection] = Field(default_factory=list)
