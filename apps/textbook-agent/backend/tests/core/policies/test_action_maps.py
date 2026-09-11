from __future__ import annotations

from core.policies.loader import (
    learn_interaction_for_action,
    load_learn_action_map,
    load_learner_actions,
    load_print_action_map,
    print_treatment_for_action,
)
from learn.interactions.action_map import ACTION_TO_LEARN_INTERACTION, PASSIVE_LEARNER_ACTIONS
from print.generation.task_treatments import (
    LEARNER_ACTION_TO_PRINT_TREATMENT,
    print_treatment_for_learner_action,
)


def test_learn_and_print_maps_load_from_yaml() -> None:
    learn = load_learn_action_map()
    print_map = load_print_action_map()
    vocab = load_learner_actions()
    assert learn["mappings"]["select-one"]["default"] == "choice"
    assert print_map["mappings"]["select-one"]["default"] == "choices"
    assert "select-one" in vocab["actions"]
    assert ACTION_TO_LEARN_INTERACTION["select-one"] == "choice"
    assert LEARNER_ACTION_TO_PRINT_TREATMENT["select-one"] == "choices"
    assert "read-explanation" in PASSIVE_LEARNER_ACTIONS


def test_twin_defaults_follow_policy_files() -> None:
    assert learn_interaction_for_action("select-one") == "choice"
    assert print_treatment_for_action("select-one") == "choices"
    assert learn_interaction_for_action("classify-items") == "classify"
    assert print_treatment_for_action("classify-items") == "questions"
    assert print_treatment_for_learner_action("enter-number", intent="demonstrate") == (
        "worked-example"
    )
    assert learn_interaction_for_action("read-explanation") is None
    assert print_treatment_for_action("read-explanation") is None
