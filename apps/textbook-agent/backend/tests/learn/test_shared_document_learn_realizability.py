"""Every task the shared-task validator accepts must map to a working Learn interaction."""

from __future__ import annotations

import pytest

from curriculum.shared_tasks.models import ACTION_RESPONSE_TYPES, SharedTaskSpec
from curriculum.shared_tasks.validation import (
    ALLOWED_EVALUATION_TYPES,
    validate_final_task_response_contract,
)
from document.shared_lesson.models import TaskAnchor
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    SharedDocumentLearnMappingError,
    _learn_kind_and_config,
    _task_contract,
)
from learn.runtime.evaluation import (
    InteractionResponseError,
    evaluate_interaction,
)
from learn.interactions.contract_validation import validate_interaction_contract

_ACTION_FOR_RESPONSE = {value: key for key, value in reversed(list(ACTION_RESPONSE_TYPES.items()))}

_RESPONSES = {
    "single_choice": {
        "type": "single_choice",
        "options": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}],
    },
    "multiple_choice": {
        "type": "multiple_choice",
        "options": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}],
    },
    "missing_values": {"type": "missing_values", "values": ["alpha", "beta"]},
    "classification": {
        "type": "classification",
        "items": ["x", "y"],
        "categories": ["red", "blue"],
        "correct_placements": {"x": "red", "y": "blue"},
    },
    "matching": {
        "type": "matching",
        "pairs": [{"left": "l1", "right": "r1"}, {"left": "l2", "right": "r2"}],
    },
    "ordered_items": {
        "type": "ordered_items",
        "items": ["one", "two", "three"],
        "correct_order": ["one", "two", "three"],
    },
    "number": {"type": "number"},
    "text": {"type": "text", "min_length": 1},
}

_EXACT_ANSWERS = {
    "missing_values": ["alpha", "beta"],
    "matching": [{"left": "l1", "right": "r1"}, {"left": "l2", "right": "r2"}],
    "ordered_items": ["one", "two", "three"],
    "number": 5,
    "text": "answer",
}


def _evaluation(response_type: str, evaluation_type: str) -> dict:
    response = _RESPONSES[response_type]
    if evaluation_type == "rubric":
        return {"type": "rubric", "criteria": ["Gives a reasoned answer"]}
    if evaluation_type == "numeric":
        return {"type": "numeric", "value": 5, "tolerance": 0.5}
    if evaluation_type == "accepted_answers":
        answers = response.get("values") if response_type == "missing_values" else ["answer"]
        return {"type": "accepted_answers", "accepted_answers": answers}
    if evaluation_type == "teacher_review":
        return {"type": "teacher_review", "review_guidance": "Check the reasoning."}
    if evaluation_type == "mapping":
        if response_type == "classification":
            return {"type": "mapping", "correct_placements": response["correct_placements"]}
        return {"type": "mapping", "pairs": response["pairs"]}
    if evaluation_type == "ordered_match":
        return {"type": "ordered_match", "correct_order": response["correct_order"]}
    if evaluation_type == "choice_keys":
        return {"type": "choice_keys", "correct": ["b"]}
    if evaluation_type == "exact_match":
        if response_type in {"single_choice", "multiple_choice"}:
            return {"type": "exact_match", "correct_option_id": "b"}
        return {"type": "exact_match", "answer": _EXACT_ANSWERS[response_type]}
    raise AssertionError(evaluation_type)


def _task(
    response_type: str,
    evaluation: dict,
    *,
    role: str | None = None,
    response: dict | None = None,
) -> SharedTaskSpec:
    return SharedTaskSpec(
        id="task-1",
        teaching_plan_id="plan-1",
        teaching_plan_revision=1,
        teaching_plan_hash="b" * 64,
        teaching_block_id="block-1",
        mode="formative",
        action=_ACTION_FOR_RESPONSE[response_type],
        purpose="Check understanding",
        prompt="Answer the question.",
        role=role,
        difficulty="guided",
        expected_evidence="A response",
        response=dict(response if response is not None else _RESPONSES[response_type]),
        evaluation=evaluation,
    )


def _contract(task: SharedTaskSpec) -> dict:
    return _task_contract(
        task,
        TaskAnchor(id="anchor-1", task_spec_id=task.id, teaching_block_id=task.teaching_block_id),
        SharedDocumentIdentity(id="doc-1", revision=1, content_hash="c" * 64),
    )


