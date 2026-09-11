"""Learner-action → retained interaction mapping (Learn-owned).

Teaching Plan learner actions describe WHAT the learner should do.
Legal mappings come from ``backend/resources/policies/learn-action-map.yaml``.
"""

from __future__ import annotations

from typing import Literal

from core.policies.loader import learn_defaults, learn_interaction_for_action, passive_learner_actions
from learn.interactions.registry import RETAINED_INTERACTIONS

LearnRetainedInteraction = Literal[
    "choice",
    "multi-select",
    "fill-blank",
    "classify",
    "match-pairs",
    "sequence",
    "numeric",
    "short-response",
]

PASSIVE_LEARNER_ACTIONS: frozenset[str] = passive_learner_actions()

ACTION_TO_LEARN_INTERACTION: dict[str, LearnRetainedInteraction] = {
    key: value  # type: ignore[misc]
    for key, value in learn_defaults().items()
    if value in RETAINED_INTERACTIONS
}

assert frozenset(ACTION_TO_LEARN_INTERACTION.values()) <= RETAINED_INTERACTIONS


def interaction_for_learner_action(action: str | None) -> LearnRetainedInteraction | None:
    mapped = learn_interaction_for_action(action)
    if mapped in RETAINED_INTERACTIONS:
        return mapped  # type: ignore[return-value]
    return None


__all__ = [
    "ACTION_TO_LEARN_INTERACTION",
    "LearnRetainedInteraction",
    "PASSIVE_LEARNER_ACTIONS",
    "interaction_for_learner_action",
]
