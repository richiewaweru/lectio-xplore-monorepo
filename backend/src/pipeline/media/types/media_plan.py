from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from pipeline.media.types.visual_slot import VisualSlot


class MediaPlanStatus(str, Enum):
    PLANNED = "planned"
    PARTIAL = "partial"
    COMPLETE = "complete"
    FAILED = "failed"


class MediaPlan(BaseModel):
    section_id: str
    slots: list[VisualSlot] = Field(default_factory=list)
    status: MediaPlanStatus = MediaPlanStatus.PLANNED
    planner_notes: list[str] = Field(default_factory=list)
