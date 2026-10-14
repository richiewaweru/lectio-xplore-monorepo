"""Retry rules for shared-document Learn tasks.

Only contracts that carry a ``shared_task`` key are governed by these rules.
Every other contract keeps using its stored ``attempt_policy`` unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_VALID_AGGREGATIONS = {"first", "latest", "best"}


def is_shared_document_contract(contract: Mapping[str, Any] | None) -> bool:
    return isinstance(contract, Mapping) and "shared_task" in contract


def _role_of(contract: Mapping[str, Any]) -> str:
    role = contract.get("role")
    if role in {"predict", "check", "practice"}:
        return str(role)
    return "check" if contract.get("assessment_mode") == "graded" else "practice"


def _is_teacher_review(contract: Mapping[str, Any]) -> bool:
    config = contract.get("config") if isinstance(contract.get("config"), Mapping) else {}
    return contract.get("kind") == "short-response" and config.get("evaluation") == "teacher-review"


def policy_for(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Attempt rules for a shared-document contract, derived from its role."""
    role = _role_of(contract)
    if role == "predict" or _is_teacher_review(contract):
        return {
            "max_attempts": 1,
            "allow_retry_after_correct": False,
            "score_aggregation": "first",
            "reveal_after": None,
        }
    if role == "check":
        return {
            "max_attempts": 2,
            "allow_retry_after_correct": False,
            "score_aggregation": "first",
            "reveal_after": None,
        }
    return {
        "max_attempts": None,
        "allow_retry_after_correct": True,
        "score_aggregation": "latest",
        "reveal_after": 2,
    }


def effective_policy(contract: Mapping[str, Any] | None) -> dict[str, Any]:
    """policy_for for shared-document contracts, else the stored policy."""
    if not isinstance(contract, Mapping):
        return {
            "max_attempts": None,
            "allow_retry_after_correct": True,
            "score_aggregation": "latest",
            "reveal_after": None,
        }
    if is_shared_document_contract(contract):
        return policy_for(contract)
    stored = contract.get("attempt_policy")
    stored = stored if isinstance(stored, Mapping) else {}
    aggregation = contract.get("score_aggregation") or stored.get("score_aggregation")
    return {
        "max_attempts": stored.get("max_attempts"),
        "allow_retry_after_correct": stored.get("allow_retry_after_correct") is not False,
        "score_aggregation": aggregation if aggregation in _VALID_AGGREGATIONS else "latest",
        "reveal_after": None,
    }


def max_attempts_of(policy: Mapping[str, Any]) -> int | None:
    raw = policy.get("max_attempts")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def attempt_state(contract: Mapping[str, Any], outcomes: Sequence[str]) -> dict[str, Any]:
    """attempts_used / attempts_left / reveal after the given ordered outcomes."""
    policy = effective_policy(contract)
    used = len(outcomes)
    max_n = max_attempts_of(policy)
    last = outcomes[-1] if outcomes else None
    left: int | None = None if max_n is None else max(0, max_n - used)
    if policy["allow_retry_after_correct"] is False and last == "correct":
        left = 0

    reveal = None
    if is_shared_document_contract(contract) and last is not None and last != "correct":
        role = _role_of(contract)
        if role != "predict" and not _is_teacher_review(contract):
            non_correct = sum(1 for outcome in outcomes if outcome != "correct")
            reveal_after = policy.get("reveal_after")
            if role == "check":
                allowed = left == 0
            else:
                allowed = reveal_after is not None and non_correct >= int(reveal_after)
            if allowed:
                reveal = reveal_for(contract)
    return {"attempts_used": used, "attempts_left": left, "reveal": reveal}


def reveal_for(contract: Mapping[str, Any]) -> dict[str, Any] | None:
    """Correct response in the same shape as the learner response body."""
    kind = str(contract.get("kind") or "")
    config = contract.get("config") if isinstance(contract.get("config"), Mapping) else {}
    if kind in {"choice", "image-hotspot"}:
        correct = config.get("correct_option_id")
        return {"selected_option_id": str(correct)} if correct else None
    if kind == "multi-select":
        ids = config.get("correct_option_ids")
        if isinstance(ids, list) and ids:
            return {"selected_option_ids": [str(item) for item in ids]}
        return None
    if kind == "fill-blank":
        answers = config.get("answers")
        if not isinstance(answers, list) or not answers:
            return None
        blanks = []
        for answer in answers:
            first = answer[0] if isinstance(answer, list) and answer else answer
            blanks.append(str(first))
        return {"blanks": blanks}
    if kind == "numeric":
        value = config.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return {"value": value}
        return None
    if kind == "short-response":
        if config.get("evaluation") == "teacher-review":
            return None
        accepted = config.get("accepted_answers")
        if isinstance(accepted, list) and accepted:
            return {"text": str(accepted[0])}
        return None
    if kind in {"match-pairs", "classify", "drag-label"}:
        pairs = config.get("pairs")
        if not isinstance(pairs, list):
            return None
        matches = [
            {"left": str(pair["left"]), "right": str(pair["right"])}
            for pair in pairs
            if isinstance(pair, Mapping) and "left" in pair and "right" in pair
        ]
        return {"matches": matches} if matches else None
    if kind == "sequence":
        order = config.get("order")
        if isinstance(order, list) and order:
            return {"order": [str(item) for item in order]}
        return None
    return None
