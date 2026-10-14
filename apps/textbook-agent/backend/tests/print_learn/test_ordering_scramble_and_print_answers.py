from __future__ import annotations

import pytest

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.shared_tasks.ordering import scramble_for_display
from document.shared_lesson.models import TaskAnchor
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    _learn_config,
    _task_contract,
)
from learn.interactions.contract_validation import validate_interaction_contract
from learn.runtime.evaluation import evaluate_sequence
from print.generation.shared_document_adapter import _question_task


def _task(task_id: str, action: str, response: dict, evaluation: dict) -> SharedTaskSpec:
    return SharedTaskSpec(
        id=task_id,
        teaching_plan_id="plan-1",
        teaching_plan_revision=1,
        teaching_plan_hash="b" * 64,
        teaching_block_id="block-1",
        mode="formative",
        action=action,
        purpose="Check understanding",
        prompt="Do the task.",
        difficulty="guided",
        expected_evidence="A response",
        response=response,
        evaluation=evaluation,
    )


def _order_task(task_id: str = "t-order", order=("egg", "larva", "pupa", "adult"), evaluation=None) -> SharedTaskSpec:
    order = list(order)
    return _task(
        task_id,
        "order-items",
        {"type": "ordered_items", "items": list(order), "correct_order": list(order)},
        evaluation or {"type": "ordered_match", "correct_order": list(order)},
    )


@pytest.mark.parametrize("order", [["a", "b"], ["a", "b", "c"], ["egg", "larva", "pupa", "adult"]])
def test_scramble_never_equals_order_and_is_stable(order: list[str]) -> None:
    for i in range(40):
        shown = scramble_for_display(f"task-{i}", order, order)
        assert shown != order
        assert sorted(shown) == sorted(order)
        assert shown == scramble_for_display(f"task-{i}", order, order)


def test_scramble_single_item_unchanged() -> None:
    assert scramble_for_display("x", ["only"], ["only"]) == ["only"]


@pytest.mark.parametrize("order", [["a", "b"], ["egg", "larva", "pupa", "adult"]])
def test_learn_sequence_items_scrambled_and_still_valid(order: list[str]) -> None:
    task = _order_task(order=order)
    config = _learn_config(task, "sequence")
    assert config["order"] == order
    assert config["items"] != order
    assert sorted(config["items"]) == sorted(order)
    assert config == _learn_config(task, "sequence")
    contract = _task_contract(
        task,
        TaskAnchor(id="anchor-1", task_spec_id=task.id, teaching_block_id=task.teaching_block_id),
        SharedDocumentIdentity(id="doc-1", revision=1, content_hash="c" * 64),
    )
    assert validate_interaction_contract(contract) == []
    assert contract["config"]["items"] == config["items"]
    result = evaluate_sequence(config, {"order": order}, {})
    assert result.score_earned == len(order)


def test_print_ordering_scrambled_with_rubric_and_answer_key() -> None:
    order = ["egg", "larva", "pupa", "adult"]
    task = _order_task(evaluation={"type": "rubric", "criteria": ["Correct life-cycle order"]})
    item, entry = _question_task(task)
    shown = item["prompt"]
    text = "".join(run.get("value", "") for run in shown) if isinstance(shown, list) else str(shown)
    listed = text.split("Put these in order: ")[1].split("; ")
    assert listed != order and sorted(listed) == sorted(order)
    assert entry["answer"] == " → ".join(order)


def test_print_fill_blank_does_not_leak_answers_to_students() -> None:
    task = _task(
        "t-fill",
        "complete-missing-values",
        {"type": "missing_values", "values": ["Paris", "Lyon"]},
        {"type": "accepted_answers", "accepted_answers": ["Paris", "Lyon"]},
    )
    item, entry = _question_task(task)
    text = "".join(r.get("value", "") for r in item["prompt"])
    assert "Paris" not in text and "Lyon" not in text
    assert "Paris" in entry["answer"] and "Lyon" in entry["answer"]
