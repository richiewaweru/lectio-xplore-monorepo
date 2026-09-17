from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from curriculum.teaching_plan.models import LearnerActionId

TaskResponseType = Literal[
    "single_choice",
    "multiple_choice",
    "number",
    "text",
    "missing_values",
    "classification",
    "matching",
    "ordered_items",
]


class SharedTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    teaching_plan_id: str = ""
    teaching_plan_revision: int = Field(default=1, ge=1)
    teaching_plan_hash: str = ""
    teaching_block_id: str = Field(min_length=1)
    mode: Literal["formative", "assessment"]
    action: LearnerActionId
    purpose: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    difficulty: Literal["guided", "independent"]
    sourcebook_refs: list[str] = Field(default_factory=list)
    expected_evidence: str = Field(min_length=1)
    response: dict[str, Any]
    evaluation: dict[str, Any]
    feedback: dict[str, Any] | None = None
    approved_source_ids: list[str] = Field(default_factory=list)

    @property
    def response_type(self) -> str | None:
        value = self.response.get("type")
        return str(value) if value is not None else None


class SharedTaskDraft(BaseModel):
    """Provider-owned task semantics; identity and ownership are code-owned."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    response: dict[str, Any]
    evaluation: dict[str, Any]
    feedback: dict[str, Any] | None = None
    expected_evidence: str = Field(min_length=1)
    difficulty: Literal["guided", "independent"]
