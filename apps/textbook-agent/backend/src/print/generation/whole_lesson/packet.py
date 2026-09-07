"""Immutable lesson packet — fixed inputs for whole-lesson planners."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScopeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str


class LessonIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_lesson_id: str
    subject: str
    grade_level: str
    objective: str
    knowledge_type: str
    lesson_mode: str


class ScopeContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_establish: list[ScopeEntry] = Field(default_factory=list)
    must_not_introduce: list[ScopeEntry] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)


class AnchorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str


class MisconceptionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str


class PriorEstablishedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str


class SlotRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    purpose: str = ""
    typical_intents: list[str] = Field(default_factory=list)
    min_blocks: int = 1
    max_blocks: int = 3
    visual_required: bool = Field(
        default=False,
        description="Authoritative structural requirement for a visual in this slot.",
    )


class ApprovedItemRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    card_id: str
    stem: str
    options: list[dict[str, Any]] = Field(default_factory=list)
    correct_key: str = ""
    diagnoses: dict[str, Any] = Field(default_factory=dict)


class LessonLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_sections: int = 4
    max_blocks_per_section: int = 3
    max_total_blocks: int = 10


class ImmutableLessonPacket(BaseModel):
    """Planner may consume this packet. It may not change fixed fields."""

    model_config = ConfigDict(extra="forbid")

    lesson: LessonIdentity
    scope: ScopeContract
    anchor: AnchorRecord
    misconceptions: list[MisconceptionRecord] = Field(default_factory=list)
    prior_established: list[PriorEstablishedEntry] = Field(default_factory=list)
    approved_items: list[ApprovedItemRef] = Field(default_factory=list)
    slots: list[SlotRecord] = Field(default_factory=list)
    limits: LessonLimits = Field(default_factory=LessonLimits)
    resource_id: str = "lesson"

    def approved_item_ids(self) -> list[str]:
        return [item.id for item in self.approved_items]

    def required_visual_slots(self) -> tuple[str, ...]:
        return tuple(slot.slot_id for slot in self.slots if slot.visual_required)

    def planner_payload(self) -> dict[str, Any]:
        """Subset visible to the teaching planner (IDs, not invented content)."""
        return {
            "lesson": self.lesson.model_dump(mode="json"),
            "scope": self.scope.model_dump(mode="json"),
            "anchor": self.anchor.model_dump(mode="json"),
            "misconceptions": [m.model_dump(mode="json") for m in self.misconceptions],
            "prior_established": [p.model_dump(mode="json") for p in self.prior_established],
            "slots": [s.model_dump(mode="json") for s in self.slots],
            "required_visual_slots": list(self.required_visual_slots()),
            "approved_item_ids": self.approved_item_ids(),
            "limits": self.limits.model_dump(mode="json"),
        }
