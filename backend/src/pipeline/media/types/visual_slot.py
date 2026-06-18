from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from pipeline.media.types.visual_frame import VisualFrame


class SlotType(str, Enum):
    DIAGRAM = "diagram"
    DIAGRAM_COMPARE = "diagram_compare"
    DIAGRAM_SERIES = "diagram_series"
    SIMULATION = "simulation"


class VisualRender(str, Enum):
    IMAGE = "image"
    SVG = "svg"
    HTML_SIMULATION = "html_simulation"


class ReferenceStyle(str, Enum):
    STANDARD = "standard"
    CONSISTENT_SEQUENCE = "consistent_sequence"
    LOCKED_COMPARISON = "locked_comparison"
    INTERACTIVE = "interactive"


class VisualSlotStatus(str, Enum):
    PLANNED = "planned"
    GENERATED = "generated"
    FAILED = "failed"


class VisualSlot(BaseModel):
    slot_id: str
    slot_type: SlotType
    required: bool = False
    preferred_render: VisualRender
    fallback_render: VisualRender | None = None
    sizing: Literal["full", "compact"] = "full"
    block_target: Literal["hook", "explanation", "practice", "worked_example"] | None = None
    problem_index: int | None = None
    content_brief: str | None = None
    generation_prompt: str | None = None
    pedagogical_intent: str
    caption: str
    reference_style: ReferenceStyle = ReferenceStyle.STANDARD
    frames: list[VisualFrame] = Field(default_factory=list)
    series_context: str | None = None
    simulation_intent: str | None = None
    simulation_type: str | None = None
    simulation_goal: str | None = None
    anchor_block: str | None = None
    print_translation: Literal["static_midstate", "static_diagram", "hide"] | None = None
    expects_static_fallback: bool = False
    status: VisualSlotStatus = VisualSlotStatus.PLANNED
