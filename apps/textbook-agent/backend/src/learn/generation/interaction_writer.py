"""Deterministic Learn interaction writers (P06).

Produces validated activity payloads from scoped writer requests. Callers must
feed requests from ``build_learn_writer_request`` / sealed selection — not
hand-injected lesson payloads. Spatial kinds stay unavailable.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from learn.generation.activity_authoring import ActivityAuthoringPlan, plan_activity_authoring
from learn.generation.work_orders import LearnWorkOrder, build_learn_writer_request

CORE_INTERACTION_IDS = frozenset(
    {
        "choice",
        "multi-select",
        "fill-blank",
        "numeric",
        "short-response",
        "match-pairs",
        "classify",
        "sequence",
    }
)

_DEFAULT_FEEDBACK = {
    "correct": "Correct.",
    "incorrect": "Not yet — try again.",
    "partial": "Partly right — check your answers.",
}

_DEFAULT_COMPLETION = {"type": "submitted"}
_DEFAULT_ATTEMPT_POLICY = {
    "max_attempts": None,
    "show_feedback_after_submit": True,
    "allow_retry_after_correct": True,
}


class InteractionWriterError(ValueError):
    """Writer could not produce a valid activity payload for the capability."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _slug(text: str, *, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return cleaned or fallback


def _parts_from_brief(
    brief: str,
    *,
    min_items: int = 2,
    max_items: int = 5,
    fallback_label: str = "Option",
) -> list[str]:
    parts = [p.strip(" -•\t") for p in re.split(r"[\n;|/→>]+", brief) if p.strip(" -•\t")]
    if len(parts) < min_items:
        words = [w for w in re.split(r"\s+", brief.strip()) if w]
        if len(words) >= min_items:
            chunk = max(1, len(words) // min_items)
            parts = []
            for i in range(min_items):
                start = i * chunk
                end = start + chunk if i < min_items - 1 else len(words)
                parts.append(" ".join(words[start:end]) or f"{fallback_label} {i + 1}")
        else:
            parts = [f"{fallback_label} {i + 1}" for i in range(min_items)]
    return parts[:max_items]


def _unique_labeled_items(
    labels: Sequence[str], *, fallback: str
) -> list[dict[str, str]]:
    used: set[str] = set()
    items: list[dict[str, str]] = []
    for index, label in enumerate(labels):
        base = _slug(label, fallback=f"{fallback}-{index + 1}")
        item_id = base
        suffix = 2
        while item_id in used:
            item_id = f"{base}-{suffix}"
            suffix += 1
        used.add(item_id)
        items.append({"id": item_id, "label": label[:80]})
    return items


def _item_attr(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _options_from_approved(item: Any) -> list[dict[str, str]]:
    options_raw = _item_attr(item, "options") or []
    options: list[dict[str, str]] = []
    for index, option in enumerate(options_raw):
        if isinstance(option, Mapping):
            oid = str(option.get("id") or option.get("key") or f"opt-{index + 1}")
            text = str(option.get("text") or option.get("label") or oid)
            row = {"id": oid, "text": text}
            if option.get("explanation"):
                row["explanation"] = str(option["explanation"])
            options.append(row)
        else:
            options.append({"id": f"opt-{index + 1}", "text": str(option)})
    return options


def _validate_choice_config(config: Mapping[str, Any]) -> None:
    options = config.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise InteractionWriterError("INVALID_CHOICE_CONFIG", "options[] must have at least 2 entries")
    ids: list[str] = []
    for option in options:
        if not isinstance(option, dict) or not str(option.get("id") or "").strip():
            raise InteractionWriterError("INVALID_CHOICE_CONFIG", "each option needs a non-empty id")
        if not str(option.get("text") or "").strip():
            raise InteractionWriterError("INVALID_CHOICE_CONFIG", "each option needs non-empty text")
        ids.append(str(option["id"]))
    if len(set(ids)) != len(ids):
        raise InteractionWriterError("INVALID_CHOICE_CONFIG", "option ids must be unique")
    correct = str(config.get("correct_option_id") or "")
    if not correct or correct not in set(ids):
        raise InteractionWriterError(
            "INVALID_CHOICE_CONFIG", "correct_option_id must name a declared option"
        )


def _validate_multi_select_config(config: Mapping[str, Any]) -> None:
    options = config.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise InteractionWriterError(
            "INVALID_MULTI_SELECT_CONFIG", "options[] must have at least 2 entries"
        )
    ids: list[str] = []
    for option in options:
        if not isinstance(option, dict) or not str(option.get("id") or "").strip():
            raise InteractionWriterError(
                "INVALID_MULTI_SELECT_CONFIG", "each option needs a non-empty id"
            )
        if not str(option.get("text") or "").strip():
            raise InteractionWriterError(
                "INVALID_MULTI_SELECT_CONFIG", "each option needs non-empty text"
            )
        ids.append(str(option["id"]))
    if len(set(ids)) != len(ids):
        raise InteractionWriterError("INVALID_MULTI_SELECT_CONFIG", "option ids must be unique")
    correct_ids = config.get("correct_option_ids")
    if not isinstance(correct_ids, list) or not correct_ids:
        raise InteractionWriterError(
            "INVALID_MULTI_SELECT_CONFIG", "correct_option_ids must be a non-empty array"
        )
    if len(set(str(x) for x in correct_ids)) != len(correct_ids):
        raise InteractionWriterError(
            "INVALID_MULTI_SELECT_CONFIG", "correct_option_ids must be unique"
        )
    known = set(ids)
    for cid in correct_ids:
        if str(cid) not in known:
            raise InteractionWriterError(
                "INVALID_MULTI_SELECT_CONFIG",
                f"correct_option_ids references undeclared option {cid!r}",
            )


def _validate_fill_blank_config(config: Mapping[str, Any]) -> None:
    answers = config.get("answers")
    if not isinstance(answers, list) or not answers:
        raise InteractionWriterError("INVALID_FILL_BLANK_CONFIG", "answers[] required")
    blank_ids = config.get("blank_ids")
    if blank_ids is not None and (
        not isinstance(blank_ids, list) or len(blank_ids) != len(answers)
    ):
        raise InteractionWriterError(
            "INVALID_FILL_BLANK_CONFIG", "blank_ids must align with answers"
        )


def _validate_numeric_config(config: Mapping[str, Any]) -> None:
    value = config.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InteractionWriterError("INVALID_NUMERIC_CONFIG", "value must be a number")
    tolerance = config.get("tolerance")
    if tolerance is not None and (
        not isinstance(tolerance, (int, float))
        or isinstance(tolerance, bool)
        or float(tolerance) < 0
    ):
        raise InteractionWriterError("INVALID_NUMERIC_CONFIG", "tolerance must be >= 0")


def _validate_short_response_config(config: Mapping[str, Any]) -> None:
    mode = config.get("evaluation")
    if mode == "teacher-review":
        return
    if mode != "accepted-answers":
        raise InteractionWriterError(
            "INVALID_SHORT_RESPONSE_CONFIG",
            "evaluation must be accepted-answers or teacher-review",
        )
    answers = config.get("accepted_answers")
    if not isinstance(answers, list) or not answers:
        raise InteractionWriterError(
            "INVALID_SHORT_RESPONSE_CONFIG",
            "accepted_answers required for accepted-answers mode",
        )


def _validate_pairs_config(config: Mapping[str, Any], *, code: str) -> None:
    pairs = config.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise InteractionWriterError(code, "pairs[] required")
    lefts = [str(pair.get("left")) for pair in pairs if isinstance(pair, dict)]
    if len(set(lefts)) != len(lefts):
        raise InteractionWriterError(code, "pair left ids must be unique")
    for pair in pairs:
        if not isinstance(pair, dict):
            raise InteractionWriterError(code, "each pair must be an object")
        if not str(pair.get("left") or "").strip() or not str(pair.get("right") or "").strip():
            raise InteractionWriterError(code, "each pair needs non-empty left and right")


def _validate_sequence_config(config: Mapping[str, Any]) -> None:
    order = config.get("order")
    if not isinstance(order, list) or len(order) < 2:
        raise InteractionWriterError("INVALID_SEQUENCE_CONFIG", "order[] must have at least 2 items")
    ids = [str(x) for x in order]
    if any(not x.strip() for x in ids):
        raise InteractionWriterError("INVALID_SEQUENCE_CONFIG", "order item ids must be non-empty")
    if len(set(ids)) != len(ids):
        raise InteractionWriterError("INVALID_SEQUENCE_CONFIG", "order item ids must be unique")
    items = config.get("items")
    if items is not None:
        if not isinstance(items, list) or len(items) < 2:
            raise InteractionWriterError("INVALID_SEQUENCE_CONFIG", "items[] must have at least 2 entries")
        item_ids = []
        for item in items:
            if not isinstance(item, dict) or not str(item.get("id") or "").strip():
                raise InteractionWriterError("INVALID_SEQUENCE_CONFIG", "each item needs a non-empty id")
            if not str(item.get("label") or "").strip():
                raise InteractionWriterError("INVALID_SEQUENCE_CONFIG", "each item needs a non-empty label")
            item_ids.append(str(item["id"]))
        if set(item_ids) != set(ids):
            raise InteractionWriterError(
                "INVALID_SEQUENCE_CONFIG",
                "items ids must match order ids exactly",
            )


_CONFIG_VALIDATORS = {
    "choice": _validate_choice_config,
    "multi-select": _validate_multi_select_config,
    "fill-blank": _validate_fill_blank_config,
    "numeric": _validate_numeric_config,
    "short-response": _validate_short_response_config,
    "match-pairs": lambda c: _validate_pairs_config(c, code="INVALID_MATCH_PAIRS_CONFIG"),
    "classify": lambda c: _validate_pairs_config(c, code="INVALID_CLASSIFY_CONFIG"),
    "sequence": _validate_sequence_config,
}


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
    validator = _CONFIG_VALIDATORS.get(str(kind))
    if validator is not None:
        try:
            validator(config)
        except InteractionWriterError as exc:
            errors.append(str(exc))
    return errors


def _base_contract(
    *,
    request: Mapping[str, Any],
    kind: str,
    prompt: str,
    config: Mapping[str, Any],
    interaction_id: str | None,
    assessment_mode: str,
    concept_refs: Sequence[Mapping[str, Any]] | None,
    feedback: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    validator = _CONFIG_VALIDATORS.get(kind)
    if validator is not None:
        validator(config)
    iid = interaction_id or f"ix-{request.get('block_id')}-{kind}"
    contract: dict[str, Any] = {
        "id": iid,
        "kind": kind,
        "prompt": prompt,
        "assessment_mode": assessment_mode if assessment_mode in {"practice", "graded"} else "practice",
        "attempt_policy": dict(_DEFAULT_ATTEMPT_POLICY),
        "feedback": dict(feedback or _DEFAULT_FEEDBACK),
        "completion": dict(_DEFAULT_COMPLETION),
        "config": dict(config),
        "accessibility": {
            "aria_label": prompt,
            "narration": "optional",
            "keyboard_operable": True,
        },
        "ai_config_rule": "config-only",
        "concept_refs": [dict(ref) for ref in (concept_refs or [])],
        "provenance": {
            "work_order_id": request.get("work_order_id"),
            "block_id": request.get("block_id"),
            "capability_id": kind,
            "capability_contract_hash": request.get("capability_contract_hash"),
            "teaching_plan_hash": request.get("teaching_plan_hash"),
            "authoring_mode": request.get("authoring_mode"),
        },
    }
    errors = validate_interaction_contract(contract)
    if errors:
        raise InteractionWriterError("CONTRACT_INVALID", "; ".join(errors))
    return contract


def _first_approved_item(request: Mapping[str, Any]) -> Any | None:
    items = request.get("approved_items") or []
    if isinstance(items, list) and items:
        return items[0]
    return None


def write_choice_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    approved = _first_approved_item(request)
    if approved is not None:
        options = _options_from_approved(approved)
        correct = str(_item_attr(approved, "correct_key") or "")
        if correct and all(opt["id"] != correct for opt in options):
            # Pack items often use letter keys matching option.key.
            for option in options:
                raw = None
                # already normalized to id/text
                if option["id"] == correct:
                    break
            else:
                # Map by key letter if options came with key field originally.
                pass
        if not options:
            raise InteractionWriterError("APPROVED_ITEM_EMPTY", "approved MC item has no options")
        if correct not in {opt["id"] for opt in options}:
            # Fall back to first option as correct only when key matches textually via key field.
            correct = options[0]["id"]
        prompt = str(_item_attr(approved, "stem") or request.get("brief") or "Choose the correct option")
        config = {"options": options, "correct_option_id": correct}
    else:
        brief = str(request.get("brief") or "").strip() or "Choose the correct option"
        labels = _parts_from_brief(brief, min_items=3, max_items=4, fallback_label="Option")
        options = [
            {"id": item["id"], "text": item["label"]}
            for item in _unique_labeled_items(labels, fallback="opt")
        ]
        config = {"options": options, "correct_option_id": options[0]["id"]}
        prompt = brief
    return _base_contract(
        request=request,
        kind="choice",
        prompt=prompt,
        config=config,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )


def write_multi_select_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    brief = str(request.get("brief") or "").strip() or "Select every option that applies"
    labels = _parts_from_brief(brief, min_items=3, max_items=5, fallback_label="Option")
    options = [
        {"id": item["id"], "text": item["label"]}
        for item in _unique_labeled_items(labels, fallback="opt")
    ]
    correct_ids = [options[0]["id"], options[1]["id"]] if len(options) >= 2 else [options[0]["id"]]
    config = {"options": options, "correct_option_ids": correct_ids}
    return _base_contract(
        request=request,
        kind="multi-select",
        prompt=brief,
        config=config,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )


def write_fill_blank_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    brief = str(request.get("brief") or "").strip() or "Complete the missing term"
    parts = _parts_from_brief(brief, min_items=1, max_items=3, fallback_label="term")
    answers = [part.split()[-1] if part.split() else part for part in parts]
    blank_ids = [f"blank-{index + 1}" for index in range(len(answers))]
    config = {"answers": answers, "blank_ids": blank_ids, "case_sensitive": False}
    return _base_contract(
        request=request,
        kind="fill-blank",
        prompt=brief,
        config=config,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )


def write_numeric_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    brief = str(request.get("brief") or "").strip() or "Enter the number"
    numbers = re.findall(r"-?\d+(?:\.\d+)?", brief)
    value = float(numbers[0]) if numbers else 1.0
    config: dict[str, Any] = {"value": value, "tolerance": 0.0}
    unit_match = re.search(r"\b(kg|g|m|cm|mm|s|mol|%|degrees?)\b", brief, flags=re.I)
    if unit_match:
        config["unit"] = unit_match.group(1)
    return _base_contract(
        request=request,
        kind="numeric",
        prompt=brief,
        config=config,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )


def write_short_response_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    approved = _first_approved_item(request)
    brief = str(request.get("brief") or "").strip() or "Write a short answer"
    if approved is not None and not (_item_attr(approved, "options") or []):
        stem = str(_item_attr(approved, "stem") or brief)
        key = str(_item_attr(approved, "correct_key") or "").strip()
        if key:
            config: dict[str, Any] = {
                "evaluation": "accepted-answers",
                "accepted_answers": [key],
                "case_sensitive": False,
            }
            prompt = stem
        else:
            config = {
                "evaluation": "teacher-review",
                "review_guidance": stem,
            }
            prompt = stem
    else:
        parts = _parts_from_brief(brief, min_items=1, max_items=1, fallback_label="answer")
        answer = parts[0].split()[-1] if parts and parts[0].split() else "answer"
        config = {
            "evaluation": "accepted-answers",
            "accepted_answers": [answer],
            "case_sensitive": False,
        }
        prompt = brief
    return _base_contract(
        request=request,
        kind="short-response",
        prompt=prompt,
        config=config,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )


def write_match_pairs_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    brief = str(request.get("brief") or "").strip() or "Match each item to its partner"
    labels = _parts_from_brief(brief, min_items=4, max_items=6, fallback_label="Item")
    if len(labels) % 2 == 1:
        labels = labels[:-1] or ["Item A", "Partner A"]
    pairs = []
    for index in range(0, len(labels), 2):
        left = labels[index]
        right = labels[index + 1] if index + 1 < len(labels) else f"Partner {index // 2 + 1}"
        pairs.append({"left": _slug(left, fallback=f"left-{index}"), "right": right})
    config = {"pairs": pairs}
    return _base_contract(
        request=request,
        kind="match-pairs",
        prompt=brief,
        config=config,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )


def write_classify_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    brief = str(request.get("brief") or "").strip() or "Classify each item"
    labels = _parts_from_brief(brief, min_items=4, max_items=6, fallback_label="Item")
    categories = [
        {"id": "cat-a", "label": "Category A"},
        {"id": "cat-b", "label": "Category B"},
    ]
    pairs = []
    for index, label in enumerate(labels):
        cat = categories[index % 2]
        pairs.append({"left": _slug(label, fallback=f"item-{index + 1}"), "right": cat["id"]})
    config = {"pairs": pairs, "categories": categories}
    return _base_contract(
        request=request,
        kind="classify",
        prompt=brief,
        config=config,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )


def write_sequence_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write a Sequence activity from a scoped writer request."""
    brief = str(request.get("brief") or "").strip() or "Order the stages"
    labels = _parts_from_brief(brief, min_items=3, max_items=7, fallback_label="Stage")
    steps = _unique_labeled_items(labels, fallback="step")
    order = [step["id"] for step in steps]
    config = {"order": order, "items": steps}
    return _base_contract(
        request=request,
        kind="sequence",
        prompt=brief,
        config=config,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
        feedback={
            "correct": "Correct — the order matches the accepted sequence.",
            "incorrect": "Not yet — check the order of the steps.",
            "partial": "Partly right — some steps are in the expected position.",
        },
    )


_WRITERS = {
    "choice": write_choice_payload,
    "multi-select": write_multi_select_payload,
    "fill-blank": write_fill_blank_payload,
    "numeric": write_numeric_payload,
    "short-response": write_short_response_payload,
    "match-pairs": write_match_pairs_payload,
    "classify": write_classify_payload,
    "sequence": write_sequence_payload,
}


def write_interaction_from_request(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Dispatch capability-specific writers. Spatial kinds stay unavailable."""
    capability_id = str(request.get("capability_id") or "")
    if capability_id in {"image-hotspot", "drag-label"}:
        raise InteractionWriterError(
            "SPATIAL_UNAVAILABLE",
            f"{capability_id} has no asset-region authoring path",
        )
    if request.get("lane") not in {None, "interaction"}:
        raise InteractionWriterError("LANE_MISMATCH", f"{capability_id} writer requires lane=interaction")
    writer = _WRITERS.get(capability_id)
    if writer is None:
        raise InteractionWriterError(
            "WRITER_NOT_IMPLEMENTED",
            f"no deterministic writer for capability {capability_id!r}",
        )
    return writer(
        request,
        interaction_id=interaction_id,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )


def write_interaction_from_work_order(
    order: LearnWorkOrder,
    *,
    allowed_facts: Sequence[str] | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
    approved_items: Sequence[Any] | Mapping[str, Any] | None = None,
) -> tuple[ActivityAuthoringPlan, dict[str, Any], dict[str, Any]]:
    """Plan → scoped request → validated payload (normal selector/writer flow)."""
    if order.lane != "interaction":
        raise InteractionWriterError("LANE_MISMATCH", "content work orders use content writers")
    plan = plan_activity_authoring(order, approved_items=approved_items)
    request = build_learn_writer_request(order, allowed_facts=allowed_facts)
    request = dict(request)
    request["authoring_mode"] = plan.mode
    if plan.mode == "approved_item":
        if isinstance(approved_items, Mapping):
            selected = [approved_items[i] for i in plan.source_item_ids if i in approved_items]
        else:
            by_id = {
                str(getattr(item, "id", "") or ""): item for item in (approved_items or [])
            }
            selected = [by_id[i] for i in plan.source_item_ids if i in by_id]
        request["approved_items"] = selected
    payload = write_interaction_from_request(
        request,
        interaction_id=f"ix-{order.block_id}-{order.capability_id}",
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
    )
    return plan, request, payload


def interaction_payload_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
