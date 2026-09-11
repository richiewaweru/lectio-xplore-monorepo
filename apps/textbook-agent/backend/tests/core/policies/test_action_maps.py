from __future__ import annotations

from core.policies.loader import (
    canonical_non_passive_actions,
    is_known_learner_action,
    known_learner_actions,
    learn_candidates_for_action,
    learn_interaction_for_action,
    learner_action_aliases,
    load_learn_action_map,
    load_learner_actions,
    load_print_action_map,
    print_treatment_for_action,
    resolve_learner_action,
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


def test_alias_resolves_for_learn_and_print() -> None:
    assert learner_action_aliases()["reconstruct-order"] == "order-items"
    assert resolve_learner_action("reconstruct-order") == "order-items"
    assert learn_interaction_for_action("reconstruct-order") == "sequence"
    assert print_treatment_for_action("reconstruct-order") == "questions"
    assert is_known_learner_action("reconstruct-order")


def test_describe_in_own_words_is_unknown_not_aliased() -> None:
    assert not is_known_learner_action("describe-in-own-words")
    assert resolve_learner_action("describe-in-own-words") == "describe-in-own-words"
    assert learn_interaction_for_action("describe-in-own-words") is None
    assert print_treatment_for_action("describe-in-own-words") is None


def test_every_canonical_non_passive_has_learn_and_print_realization() -> None:
    for action in sorted(canonical_non_passive_actions()):
        assert learn_interaction_for_action(action), f"missing Learn map for {action}"
        assert print_treatment_for_action(action), f"missing Print map for {action}"
        assert learn_candidates_for_action(action), f"missing Learn candidates for {action}"


def test_known_vocab_includes_passive_and_aliases() -> None:
    known = known_learner_actions()
    assert "select-one" in known
    assert "enter-text" in known
    assert "reconstruct-order" in known
    assert "read-explanation" in known
    assert "compare-without-response" in known
    assert "describe-in-own-words" not in known
