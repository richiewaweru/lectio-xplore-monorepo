from __future__ import annotations

import pytest

from learn.runtime.evaluation import InteractionResponseError, contract_from_v2_node, evaluate_interaction


def _contract() -> dict[str, object]:
    return {
        "id": "interaction-predict",
        "kind": "choice",
        "role": "predict",
        "config": {
            "options": [{"id": "soil"}, {"id": "light"}],
            "correct_option_id": "light",
        },
        "feedback": {"saved": "Prediction saved; revisit it after the evidence."},
    }


def test_prediction_validates_choice_but_returns_existing_ungraded_state() -> None:
    result = evaluate_interaction(_contract(), {"selected_option_id": "soil"})

    assert result.outcome == "pending-review"
    assert result.score_earned == 0
    assert result.score_possible == 0
    assert result.feedback == "Prediction saved; revisit it after the evidence."


def test_prediction_keeps_hard_response_validation() -> None:
    with pytest.raises(InteractionResponseError, match="unknown id"):
        evaluate_interaction(_contract(), {"selected_option_id": "unknown"})


def test_v2_node_fallback_preserves_task_presentation_fields() -> None:
    contract = contract_from_v2_node(
        {
            "id": "interaction-predict",
            "kind": "interaction",
            "interaction_type": "choice",
            "prompt": "Long context",
            "role": "predict",
            "display_prompt": "What is your prediction?",
            "option_notes": {"soil": "Roots take up water, not food."},
            "config": {"options": [{"id": "soil"}, {"id": "light"}]},
            "feedback": {"saved": "Saved."},
        }
    )

    assert contract["role"] == "predict"
    assert contract["display_prompt"] == "What is your prediction?"
    assert contract["option_notes"] == {"soil": "Roots take up water, not food."}


def test_v2_nested_contract_inherits_new_outer_presentation_fields() -> None:
    contract = contract_from_v2_node(
        {
            "id": "interaction-predict",
            "kind": "interaction",
            "interaction_type": "choice",
            "role": "predict",
            "display_prompt": "Choose a prediction.",
            "option_notes": {"soil": "Teacher explanation."},
            "contract": {"id": "interaction-predict", "kind": "choice", "config": {}},
        }
    )

    assert contract["role"] == "predict"
    assert contract["display_prompt"] == "Choose a prediction."
    assert contract["option_notes"] == {"soil": "Teacher explanation."}
