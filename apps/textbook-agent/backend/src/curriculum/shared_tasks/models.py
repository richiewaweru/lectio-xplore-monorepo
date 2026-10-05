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
    response: dict[str, Any],
    evaluation: dict[str, Any],
    feedback: dict[str, Any] | None,
    *,
    role: str | None = None,
) -> dict[str, Any] | None:
    """Deterministically tidy per-option feedback for choice tasks.

    Feedback is presentation text, so shape slips must not cost a whole task
    attempt: blank entries are dropped, option keys are matched to declared
    option ids case-insensitively, keys naming no declared option are dropped,
    and text keyed to a correct option moves into ``correct`` (or is dropped
    when ``correct`` already exists, since per-option text is reserved for
    wrong options). The evaluation key itself is never altered.
    """
    if not isinstance(feedback, dict) or response.get("type") not in {
        "single_choice",
        "multiple_choice",
    }:
        return feedback
    declared = [
        str(option.get("id"))
        for option in response.get("options") or ()
        if isinstance(option, dict) and option.get("id") is not None
    ]
    by_lower = {option_id.lower(): option_id for option_id in declared}
    correct: set[str] = set()
    if evaluation.get("correct_option_id") is not None:
        correct.add(str(evaluation["correct_option_id"]))
    for key in evaluation.get("correct_keys") or ():
        correct.add(str(key))

    def _clean_options(entries: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        kept: dict[str, Any] = {}
        moved: list[str] = []
        for key, value in entries.items():
            if not isinstance(value, str) or not value.strip():
                continue
            option_id = by_lower.get(str(key).strip().lower())
            if option_id is None:
                continue
            if option_id in correct:
                moved.append(value)
                continue
            kept[option_id] = value
        return kept, moved

    normalized: dict[str, Any] = {}
    feedback_meta_keys = (
        _FEEDBACK_META_KEYS | {"saved"} if role == "predict" else _FEEDBACK_META_KEYS
    )
    top_level_options: dict[str, Any] = {}
    for key, value in feedback.items():
        if key in feedback_meta_keys:
            if key == "by_option":
                normalized[key] = value
            elif isinstance(value, str) and value.strip():
                normalized[key] = value
        else:
            top_level_options[key] = value
    kept_top, moved = _clean_options(top_level_options)
    normalized.update(kept_top)
    if isinstance(normalized.get("by_option"), dict):
        kept_by_option, moved_by_option = _clean_options(normalized["by_option"])
        moved.extend(moved_by_option)
        if kept_by_option:
            normalized["by_option"] = kept_by_option
        else:
            normalized.pop("by_option")
    if moved and not normalized.get("correct"):
        normalized["correct"] = moved[0]
    if normalized == feedback:
        return feedback
    return normalized or None


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
    role: Literal["predict", "practice", "check"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    display_prompt: str | None = Field(default=None, exclude_if=lambda value: value is None)
    difficulty: Literal["guided", "independent"]
    sourcebook_refs: list[str] = Field(default_factory=list)
    expected_evidence: str = Field(min_length=1)
    response: dict[str, Any]
    evaluation: dict[str, Any]
    feedback: dict[str, Any] | None = None
    option_notes: dict[str, str] | None = Field(default=None, exclude_if=lambda value: value is None)
    approved_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_feedback(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        response, evaluation = data.get("response"), data.get("evaluation")
        if not isinstance(response, dict) or not isinstance(evaluation, dict):
            return data
        normalized = normalize_choice_feedback(
            response, evaluation, data.get("feedback"), role=data.get("role")
        )
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
    role: Literal["predict", "practice", "check"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    display_prompt: str | None = Field(default=None, exclude_if=lambda value: value is None)
    response: dict[str, Any]
    evaluation: dict[str, Any]
    feedback: dict[str, Any] | None = None
    option_notes: dict[str, str] | None = Field(default=None, exclude_if=lambda value: value is None)
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
        normalized = normalize_choice_feedback(
            response, evaluation, data.get("feedback"), role=data.get("role")
        )
        if normalized is data.get("feedback"):
            return data
        return {**data, "feedback": normalized}

