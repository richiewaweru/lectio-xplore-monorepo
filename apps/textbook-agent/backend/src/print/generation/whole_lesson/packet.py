"""Immutable lesson packet — fixed inputs for whole-lesson planners."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


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
    risk: str = "high"


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

    @model_validator(mode="before")
    @classmethod
    def _ignore_retired_visual_required(cls, data: Any) -> Any:
        # Packets persisted before the flag was retired may still carry it.
        if isinstance(data, dict) and "visual_required" in data:
            return {key: value for key, value in data.items() if key != "visual_required"}
        return data


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
    # Structural question planning owns where approved assessment items may be
    # consumed. Keeping this in the immutable packet prevents the Teaching LLM
    # from moving a cold check into guided practice simply because it sees an item.
    required_assessment_slots: list[str] = Field(default_factory=list)
    limits: LessonLimits = Field(default_factory=LessonLimits)
    resource_id: str = "lesson"
    # Lesson backbone (LessonBackbone.model_dump) the approved questions were written
    # against, and approved item id -> {target, figure_id}. Both are omitted from
    # serialization when empty so packets (and any hash over them) stay byte-stable.
    backbone: dict[str, Any] | None = None
    item_backbone_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _omit_empty_backbone(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        if not data.get("backbone"):
            data.pop("backbone", None)
        if not data.get("item_backbone_refs"):
            data.pop("item_backbone_refs", None)
        return data

    def approved_item_ids(self) -> list[str]:
        return [item.id for item in self.approved_items]

    def planner_payload(self) -> dict[str, Any]:
        """Subset visible to the teaching planner (fixed identities only)."""
        payload: dict[str, Any] = {
            "lesson": self.lesson.model_dump(mode="json"),
            "scope": self.scope.model_dump(mode="json"),
            "anchor": self.anchor.model_dump(mode="json"),
            "misconceptions": [m.model_dump(mode="json") for m in self.misconceptions],
            "prior_established": [p.model_dump(mode="json") for p in self.prior_established],
            "slots": [s.model_dump(mode="json") for s in self.slots],
            "required_assessment_slots": list(self.required_assessment_slots),
            "approved_item_ids": self.approved_item_ids(),
            "limits": self.limits.model_dump(mode="json"),
        }
        if self.backbone:
            payload["backbone"] = dict(self.backbone)
            if self.item_backbone_refs:
                payload["item_backbone_refs"] = {
                    key: dict(value) for key, value in self.item_backbone_refs.items()
                }
        return payload
