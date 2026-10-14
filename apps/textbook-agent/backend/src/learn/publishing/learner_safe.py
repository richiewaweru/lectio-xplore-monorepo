"""Learner-safe projection of a published Learn document.

Learners receive the document needed to render and answer each interaction, but
never its answer key. Marking is server-side and reads the stored release, so
stripping this projection does not affect evaluation. Owners keep the full
document.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from curriculum.shared_tasks.ordering import derange_for_display, scramble_for_display

# Config fields that reveal or encode the expected answer.
_ANSWER_KEY_FIELDS = (
    "correct_option_id",
    "correct_option_ids",
    "answers",
    "accepted_answers",
    "value",
    "tolerance",
    "pairs",
    "order",
    "correct_placements",
    "review_guidance",
    "rubric_criteria",
)


def _task_key(node: Mapping[str, Any]) -> str:
    contract = node.get("contract")
    if isinstance(contract, Mapping):
        shared_task = contract.get("shared_task")
        if isinstance(shared_task, Mapping) and shared_task.get("id"):
            return str(shared_task["id"])
        if contract.get("id"):
            return str(contract["id"])
    return str(node.get("id") or "")


def _pair_lists(config: Mapping[str, Any]) -> tuple[list[Any], list[Any]]:
    pairs = config.get("pairs")
    if not isinstance(pairs, list):
        return [], []
    lefts = [pair.get("left") for pair in pairs if isinstance(pair, Mapping)]
    rights = list(
        dict.fromkeys(pair.get("right") for pair in pairs if isinstance(pair, Mapping))
    )
    return lefts, rights


def _ensure_display_fields(node: dict[str, Any], config: dict[str, Any]) -> None:
    kind = node.get("interaction_type") or node.get("kind")
    key = _task_key(node)
    if kind == "match-pairs":
        lefts, rights = _pair_lists(config)
        if "left_items" not in config and lefts:
            config["left_items"] = lefts
        if "right_items" not in config and rights:
            config["right_items"] = derange_for_display(key, rights)
    elif kind == "fill-blank":
        if "blank_count" not in config:
            answers = config.get("answers")
            blank_ids = config.get("blank_ids")
            count = max(
                len(answers) if isinstance(answers, list) else 0,
                len(blank_ids) if isinstance(blank_ids, list) else 0,
            )
            if count:
                config["blank_count"] = count
    elif kind == "classify":
        lefts, rights = _pair_lists(config)
        if "items" not in config and lefts:
            config["items"] = lefts
        if "categories" not in config and rights:
            config["categories"] = [{"id": right, "label": right} for right in rights]
    elif kind == "sequence":
        order = config.get("order")
        if "items" not in config and isinstance(order, list) and order:
            config["items"] = scramble_for_display(key, order, order)


def learner_safe_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``document`` with every answer key removed.

    The input is never mutated. Display fields (match columns, blank count,
    classify items/categories, shuffled sequence items) are filled in first for
    releases published before those fields existed.
    """
    safe = copy.deepcopy(document)
    if not isinstance(safe, dict):
        return safe
    nodes = safe.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict) and node.get("kind") == "interaction":
                _strip_interaction(node)
    # Legacy v1 documents keep interactions on blocks.
    blocks = safe.get("blocks")
    if isinstance(blocks, dict):
        for block in blocks.values():
            interaction = block.get("learn_interaction") if isinstance(block, dict) else None
            if isinstance(interaction, dict):
                _strip_interaction(interaction)
    return safe


def _strip_interaction(node: dict[str, Any]) -> None:
    config = node.get("config")
    if isinstance(config, dict):
        _ensure_display_fields(node, config)
        for field in _ANSWER_KEY_FIELDS:
            config.pop(field, None)
    node.pop("contract", None)
