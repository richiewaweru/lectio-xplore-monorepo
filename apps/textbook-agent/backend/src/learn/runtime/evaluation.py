"""Server-authoritative Learn evaluators (P07).

Parity target: ``@lectio/learn`` ``interaction-contract.ts`` — especially
``evaluateSequence``. Hand-maintained divergent scoring is not allowed;
golden tests pin shared semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class InteractionConfigError(ValueError):
    """Authored config cannot be evaluated as declared."""


class InteractionResponseError(ValueError):
    """Learner response cannot be scored (unknown/duplicate/malformed)."""

    def __init__(self, message: str, code: str = "invalid-response") -> None:
        self.code = code
        super().__init__(message)


class UnknownInteractionError(LookupError):
    """interaction_id is not present on the release document."""


@dataclass(frozen=True)
class EvaluationResult:
    outcome: str  # correct | incorrect | partial | pending-review
    score_earned: float
    score_possible: float
    feedback: str
    details: dict[str, Any] | None = None


def _partial_outcome(earned: float, possible: float) -> str:
    if possible > 0 and earned == possible:
        return "correct"
    return "partial" if earned > 0 else "incorrect"


def _graded_feedback(outcome: str, feedback: Mapping[str, Any]) -> str:
    if outcome == "correct":
        return str(feedback.get("correct") or "")
    if outcome == "partial":
        return str(feedback.get("partial") or feedback.get("incorrect") or "")
    return str(feedback.get("incorrect") or "")


def _require_string_array(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise InteractionResponseError(f"{field} must be an array of strings", "invalid-response")
    return list(value)


def _reject_duplicates(ids: list[str], field: str) -> None:
    if len(set(ids)) != len(ids):
        raise InteractionResponseError(f"{field} contains duplicate ids", "duplicate-response-id")


def _reject_unknown(ids: list[str], known: set[str], field: str) -> None:
    for item_id in ids:
        if item_id not in known:
            raise InteractionResponseError(
                f'{field} references unknown id "{item_id}"',
                "unknown-response-id",
            )


def evaluate_sequence(
    config: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    feedback: Mapping[str, Any],
) -> EvaluationResult:
    """Mirror TS ``evaluateSequence``: one point per item in expected position."""
    order = config.get("order")
    if not isinstance(order, list) or len(order) == 0:
        raise InteractionConfigError("sequence config requires a non-empty order[]")
    expected = [str(item_id) for item_id in order]
    if len(set(expected)) != len(expected):
        raise InteractionConfigError("sequence item ids must be unique")

    given = _require_string_array((response or {}).get("order"), "order")
    _reject_duplicates(given, "order")
    if len(given) != len(expected):
        raise InteractionResponseError(
            f"expected {len(expected)} ordered item(s), received {len(given)}",
            "response-count-mismatch",
        )
    _reject_unknown(given, set(expected), "order")

    score_earned = sum(1.0 for index, item_id in enumerate(expected) if given[index] == item_id)
    score_possible = float(len(expected))
    outcome = _partial_outcome(score_earned, score_possible)
    return EvaluationResult(
        outcome=outcome,
        score_earned=score_earned,
        score_possible=score_possible,
        feedback=_graded_feedback(outcome, feedback),
    )


def evaluate_choice(
    config: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    feedback: Mapping[str, Any],
) -> EvaluationResult:
    selected = (response or {}).get("selected_option_id")
    if not isinstance(selected, str) or not selected.strip():
        raise InteractionResponseError(
            "selected_option_id must be a non-empty string", "invalid-response"
        )
    correct = str(config.get("correct_option_id") or "")
    if not correct:
        raise InteractionConfigError("choice config requires correct_option_id")
    options = config.get("options")
    if isinstance(options, list) and options:
        known: set[str] = set()
        for option in options:
            if isinstance(option, dict) and option.get("id") is not None:
                known.add(str(option["id"]))
            else:
                known.add(str(option))
        if correct not in known:
            raise InteractionConfigError(
                f'correct_option_id "{correct}" is not one of the declared options'
            )
        if selected not in known:
            raise InteractionResponseError(
                f'selected_option_id references unknown id "{selected}"',
                "unknown-response-id",
            )
    score_earned = 1.0 if selected == correct else 0.0
    outcome = "correct" if score_earned == 1.0 else "incorrect"
    return EvaluationResult(
        outcome=outcome,
        score_earned=score_earned,
        score_possible=1.0,
        feedback=_graded_feedback(outcome, feedback),
    )


def evaluate_interaction(contract: Mapping[str, Any], response: Any) -> EvaluationResult:
    kind = str(contract.get("kind") or "")
    config = contract.get("config") if isinstance(contract.get("config"), dict) else {}
    feedback = contract.get("feedback") if isinstance(contract.get("feedback"), dict) else {}
    response_map = response if isinstance(response, dict) else {}

    if kind == "sequence":
        return evaluate_sequence(config, response_map, feedback)
    if kind in {"choice", "image-hotspot"}:
        return evaluate_choice(config, response_map, feedback)
    raise InteractionConfigError(f"Unsupported interaction kind: {kind}")


def is_complete(result: EvaluationResult, rule: Mapping[str, Any] | None) -> bool:
    """Mirror TS ``isComplete`` — submitted / correct / score_at_least."""
    if not isinstance(rule, dict):
        return True
    rule_type = rule.get("type")
    if rule_type == "submitted":
        return True
    if rule_type == "correct":
        return result.outcome == "correct"
    if rule_type == "score_at_least":
        min_ratio = float(rule.get("min_ratio") or 0)
        return (
            result.score_possible > 0
            and result.score_earned / result.score_possible >= min_ratio
        )
    return True


def score_aggregation_of(contract: Mapping[str, Any] | None) -> str:
    """Declared retry aggregation: first | latest | best (default latest)."""
    if not isinstance(contract, dict):
        return "latest"
    policy = contract.get("score_aggregation") or contract.get("attempt_policy", {}).get(
        "score_aggregation"
    )
    if policy in {"first", "latest", "best"}:
        return str(policy)
    return "latest"


def find_interaction_in_document(
    document: Mapping[str, Any] | None, interaction_id: str
) -> tuple[dict[str, Any], str | None]:
    """Locate learn_interaction by contract id or block id. Returns (contract, section_id)."""
    if not isinstance(document, dict):
        raise UnknownInteractionError(interaction_id)
    blocks = document.get("blocks") if isinstance(document.get("blocks"), dict) else {}
    sections = document.get("sections") if isinstance(document.get("sections"), list) else []

    block_to_section: dict[str, str] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        sid = str(section.get("id") or "")
        for bid in section.get("block_ids") or []:
            block_to_section[str(bid)] = sid

    for block_id, block in blocks.items():
        if not isinstance(block, dict):
            continue
        contract = block.get("learn_interaction") or block.get("interaction")
        if not isinstance(contract, dict):
            continue
        cid = str(contract.get("id") or block.get("id") or block_id)
        if cid == interaction_id or str(block_id) == interaction_id or str(block.get("id")) == interaction_id:
            return dict(contract), block_to_section.get(str(block_id))
    raise UnknownInteractionError(interaction_id)


def concept_bindings_from_contract(
    contract: Mapping[str, Any], *, interaction_id: str
) -> list[dict[str, Any]]:
    """Derive concept bindings from the release contract — never from the client."""
    refs = contract.get("concept_refs") or contract.get("concepts") or []
    if not isinstance(refs, list):
        return []
    bindings: list[dict[str, Any]] = []
    for ref in refs:
        if isinstance(ref, str) and ref.strip():
            bindings.append(
                {"concept_id": ref.strip(), "weight": 1.0, "node_id": interaction_id}
            )
        elif isinstance(ref, dict) and ref.get("concept_id"):
            bindings.append(
                {
                    "concept_id": str(ref["concept_id"]),
                    "weight": float(ref.get("weight", 1.0)),
                    "node_id": ref.get("node_id") or interaction_id,
                    "unit_id": ref.get("unit_id"),
                    "path_lesson_id": ref.get("path_lesson_id"),
                    "misconception_id": ref.get("misconception_id"),
                }
            )
    return bindings


def feedback_for_outcome(contract: Mapping[str, Any], outcome: str) -> str:
    feedback = contract.get("feedback") if isinstance(contract.get("feedback"), dict) else {}
    return _graded_feedback(outcome, feedback)