_PAIRS = [
    (response_type, evaluation_type, role)
    for response_type, evaluation_types in ALLOWED_EVALUATION_TYPES.items()
    for evaluation_type in sorted(evaluation_types)
    for role in (None, "predict")
]


@pytest.mark.parametrize(("response_type", "evaluation_type", "role"), _PAIRS)
def test_every_validator_accepted_combination_maps_to_learn(
    response_type: str, evaluation_type: str, role: str | None
) -> None:
    task = _task(response_type, _evaluation(response_type, evaluation_type), role=role)
    if validate_final_task_response_contract(task):
        pytest.skip("validator rejects this minimal task")

    contract = _contract(task)

    assert validate_interaction_contract(contract) == []
    if evaluation_type == "rubric":
        assert contract["config"].get("rubric_criteria") == ["Gives a reasoned answer"]


def test_matrix_covers_every_response_type() -> None:
    assert set(_RESPONSES) == set(ALLOWED_EVALUATION_TYPES)


def test_predict_number_with_rubric_maps_to_answer_free_numeric_and_saves_ungraded() -> None:
    task = _task(
        "number",
        {"type": "rubric", "criteria": "Any reasoned estimate is fine."},
        role="predict",
        response={"type": "number", "unit": "m", "min": 0},
    )
    assert validate_final_task_response_contract(task) == []

    contract = _contract(task)

    assert contract["kind"] == "numeric"
    assert "value" not in contract["config"]
    assert contract["config"]["rubric_criteria"] == "Any reasoned estimate is fine."
    assert contract["role"] == "predict"
    assert validate_interaction_contract(contract) == []

    result = evaluate_interaction(contract, {"value": 12})
    assert result.outcome == "pending-review"
    assert result.score_earned == 0.0
    assert result.score_possible == 0.0
    assert result.feedback == "Prediction saved."

    with pytest.raises(InteractionResponseError):
        evaluate_interaction(contract, {"value": "abc"})
    with pytest.raises(InteractionResponseError):
        evaluate_interaction(contract, {})


def test_non_predict_number_with_rubric_becomes_teacher_review_short_response() -> None:
    task = _task("number", {"type": "rubric", "criteria": ["Shows working", "Uses units"]})

    kind, config = _learn_kind_and_config(task)

    assert kind == "short-response"
    assert config["evaluation"] == "teacher-review"
    assert config["rubric_criteria"] == ["Shows working", "Uses units"]
    assert "Shows working" in config["review_guidance"]
    contract = _contract(task)
    assert contract["kind"] == "short-response"
    result = evaluate_interaction(contract, {"text": "about 5 m"})
    assert result.outcome == "pending-review"


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("5", 5), ("2.5", 2.5), (" 7 ", 7), (3, 3), (1.5, 1.5)],
)
def test_number_exact_match_coerces_numeric_strings(answer, expected) -> None:
    task = _task("number", {"type": "exact_match", "answer": answer})

    kind, config = _learn_kind_and_config(task)

    assert kind == "numeric"
    assert config["value"] == expected
    assert type(config["value"]) is type(expected)


@pytest.mark.parametrize("answer", ["five", "nan", "inf", "1e999"])
def test_number_exact_match_rejects_non_numeric_strings(answer: str) -> None:
    task = _task("number", {"type": "exact_match", "answer": answer})

    with pytest.raises(SharedDocumentLearnMappingError):
        _learn_kind_and_config(task)


@pytest.mark.parametrize(("answer", "expected"), [(42, ["42"]), (2.5, ["2.5"]), ("word", ["word"])])
def test_text_exact_match_coerces_numbers_to_accepted_answers(answer, expected) -> None:
    task = _task("text", {"type": "exact_match", "answer": answer})

    kind, config = _learn_kind_and_config(task)

    assert kind == "short-response"
    assert config["evaluation"] == "accepted-answers"
    assert config["accepted_answers"] == expected


def test_structured_rubric_keeps_answer_structure_and_still_fails_closed() -> None:
    task = _task("classification", {"type": "rubric", "criteria": ["Sorted sensibly"]})
    kind, config = _learn_kind_and_config(task)
    assert kind == "classify"
    assert config["pairs"] == [
        {"left": "x", "right": "red"},
        {"left": "y", "right": "blue"},
    ]

    broken = dict(_RESPONSES["classification"], correct_placements={"x": "red"})
    with pytest.raises(SharedDocumentLearnMappingError):
        _learn_kind_and_config(_task("classification", {"type": "rubric", "criteria": "c"}, response=broken))
