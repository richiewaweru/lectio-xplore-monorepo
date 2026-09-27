from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


_FEEDBACK_META_KEYS = frozenset({"correct", "incorrect", "partial", "by_option"})


def normalize_choice_feedback(
    response: dict[str, Any], evaluation: dict[str, Any], feedback: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Deterministically move per-option feedback keyed to a correct option.

    Providers repeatedly attach explanation text to the correct option's key.
    Per-option feedback is reserved for wrong options, so that text belongs in
    ``correct`` (kept if ``correct`` is absent, otherwise dropped). Feedback on
    unknown or wrong options is left untouched for validation to judge.
    """
    if not isinstance(feedback, dict) or response.get("type") not in {
        "single_choice",
        "multiple_choice",
    }:
        return feedback
    correct: set[str] = set()
    if evaluation.get("correct_option_id") is not None:
        correct.add(str(evaluation["correct_option_id"]))
    for key in evaluation.get("correct_keys") or ():
        correct.add(str(key))
    if not correct:
        return feedback
    if not any(key in feedback for key in correct) and not (
        isinstance(feedback.get("by_option"), dict)
        and any(key in feedback["by_option"] for key in correct)
    ):
        return feedback
    normalized = dict(feedback)
    moved: list[str] = []
    for key in sorted(correct):
        if key in normalized and key not in _FEEDBACK_META_KEYS:
            value = normalized.pop(key)
            if isinstance(value, str) and value.strip():
                moved.append(value)
    by_option = normalized.get("by_option")
    if isinstance(by_option, dict):
        by_option = dict(by_option)
        for key in sorted(correct):
            if key in by_option:
                value = by_option.pop(key)
                if isinstance(value, str) and value.strip():
                    moved.append(value)
        normalized["by_option"] = by_option
    if moved and not (isinstance(normalized.get("correct"), str) and normalized["correct"].strip()):
        normalized["correct"] = moved[0]
    return normalized


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

    @model_validator(mode="before")
    @classmethod
    def _normalize_feedback(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        response, evaluation = data.get("response"), data.get("evaluation")
        if not isinstance(response, dict) or not isinstance(evaluation, dict):
            return data
        normalized = normalize_choice_feedback(response, evaluation, data.get("feedback"))
        if normalized is data.get("feedback"):
            return data
        return {**data, "feedback": normalized}

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

    @model_validator(mode="before")
    @classmethod
    def _normalize_feedback(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        response, evaluation = data.get("response"), data.get("evaluation")
        if not isinstance(response, dict) or not isinstance(evaluation, dict):
            return data
        normalized = normalize_choice_feedback(response, evaluation, data.get("feedback"))
        if normalized is data.get("feedback"):
            return data
        return {**data, "feedback": normalized}

