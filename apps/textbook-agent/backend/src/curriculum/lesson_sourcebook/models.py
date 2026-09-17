from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SourcebookEntryType = Literal[
    "definition",
    "quantitative_example",
    "worked_example_data",
    "scenario",
    "comparison_case",
    "fact_set",
    "sequence",
    "misconception_resolution",
    "stimulus",
]


class SourcebookEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: SourcebookEntryType
    purpose: str = Field(min_length=1)
    content: dict[str, Any]
    provenance_refs: list[str] = Field(default_factory=list)


class SourcebookEntryDraft(BaseModel):
    """Provider-owned content; entry identity is assigned by code."""

    model_config = ConfigDict(extra="forbid")

    type: SourcebookEntryType
    purpose: str = Field(min_length=1)
    content: dict[str, Any]
    provenance_refs: list[str] = Field(default_factory=list)


class LessonSourcebookDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[SourcebookEntryDraft] = Field(default_factory=list)


class LessonSourcebook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teaching_plan_id: str = Field(min_length=1)
    teaching_plan_revision: int = Field(ge=1)
    teaching_plan_hash: str = ""
    entries: list[SourcebookEntry] = Field(default_factory=list)

    def by_id(self) -> dict[str, SourcebookEntry]:
        return {entry.id: entry for entry in self.entries}


class TeachingContentBinding(BaseModel):
    """Post-plan bindings that keep the approved Teaching Plan immutable."""

    model_config = ConfigDict(extra="forbid")

    teaching_plan_id: str = Field(min_length=1)
    teaching_plan_revision: int = Field(ge=1)
    teaching_plan_hash: str = Field(min_length=1)
    teaching_block_id: str = Field(min_length=1)
    sourcebook_refs: list[str] = Field(default_factory=list)
    shared_task_id: str | None = None
