"""Thin re-exports of retained-interaction evaluation contracts (Phase G).

Evaluation ownership stays in ``learn.runtime.evaluation``; this module is the
interactions-package surface for writers and future interaction-specific code.
"""

from __future__ import annotations

from typing import Any, Mapping

from learn.runtime.evaluation import (
    EvaluationResult,
    InteractionConfigError,
    InteractionResponseError,
    UnknownInteractionError,
    evaluate_choice,
    evaluate_fill_blank,
    evaluate_interaction,
    evaluate_match_pairs,
    evaluate_multi_select,
    evaluate_numeric,
    evaluate_sequence,
    evaluate_short_response,
)


def evaluate_classify(
    config: Mapping[str, Any],
    response: Mapping[str, Any],
    feedback: Mapping[str, Any] | None = None,
) -> EvaluationResult:
    """Classify shares match-pairs scoring semantics in the current runtime."""
    return evaluate_match_pairs(config, response, feedback or {})


__all__ = [
    "EvaluationResult",
    "InteractionConfigError",
    "InteractionResponseError",
    "UnknownInteractionError",
    "evaluate_choice",
    "evaluate_classify",
    "evaluate_fill_blank",
    "evaluate_interaction",
    "evaluate_match_pairs",
    "evaluate_multi_select",
    "evaluate_numeric",
    "evaluate_sequence",
    "evaluate_short_response",
]
