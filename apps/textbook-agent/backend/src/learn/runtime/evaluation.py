"""Server-authoritative Learn evaluators (P07).

Parity target: ``@lectio/learn`` ``interaction-contract.ts``. Hand-maintained
divergent scoring is not allowed; golden tests pin shared semantics.
"""

from __future__ import annotations

import re
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
    if outcome == "pending-review":
        return str(feedback.get("partial") or "Submitted for teacher review.")
    return str(feedback.get("incorrect") or "")


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InteractionResponseError(
            f"{field} must be a non-empty string", "invalid-response"
        )
    return value


def _require_string_array(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise InteractionResponseError(f"{field} must be an array of strings", "invalid-response")
    return list(value)


def _require_string_array_config(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or len(value) == 0:
        raise InteractionConfigError(f"{field} must be a non-empty array")
    return [str(item) for item in value]


def _reject_duplicates(ids: list[str], field: str) -> None:
    if len(set(ids)) != len(ids):
        raise InteractionResponseError(f"{field} contains duplicate ids", "duplicate-response-id")


def _reject_unknown(ids: list[str], known: set[str] | None, field: str) -> None:
    if known is None:
        return
    for item_id in ids:
        if item_id not in known:
            raise InteractionResponseError(
                f'{field} references unknown id "{item_id}"',
                "unknown-response-id",
            )


def _reject_unknown_config(ids: list[str], known: set[str] | None, field: str) -> None:
    if known is None:
        return
    for item_id in ids:
        if item_id not in known:
            raise InteractionConfigError(f'{field} references undeclared option "{item_id}"')


def _option_id_set(options: Any) -> set[str] | None:
    if not isinstance(options, list) or not options:
        return None
    known: set[str] = set()
    for option in options:
        if isinstance(option, dict) and option.get("id") is not None:
            known.add(str(option["id"]))
        else:
            known.add(str(option))
    return known


def _normalize_answer(value: str, *, case_sensitive: bool) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip())
    return cleaned if case_sensitive else cleaned.casefold()


def evaluate_choice(
    config: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    feedback: Mapping[str, Any],
) -> EvaluationResult:
    known = _option_id_set(config.get("options"))
    correct = str(config.get("correct_option_id") or "")
    if not correct:
        raise InteractionConfigError("choice config requires correct_option_id")
    if known is not None and correct not in known:
        raise InteractionConfigError(
            f'correct_option_id "{correct}" is not one of the declared options'
        )
    selected = _require_non_empty_string(
        (response or {}).get("selected_option_id"), "selected_option_id"
    )
    _reject_unknown([selected], known, "selected_option_id")
    ok = selected == correct
    return EvaluationResult(
        outcome="correct" if ok else "incorrect",
        score_earned=1.0 if ok else 0.0,
        score_possible=1.0,
        feedback=_graded_feedback("correct" if ok else "incorrect", feedback),
        details={"selected_option_id": selected},
    )


def evaluate_multi_select(
    config: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    feedback: Mapping[str, Any],
) -> EvaluationResult:
    correct_ids = _require_string_array_config(config.get("correct_option_ids"), "correct_option_ids")
    known = _option_id_set(config.get("options"))
    _reject_unknown_config(correct_ids, known, "correct_option_ids")

    selected_ids = _require_string_array(
        (response or {}).get("selected_option_ids"), "selected_option_ids"
    )
    _reject_duplicates(selected_ids, "selected_option_ids")
    _reject_unknown(selected_ids, known, "selected_option_ids")

    correct = set(correct_ids)
    selected = set(selected_ids)
    hits = sum(1 for item_id in selected if item_id in correct)
    false_positives = sum(1 for item_id in selected if item_id not in correct)
    score_possible = float(len(correct))
    score_earned = float(max(0, hits - false_positives))
    if (
        score_earned == score_possible
        and false_positives == 0
        and len(selected) == len(correct)
    ):
        outcome = "correct"
    elif score_earned > 0:
        outcome = "partial"
    else:
        outcome = "incorrect"
    return EvaluationResult(
        outcome=outcome,
        score_earned=score_earned,
        score_possible=score_possible,
        feedback=_graded_feedback(outcome, feedback),
        details={"false_positives": false_positives},
    )


def evaluate_fill_blank(
    config: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    feedback: Mapping[str, Any],
) -> EvaluationResult:
    answers = config.get("answers")
    if not isinstance(answers, list) or len(answers) == 0:
        raise InteractionConfigError("fill-blank config requires a non-empty answers[]")
    blank_ids = config.get("blank_ids")
    if blank_ids is not None and (
        not isinstance(blank_ids, list) or len(blank_ids) != len(answers)
    ):
        raise InteractionConfigError("blank_ids must have one id per answer")

    blanks = _require_string_array((response or {}).get("blanks"), "blanks")
    if len(blanks) != len(answers):
        raise InteractionResponseError(
            f"expected {len(answers)} blank response(s), received {len(blanks)}",
            "response-count-mismatch",
        )

    case_sensitive = config.get("case_sensitive") is True
    score_possible = float(len(answers))
    score_earned = 0.0
    per_blank: list[dict[str, Any]] = []
    for index, answer in enumerate(answers):
        accepted_raw = answer if isinstance(answer, list) else [answer]
        accepted = [
            _normalize_answer(str(value), case_sensitive=case_sensitive)
            for value in accepted_raw
        ]
        given = _normalize_answer(blanks[index] if index < len(blanks) else "", case_sensitive=case_sensitive)
        correct = given in accepted
        if correct:
            score_earned += 1.0
        blank_id = (
            str(blank_ids[index])
            if isinstance(blank_ids, list) and index < len(blank_ids)
            else str(index)
        )
        per_blank.append({"id": blank_id, "correct": correct})

    outcome = _partial_outcome(score_earned, score_possible)
    return EvaluationResult(
        outcome=outcome,
        score_earned=score_earned,
        score_possible=score_possible,
        feedback=_graded_feedback(outcome, feedback),
        details={"per_blank": per_blank},
    )


def evaluate_numeric(
    config: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    feedback: Mapping[str, Any],
) -> EvaluationResult:
    value = config.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not _isfinite(value):
        raise InteractionConfigError("numeric config value must be a finite number")
    tolerance = config.get("tolerance")
    if tolerance is not None:
        if (
            not isinstance(tolerance, (int, float))
            or isinstance(tolerance, bool)
            or not _isfinite(tolerance)
        ):
            raise InteractionConfigError("numeric tolerance must be a finite number")
        if float(tolerance) < 0:
            raise InteractionConfigError("numeric tolerance must not be negative")
    given = (response or {}).get("value")
    if not isinstance(given, (int, float)) or isinstance(given, bool) or not _isfinite(given):
        raise InteractionResponseError(
            "numeric response value must be a finite number", "invalid-response"
        )
    tol = float(tolerance) if tolerance is not None else 0.0
    ok = abs(float(given) - float(value)) <= tol
    return EvaluationResult(
        outcome="correct" if ok else "incorrect",
        score_earned=1.0 if ok else 0.0,
        score_possible=1.0,
        feedback=_graded_feedback("correct" if ok else "incorrect", feedback),
        details={
            "value": float(given),
            "tolerance": tol,
            "unit": config.get("unit") if config.get("unit") is not None else None,
        },
    )


def _isfinite(value: float | int) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def evaluate_short_response(
    config: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    feedback: Mapping[str, Any],
) -> EvaluationResult:
    text = _require_non_empty_string((response or {}).get("text"), "text")
    mode = config.get("evaluation")
    if mode == "teacher-review":
        return EvaluationResult(
            outcome="pending-review",
            score_earned=0.0,
            score_possible=1.0,
            feedback=_graded_feedback("pending-review", feedback),
            details={
                "mode": "teacher-review",
                "review_guidance": config.get("review_guidance"),
                "text": text,
            },
        )
    if mode != "accepted-answers":
        raise InteractionConfigError(
            "short-response evaluation must be 'accepted-answers' or 'teacher-review', "
            f'received "{mode}"'
        )
    accepted_answers = config.get("accepted_answers")
    if not isinstance(accepted_answers, list) or len(accepted_answers) == 0:
        raise InteractionConfigError(
            "short-response accepted-answers mode requires a non-empty accepted_answers[]"
        )
    case_sensitive = config.get("case_sensitive") is True
    accepted = [
        _normalize_answer(str(answer), case_sensitive=case_sensitive)
        for answer in accepted_answers
    ]
    ok = _normalize_answer(text, case_sensitive=case_sensitive) in accepted
    return EvaluationResult(
        outcome="correct" if ok else "incorrect",
        score_earned=1.0 if ok else 0.0,
        score_possible=1.0,
        feedback=_graded_feedback("correct" if ok else "incorrect", feedback),
        details={"mode": "accepted-answers", "text": text},
    )


def evaluate_match_pairs(
    config: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    feedback: Mapping[str, Any],
) -> EvaluationResult:
    pairs = config.get("pairs")
    if not isinstance(pairs, list) or len(pairs) == 0:
        raise InteractionConfigError("match-pairs config requires a non-empty pairs[]")
    lefts = [str(pair.get("left")) for pair in pairs if isinstance(pair, dict)]
    if len(set(lefts)) != len(lefts):
        raise InteractionConfigError("match-pairs source ids must be unique")
    expected = {
        str(pair["left"]): str(pair["right"])
        for pair in pairs
        if isinstance(pair, dict)
    }
    valid_targets = {str(pair["right"]) for pair in pairs if isinstance(pair, dict)}

    matches = (response or {}).get("matches")
    if not isinstance(matches, list):
        raise InteractionResponseError("matches must be an array", "invalid-response")
    submitted_lefts = [
        _require_non_empty_string(
            match.get("left") if isinstance(match, dict) else None, "match.left"
        )
        for match in matches
    ]
    _reject_duplicates(submitted_lefts, "matches")
    _reject_unknown(submitted_lefts, set(expected.keys()), "match.left")
    submitted_rights = [
        _require_non_empty_string(
            match.get("right") if isinstance(match, dict) else None, "match.right"
        )
        for match in matches
    ]
    _reject_unknown(submitted_rights, valid_targets, "match.right")

    score_possible = float(len(expected))
    score_earned = 0.0
    for match in matches:
        if not isinstance(match, dict):
            continue
        if expected.get(str(match.get("left"))) == str(match.get("right")):
            score_earned += 1.0
    outcome = _partial_outcome(score_earned, score_possible)
    return EvaluationResult(
        outcome=outcome,
        score_earned=score_earned,
        score_possible=score_possible,
        feedback=_graded_feedback(outcome, feedback),
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


def evaluate_interaction(contract: Mapping[str, Any], response: Any) -> EvaluationResult:
    kind = str(contract.get("kind") or "")
    config = contract.get("config") if isinstance(contract.get("config"), dict) else {}
    feedback = contract.get("feedback") if isinstance(contract.get("feedback"), dict) else {}
    response_map = response if isinstance(response, dict) else {}

    if kind in {"choice", "image-hotspot"}:
        return evaluate_choice(config, response_map, feedback)
    if kind == "multi-select":
        return evaluate_multi_select(config, response_map, feedback)
    if kind == "fill-blank":
        return evaluate_fill_blank(config, response_map, feedback)
    if kind == "numeric":
        return evaluate_numeric(config, response_map, feedback)
    if kind == "short-response":
        return evaluate_short_response(config, response_map, feedback)
    if kind in {"match-pairs", "classify", "drag-label"}:
        return evaluate_match_pairs(config, response_map, feedback)
    if kind == "sequence":
        return evaluate_sequence(config, response_map, feedback)
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
        if (
            cid == interaction_id
            or str(block_id) == interaction_id
            or str(block.get("id")) == interaction_id
        ):
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
