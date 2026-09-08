"""Deterministic Learn interaction writer (P06).

Produces validated activity payloads from scoped writer requests. Callers must
feed requests from ``build_learn_writer_request`` / sealed selection — not
hand-injected lesson payloads.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from learn.generation.activity_authoring import ActivityAuthoringPlan, plan_activity_authoring
from learn.generation.work_orders import LearnWorkOrder, build_learn_writer_request


class InteractionWriterError(ValueError):
    """Writer could not produce a valid activity payload for the capability."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


_DEFAULT_FEEDBACK = {
    "correct": "Correct — the order matches the accepted sequence.",
    "incorrect": "Not yet — check the order of the steps.",
    "partial": "Partly right — some steps are in the expected position.",
}

_DEFAULT_COMPLETION = {"type": "submitted"}
_DEFAULT_ATTEMPT_POLICY = {
    "max_attempts": None,
    "show_feedback_after_submit": True,
    "allow_retry_after_correct": True,
}


def _slug(text: str, *, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return cleaned or fallback


def _steps_from_brief(brief: str, *, min_items: int = 3, max_items: int = 7) -> list[dict[str, str]]:
    """Derive sequence steps from a teaching brief (deterministic, no LLM)."""
    parts = [p.strip(" -•\t") for p in re.split(r"[\n;|/→>]+", brief) if p.strip(" -•\t")]
    if len(parts) < min_items:
        # Fall back to word chunks so the writer still emits a legal payload.
        words = [w for w in re.split(r"\s+", brief.strip()) if w]
        if len(words) >= min_items:
            chunk = max(1, len(words) // min_items)
            parts = []
            for i in range(min_items):
                start = i * chunk
                end = start + chunk if i < min_items - 1 else len(words)
                parts.append(" ".join(words[start:end]) or f"Step {i + 1}")
        else:
            parts = [f"Stage {i + 1}" for i in range(min_items)]
    parts = parts[:max_items]
    used: set[str] = set()
    steps: list[dict[str, str]] = []
    for index, label in enumerate(parts):
        base = _slug(label, fallback=f"step-{index + 1}")
        step_id = base
        suffix = 2
        while step_id in used:
            step_id = f"{base}-{suffix}"
            suffix += 1
        used.add(step_id)
        steps.append({"id": step_id, "label": label[:80]})
    return steps


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
    if kind == "sequence":
        try:
            _validate_sequence_config(config)
        except InteractionWriterError as exc:
            errors.append(str(exc))
    return errors


def write_sequence_payload(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write a Sequence activity from a scoped writer request."""
    if request.get("capability_id") != "sequence":
        raise InteractionWriterError(
            "CAPABILITY_MISMATCH",
            f"expected sequence, got {request.get('capability_id')!r}",
        )
    if request.get("lane") != "interaction":
        raise InteractionWriterError("LANE_MISMATCH", "sequence writer requires lane=interaction")

    brief = str(request.get("brief") or "").strip() or "Order the stages"
    steps = _steps_from_brief(brief)
    order = [step["id"] for step in steps]
    config = {"order": order, "items": steps}
    _validate_sequence_config(config)

    iid = interaction_id or f"ix-{request.get('block_id')}-sequence"
    contract: dict[str, Any] = {
        "id": iid,
        "kind": "sequence",
        "prompt": brief,
        "assessment_mode": assessment_mode if assessment_mode in {"practice", "graded"} else "practice",
        "attempt_policy": dict(_DEFAULT_ATTEMPT_POLICY),
        "feedback": dict(_DEFAULT_FEEDBACK),
        "completion": dict(_DEFAULT_COMPLETION),
        "config": config,
        "accessibility": {
            "aria_label": brief,
            "narration": "optional",
            "keyboard_operable": True,
        },
        "ai_config_rule": "config-only",
        "concept_refs": [dict(ref) for ref in (concept_refs or [])],
        "provenance": {
            "work_order_id": request.get("work_order_id"),
            "block_id": request.get("block_id"),
            "capability_id": "sequence",
            "capability_contract_hash": request.get("capability_contract_hash"),
            "teaching_plan_hash": request.get("teaching_plan_hash"),
            "authoring_mode": request.get("authoring_mode"),
        },
    }
    errors = validate_interaction_contract(contract)
    if errors:
        raise InteractionWriterError("CONTRACT_INVALID", "; ".join(errors))
    return contract


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
    if capability_id == "sequence":
        return write_sequence_payload(
            request,
            interaction_id=interaction_id,
            assessment_mode=assessment_mode,
            concept_refs=concept_refs,
        )
    raise InteractionWriterError(
        "WRITER_NOT_IMPLEMENTED",
        f"no deterministic writer for capability {capability_id!r}",
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
