from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class VisualFrameStatus(str, Enum):
    PLANNED = "planned"
    GENERATED = "generated"
    FAILED = "failed"


class VisualFrame(BaseModel):
    slot_id: str
    index: int
    label: str | None = None
    generation_goal: str
    must_include: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    output_placeholders: dict[str, str | None] = Field(default_factory=dict)
    status: VisualFrameStatus = VisualFrameStatus.PLANNED
    target_w: int | None = None
    target_h: int | None = None
