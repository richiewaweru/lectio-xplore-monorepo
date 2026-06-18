from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

from pipeline.media.types.visual_slot import SlotType, VisualRender
from pipeline.types.section_content import InteractionSpec


class VisualFrameResultStatus(str, Enum):
    PENDING = "pending"
    GENERATED = "generated"
    FAILED = "failed"


class VisualFrameResult(BaseModel):
    slot_id: str
    frame_index: int
    label: str | None = None
    render: VisualRender | None = None
    status: VisualFrameResultStatus = VisualFrameResultStatus.PENDING
    svg_content: str | None = None
    image_url: str | None = None
    html_content: str | None = None
    diagram_spec: dict[str, Any] | None = None
    interaction_spec: InteractionSpec | None = None
    alt_text: str | None = None
    explanation: str | None = None
    error_message: str | None = None


class VisualSlotResultStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    GENERATED = "generated"
    FAILED = "failed"


class VisualSlotResult(BaseModel):
    slot_id: str
    slot_type: SlotType
    required: bool
    render: VisualRender | None = None
    caption: str
    status: VisualSlotResultStatus = VisualSlotResultStatus.PENDING
    ready: bool = False
    completed_frames: int = 0
    total_frames: int = 0
    error_message: str | None = None
