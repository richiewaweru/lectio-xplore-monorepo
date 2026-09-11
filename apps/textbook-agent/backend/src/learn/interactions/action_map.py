"""Learner-action → retained interaction mapping (Learn-owned).

Teaching Plan learner actions describe WHAT the learner should do.
This module maps those path-agnostic actions onto retained Learn interaction kinds.
"""

from __future__ import annotations

from typing import Literal

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

# Passive actions do not require an interactive response surface.
PASSIVE_LEARNER_ACTIONS: frozenset[str] = frozenset(
    {"compare-without-response", "read-explanation"}
)

ACTION_TO_LEARN_INTERACTION: dict[str, LearnRetainedInteraction] = {
    "select-one": "choice",
    "select-many": "multi-select",
    "complete-missing-values": "fill-blank",
    "classify-items": "classify",
    "match-pairs": "match-pairs",
    "order-items": "sequence",
    "enter-number": "numeric",
    "enter-text": "short-response",
    # Gate wording alias
    "reconstruct-order": "sequence",
}

assert frozenset(ACTION_TO_LEARN_INTERACTION.values()) <= RETAINED_INTERACTIONS


__all__ = [
    "ACTION_TO_LEARN_INTERACTION",
    "LearnRetainedInteraction",
    "PASSIVE_LEARNER_ACTIONS",
]
