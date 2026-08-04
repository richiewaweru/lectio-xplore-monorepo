from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

# Prefer generated literal aliases from the synced Lectio contracts.
PageObjectId = Literal[
    "prose", "list", "table", "figure", "worked-example", "questions",
    "aside", "choices", "heading", "answer-key",
]
Placement = Literal["main", "margin", "spanning"]


class PlannedBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    position: int = Field(ge=0)
    intent: str = Field(min_length=1)
    object: PageObjectId
    evidence: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    role: str | None = None
    placement: Placement = "main"
    source_question_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def first_slice_rules(self) -> "PlannedBlock":
        if self.object == "heading":
            raise ValueError("section.title owns the generated section heading")
        if self.object == "questions" and not self.source_question_ids:
            raise ValueError("questions block requires source_question_ids")
        if self.object != "questions" and self.source_question_ids:
            raise ValueError("source_question_ids belong only to questions blocks")
        return self


class SectionBlockPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocks: list[PlannedBlock] = Field(default_factory=list)
    slot_concern: str | None = None

    @model_validator(mode="after")
    def result_is_exclusive_and_ordered(self) -> "SectionBlockPlan":
        if self.slot_concern:
            if self.blocks:
                raise ValueError("slot_concern requires an empty block list")
            return self
        if not self.blocks:
            raise ValueError("successful section plan requires blocks")
        for index, block in enumerate(self.blocks):
            if block.position != index:
                raise ValueError("position must equal array index")
        return self

# Additive target for existing SectionPlan:
#
# components: list[ComponentSlot] = Field(default_factory=list)  # legacy v1
# blocks: list[PlannedBlock] = Field(default_factory=list)       # native v2
#
# Add a top-level discriminator to StructuralPlan or its persisted envelope:
# document_contract_version: Literal[1, 2] = 1
