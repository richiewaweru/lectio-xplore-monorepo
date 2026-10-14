from __future__ import annotations

import pytest

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.shared_tasks.ordering import derange_for_display, scramble_for_display
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


def _match_task(task_id: str, rights: list[str]) -> SharedTaskSpec:
    pairs = [{"left": f"L{i}", "right": right} for i, right in enumerate(rights)]
    return _task(
        task_id,
        "match-pairs",
        {"type": "matching", "pairs": pairs},
        {"type": "mapping", "pairs": pairs},
    )


def test_learn_fill_blank_carries_blank_count() -> None:
    task = _task(
        "t-blanks",
        "complete-missing-values",
        {"type": "missing_values", "values": ["Paris", "Lyon"]},
        {"type": "accepted_answers", "accepted_answers": ["Paris", "Lyon"]},
    )
    assert _learn_config(task, "fill-blank")["blank_count"] == 2


def _plain(value) -> str:
    if isinstance(value, list):
        return "".join(run.get("value", "") for run in value)
    return str(value)


@pytest.mark.parametrize("size", range(2, 9))
def test_derange_has_no_fixed_points_and_is_deterministic(size: int) -> None:
    items = [f"item-{i}" for i in range(size)]
    for i in range(40):
        shown = derange_for_display(f"task-{i}", items)
        assert sorted(shown) == sorted(items)
        assert all(shown[j] != items[j] for j in range(size))
        assert shown == derange_for_display(f"task-{i}", items)


def test_derange_small_inputs_unchanged() -> None:
    assert derange_for_display("x", []) == []
    assert derange_for_display("x", ["only"]) == ["only"]


def test_derange_duplicates_do_not_crash() -> None:
    assert sorted(derange_for_display("dup", ["a", "a", "b"])) == ["a", "a", "b"]


@pytest.mark.parametrize("size", [2, 3, 4, 5])
def test_learn_right_items_match_print_right_column(size: int) -> None:
    rights = [f"right-{i}" for i in range(size)]
    task = _match_task(f"t-match-{size}", rights)
    config = _learn_config(task, "match-pairs")
    assert config["left_items"] == [f"L{i}" for i in range(size)]
    assert all(config["right_items"][i] != rights[i] for i in range(size))
    item, entry = _question_task(task)
    shown = [_plain(cell) for cell in item["match"]["right"]]
    assert shown == config["right_items"]
    answer = _plain(entry["answer"])
    for index, right in enumerate(rights):
        assert f"{index + 1} (L{index}) → {chr(65 + shown.index(right))} ({right})" in answer


def _sentence_task() -> SharedTaskSpec:
    return _task(
        "t-sentence",
        "complete-missing-values",
        {
            "type": "missing_values",
            "values": ["chlorophyll", "stomata"],
            "sentence": "Leaves absorb light with [1] and breathe through [2].",
        },
        {"type": "accepted_answers", "accepted_answers": ["chlorophyll", "stomata"]},
    )


def test_learn_fill_blank_passes_sentence_through() -> None:
    config = _learn_config(_sentence_task(), "fill-blank")
    assert config["sentence"] == "Leaves absorb light with [1] and breathe through [2]."
    assert config["blank_count"] == 2
    plain = _task(
        "t-plain",
        "complete-missing-values",
        {"type": "missing_values", "values": ["a"]},
        {"type": "accepted_answers", "accepted_answers": ["a"]},
    )
    assert "sentence" not in _learn_config(plain, "fill-blank")


def test_print_fill_blank_sentence_shows_gaps_and_labels_answers() -> None:
    item, entry = _question_task(_sentence_task())
    text = _plain(item["prompt"])
    assert text.startswith("Do the task.\n")
    assert "(1) ________" in text and "(2) ________" in text
    assert "[1]" not in text and "chlorophyll" not in text and "stomata" not in text
    assert entry["answer"] == "(1) chlorophyll; (2) stomata"
