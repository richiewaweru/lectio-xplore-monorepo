from __future__ import annotations

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.shared_tasks.validation import validate_final_task_response_contract


def _choice_task(
    *,
    action: str = "select-many",
    response_type: str = "multiple_choice",
    options: list[dict] | None = None,
    correct_keys: list[str] | None = None,
    feedback: dict | None = None,
) -> SharedTaskSpec:
    options = options or [
        {"id": "a", "text": "A"},
        {"id": "b", "text": "B"},
        {"id": "c", "text": "C"},
        {"id": "d", "text": "D"},
    ]
    correct_keys = correct_keys if correct_keys is not None else ["a"]
    return SharedTaskSpec(
        id="task-check-b1",
        teaching_block_id="check-b1",
        mode="formative",
        action=action,
        purpose="measure understanding",
        prompt="Pick the correct option(s).",
        difficulty="independent",
        expected_evidence="the learner selects the correct option(s)",
        response={"type": response_type, "options": options},
        evaluation={"type": "choice_keys", "correct_keys": correct_keys},
        feedback=feedback,
    )


def _classification_task(
    *,
    items: list[str] | None = None,
    feedback: dict | None = None,
) -> SharedTaskSpec:
    items = items or ["glucose", "oxygen", "CO2", "ATP"]
    placements = {item: ("reactant" if item in {"glucose", "oxygen"} else "product") for item in items}
    return SharedTaskSpec(
        id="task-guided-b2",
        teaching_block_id="guided-b2",
        mode="formative",
        action="classify-items",
        purpose="classify substances",
        prompt="Classify each substance.",
        difficulty="guided",
        expected_evidence="each item is placed correctly",
        response={
            "type": "classification",
            "items": items,
            "categories": ["reactant", "product"],
            "correct_placements": placements,
        },
        evaluation={"type": "mapping", "correct_placements": placements},
        feedback=feedback,
    )


def test_live_defect_shape_is_rejected_with_correct_and_missing_option_codes() -> None:
    # Reproduces the live shared_tasks defect: the correct option's key ("a")
    # carries wrong-answer feedback text, and wrong option "b" has none.
    task = _choice_task(
        correct_keys=["a"],
        feedback={
            "a": "Carbon dioxide is released and ATP is produced, so neither belongs on the reactant side.",
            "c": "ATP is produced by cellular respiration, not taken in, so it does not belong on the reactant side.",
            "d": "Carbon dioxide, water, and ATP are all products released by the reaction.",
            "correct": "Glucose and oxygen are the substances taken in and used up.",
        },
    )

    errors = validate_final_task_response_contract(task)

    assert any("feedback_on_correct_option" in error and "'a'" in error for error in errors)
    assert any("feedback_missing_wrong_option" in error and "'b'" in error for error in errors)


def test_correct_by_option_shape_passes() -> None:
    task = _choice_task(
        correct_keys=["a"],
        feedback={
            "correct": "Glucose and oxygen are taken in and used up, so they are reactants.",
            "by_option": {
                "b": "Carbon dioxide is a product, not a reactant.",
                "c": "ATP is a product, not a reactant.",
                "d": "Water is a product, not a reactant.",
            },
        },
    )

    assert validate_final_task_response_contract(task) == []


def test_missing_wrong_option_is_rejected() -> None:
    task = _choice_task(
        correct_keys=["a"],
        feedback={
            "correct": "Glucose and oxygen are taken in and used up, so they are reactants.",
            "by_option": {
                "b": "Carbon dioxide is a product, not a reactant.",
                "c": "ATP is a product, not a reactant.",
                # "d" is missing.
            },
        },
    )

    errors = validate_final_task_response_contract(task)

    assert any("feedback_missing_wrong_option" in error and "'d'" in error for error in errors)


def test_unknown_option_is_rejected() -> None:
    task = _choice_task(
        correct_keys=["a"],
        feedback={
            "correct": "Glucose and oxygen are taken in and used up, so they are reactants.",
            "by_option": {
                "b": "Carbon dioxide is a product, not a reactant.",
                "c": "ATP is a product, not a reactant.",
                "d": "Water is a product, not a reactant.",
                "z": "This option id does not exist.",
            },
        },
    )

    errors = validate_final_task_response_contract(task)

    assert any("feedback_unknown_option" in error and "'z'" in error for error in errors)


def test_blank_feedback_text_is_rejected() -> None:
    task = _choice_task(
        correct_keys=["a"],
        feedback={
            "correct": "   ",
            "by_option": {
                "b": "Carbon dioxide is a product, not a reactant.",
                "c": "ATP is a product, not a reactant.",
                "d": "Water is a product, not a reactant.",
            },
        },
    )

    errors = validate_final_task_response_contract(task)

    assert any("feedback_blank" in error and "correct" in error for error in errors)


def test_classification_common_errors_must_reference_real_items() -> None:
    task = _classification_task(
        feedback={
            "rule": "Reactants are taken in and used up; products come out.",
            "common_errors": {
                "ATP": "ATP is produced by the reaction, so it is a product.",
                "not-a-real-item": "This item does not exist.",
            },
        },
    )

    errors = validate_final_task_response_contract(task)

    assert any("feedback_unknown_item" in error and "not-a-real-item" in error for error in errors)


def test_classification_feedback_with_only_real_items_passes() -> None:
    task = _classification_task(
        feedback={
            "rule": "Reactants are taken in and used up; products come out.",
            "common_errors": {
                "ATP": "ATP is produced by the reaction, so it is a product.",
                "CO2": "CO2 is released by the reaction, so it is a product.",
            },
        },
    )

    assert validate_final_task_response_contract(task) == []


def test_teacher_review_null_feedback_passes() -> None:
    task = SharedTaskSpec(
        id="task-apply-b1",
        teaching_block_id="apply-b1",
        mode="formative",
        action="enter-text",
        purpose="apply the rule",
        prompt="Explain your reasoning.",
        difficulty="independent",
        expected_evidence="a stated gain and a classification",
        response={"type": "text"},
        evaluation={"type": "teacher_review", "review_guidance": "Look for a stated gain."},
        feedback=None,
    )

    assert validate_final_task_response_contract(task) == []


def test_single_choice_feedback_uses_the_same_contract() -> None:
    task = _choice_task(
        action="select-one",
        response_type="single_choice",
        options=[
            {"id": "a", "text": "A"},
            {"id": "b", "text": "B"},
            {"id": "c", "text": "C"},
        ],
        correct_keys=["a"],
        feedback={
            "a": "This is the correct option, so it must not carry wrong-answer feedback.",
            "b": "B is wrong.",
            "c": "C is wrong.",
        },
    )

    errors = validate_final_task_response_contract(task)

    assert any("feedback_on_correct_option" in error and "'a'" in error for error in errors)


def test_null_feedback_entries_are_treated_as_omitted():
    from curriculum.shared_tasks.validation import _present_feedback

    assert _present_feedback({"correct": "Yes.", "incorrect": None}) == {"correct": "Yes."}
    assert _present_feedback(None) == {}


def test_partial_is_a_feedback_meta_key_not_an_option():
    from curriculum.shared_tasks.validation import _FEEDBACK_META_KEYS

    assert "partial" in _FEEDBACK_META_KEYS
