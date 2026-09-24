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

TaskEvaluationType = Literal[
    "rubric",
    "exact_match",
    "choice_keys",
    "numeric",
    "accepted_answers",
    "teacher_review",
    "mapping",
    "ordered_match",
]

TASK_RESPONSE_FIELDS: dict[TaskResponseType, frozenset[str]] = {
    "single_choice": frozenset({"type", "options", "answer_lines"}),
    "multiple_choice": frozenset({"type", "options", "answer_lines"}),
    "number": frozenset({"type", "unit", "min", "max", "step", "precision", "answer_lines"}),
    "text": frozenset({"type", "min_length", "max_length", "placeholder", "answer_lines"}),
    "missing_values": frozenset({"type", "values", "answers", "answer_lines"}),
    "classification": frozenset({"type", "items", "categories", "correct_placements"}),
    "matching": frozenset({"type", "pairs"}),
    "ordered_items": frozenset({"type", "items", "correct_order", "order"}),
}

TASK_EVALUATION_FIELDS: dict[str, frozenset[str]] = {
    "rubric": frozenset({"type", "criteria", "rubric"}),
    "exact_match": frozenset({
        "type", "answer", "correct_value", "correct_option_id", "correct_key",
        "correct_option_ids", "correct_keys",
    }),
    "choice_keys": frozenset({
        "type", "correct", "correct_keys", "correct_option_ids", "correct_option_id",
    }),
    "numeric": frozenset({"type", "value", "tolerance", "unit"}),
    "accepted_answers": frozenset({"type", "accepted_answers", "case_sensitive"}),
    "teacher_review": frozenset({"type", "review_guidance"}),
    "mapping": frozenset({"type", "correct_placements", "pairs", "correct_pairs"}),
    "ordered_match": frozenset({"type", "correct_order", "order"}),
}

ACTION_RESPONSE_TYPES: dict[LearnerActionId, TaskResponseType] = {
    "select-one": "single_choice",
    "select-many": "multiple_choice",
    "complete-missing-values": "missing_values",
    "classify-items": "classification",
    "match-pairs": "matching",
    "order-items": "ordered_items",
    "reconstruct-order": "ordered_items",
    "enter-number": "number",
    "enter-text": "text",
}

PASSIVE_ACTION_MEANINGS: dict[LearnerActionId, str] = {
    "compare-without-response": "Compare the presented ideas without submitting an answer.",
    "read-explanation": "Read the explanation without submitting an answer.",
}


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
