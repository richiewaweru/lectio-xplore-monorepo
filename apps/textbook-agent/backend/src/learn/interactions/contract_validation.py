"""Publish-time interaction contract validation (shared by Builder and publish)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from learn.runtime.evaluation import (
    InteractionConfigError,
    InteractionResponseError,
    evaluate_choice,
    evaluate_fill_blank,
    evaluate_match_pairs,
    evaluate_multi_select,
    evaluate_numeric,
    evaluate_sequence,
    evaluate_short_response,
)


def _config_validator(kind: str) -> Any:
    if kind == "choice":
        return evaluate_choice, {"selected_option_id": "__validation__"}
    if kind == "multi-select":
        return evaluate_multi_select, {"selected_option_ids": []}
    if kind == "fill-blank":
        return evaluate_fill_blank, {"blanks": []}
    if kind == "numeric":
        return evaluate_numeric, {"value": 0}
    if kind == "short-response":
        return evaluate_short_response, {"text": "__validation__"}
    if kind in {"match-pairs", "classify"}:
        return evaluate_match_pairs, {"matches": []}
    if kind == "sequence":
        return evaluate_sequence, {"order": []}
    return None, {}


def validate_interaction_contract(contract: Mapping[str, Any]) -> list[str]:
    """Lightweight publish-time contract checks (mirrors package validators)."""
    errors: list[str] = []
    if not isinstance(contract.get("id"), str) or not str(contract["id"]).strip():
        errors.append("interaction.id must be a non-empty string")
    kind = contract.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        errors.append("interaction.kind must be a non-empty string")
    if not isinstance(contract.get("prompt"), str) or not str(contract["prompt"]).strip():
        errors.append("interaction.prompt must be a non-empty string")
    if contract.get("assessment_mode") not in {"practice", "graded"}:
        errors.append("interaction.assessment_mode must be practice|graded")
    if not isinstance(contract.get("feedback"), dict):
        errors.append("interaction.feedback must be an object")
    if not isinstance(contract.get("completion"), dict):
        errors.append("interaction.completion must be an object")
    if not isinstance(contract.get("attempt_policy"), dict):
        errors.append("interaction.attempt_policy must be an object")
    if contract.get("ai_config_rule") != "config-only":
        errors.append("interaction.ai_config_rule must be 'config-only'")

    config = contract.get("config")
    if not isinstance(config, dict):
        errors.append("interaction.config must be an object")
        return errors
    evaluator, response = _config_validator(str(kind))
    if evaluator is None:
        return errors
    try:
        evaluator(config, response, {})
    except InteractionConfigError as exc:
        errors.append(str(exc))
    except InteractionResponseError:
        pass
    if kind == "classify":
        categories = config.get("categories")
        if not isinstance(categories, list) or len(categories) < 2:
            errors.append("classify config requires at least two categories")
        else:
            category_ids = {
                str(category.get("id"))
                for category in categories
                if isinstance(category, Mapping) and category.get("id")
            }
            for pair in config.get("pairs") or []:
                if isinstance(pair, Mapping) and str(pair.get("right")) not in category_ids:
                    errors.append("classify pair references undeclared category")
                    break
    return errors


__all__ = ["validate_interaction_contract"]
