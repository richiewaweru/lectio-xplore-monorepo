"""Exact Learn work orders and scoped writer requests (P04)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from curriculum.teaching_plan.compatibility import (
    ActionSourceIncompatibleError,
    assert_action_compatible_with_sources,
)
from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.resources.selection import load_learn_writer_view

REGISTERED_LEARN_VALIDATOR_REFS = frozenset(
    {
        "learn.payload_schema",
        "learn.evaluateChoice",
        "learn.evaluateMultiSelect",
        "learn.evaluateFillBlank",
        "learn.evaluateNumeric",
        "learn.evaluateShortResponse",
        "learn.evaluateMatchPairs",
        "learn.evaluateClassify",
        "learn.evaluateSequence",
        "learn.quizContentToInteractionContract",
        "learn.fillBlankContentToInteractionContract",
    }
)


class LearnWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_order_id: str
    block_id: str
    section_id: str
    lane: Literal["content", "interaction"]
    capability_id: str
    teaching_plan_id: str
    teaching_plan_revision: int
    teaching_plan_hash: str
    capability_contract_hash: str
    source_refs: list[str] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)
    expected_output_schema: dict[str, Any] = Field(default_factory=dict)
    field_guidance: dict[str, Any] = Field(default_factory=dict)
    authoring_definition: dict[str, Any] = Field(default_factory=dict)
    instructions: dict[str, Any] | str | None = None
    required_inputs: list[str] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)
    validator_refs: list[str] = Field(default_factory=list)
    brief: str = ""
    intent: str = ""
    action: str | None = None
    evidence: str = ""
    support_level: str | None = None
    authoring_mode: Literal["new", "approved_item"] = "new"
    approved_item_ids: list[str] = Field(default_factory=list)


class WriterRequestLeakError(AssertionError):
    pass


def _complete_definition_payload(writer_card: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: writer_card.get(key)
        for key in (
            "definition_version",
            "capability_id",
            "native_path",
            "lane",
            "purpose",
            "modes",
            "instructions",
            "schema_ref",
            "payload_schema_ref",
            "payload_schema",
            "field_guidance",
            "required_inputs",
            "requires",
            "capacity",
            "negative_cases",
            "examples",
            "validator_refs",
            "converter_ref",
            "postprocessor_ref",
            "asset_requirements",
        )
        if writer_card.get(key) is not None
    }


def _capability_contract_hash(capability_id: str, writer_card: Mapping[str, Any]) -> str:
    payload = _complete_definition_payload(writer_card)
    payload.setdefault("capability_id", capability_id)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _writer_card(capability_id: str) -> dict[str, Any]:
    view = load_learn_writer_view()
    cards = view.get("capabilities") or {}
    card = cards.get(capability_id)
    if not isinstance(card, dict):
        raise KeyError(f"writer view missing capability {capability_id!r}")
    out = dict(card)
    _assert_authoring_definition_ready(capability_id, out)
    return out


def _assert_authoring_definition_ready(capability_id: str, card: Mapping[str, Any]) -> None:
    instructions = card.get("instructions")
    text = ""
    if isinstance(instructions, Mapping):
        text = str(instructions.get("text") or "").strip()
    elif isinstance(instructions, str):
        text = instructions.strip()
    if not text:
        raise ValueError(f"learn/{capability_id}: missing authoring instructions")
    if not card.get("payload_schema") and not card.get("payload_schema_ref"):
        raise ValueError(f"learn/{capability_id}: missing payload schema")
    if not card.get("required_inputs"):
        raise ValueError(f"learn/{capability_id}: missing required_inputs")
    if "generate" not in set(card.get("modes") or ()) and "convert-approved" not in set(
        card.get("modes") or ()
    ):
        raise ValueError(f"learn/{capability_id}: missing supported authoring modes")
    refs = [str(ref) for ref in (card.get("validator_refs") or [])]
    if not refs:
        raise ValueError(f"learn/{capability_id}: missing validator_refs")
    unknown = sorted(set(refs) - REGISTERED_LEARN_VALIDATOR_REFS)
    if unknown:
        raise ValueError(f"learn/{capability_id}: unknown validator_refs {unknown}")


def _block_index(teaching_plan: TeachingPlan) -> dict[str, tuple[str, TeachingPlanBlock]]:
    out: dict[str, tuple[str, TeachingPlanBlock]] = {}
    for section in teaching_plan.sections:
        for block in section.blocks:
            out[block.id] = (section.slot_id, block)
    return out


def compile_learn_work_orders(
    *,
    teaching_plan: TeachingPlan,
    snapshot: LearnSelectionSnapshot,
    approved_items: Sequence[Any] | None = None,
) -> list[LearnWorkOrder]:
    """Compile exact per-capability work orders from a sealed selection snapshot."""
    approved_by_id = {
        str(item.get("id") if isinstance(item, Mapping) else getattr(item, "id", "") or ""): item
        for item in (approved_items or [])
    }
    blocks = _block_index(teaching_plan)
    orders: list[LearnWorkOrder] = []

    for decision in snapshot.decisions:
        section_id, block = blocks[decision.block_id]
        action = None
        support = None
        evidence = block.evidence
        if block.learner_action is not None:
            action = block.learner_action.action
            support = block.learner_action.support_level
            evidence = block.learner_action.evidence or evidence

        # When a learner action is present, trust decision.source_item_ids
        # including an empty list — empty means "author new", not "fall back
        # to block assessment question ids" (those are often MC/open).
        if action:
            source_ids = list(decision.source_item_ids or [])
        else:
            source_ids = list(decision.source_item_ids or block.source_question_ids or [])
        if source_ids and action:
            sources = [approved_by_id[item_id] for item_id in source_ids if item_id in approved_by_id]
            if len(sources) != len(source_ids):
                raise ActionSourceIncompatibleError(
                    f"approved item missing for block {block.id!r}: {source_ids}"
                )
            assert_action_compatible_with_sources(action=action, source_items=sources)

        surfaces: list[tuple[Literal["content", "interaction"], str]] = []
        if decision.content_id:
            surfaces.append(("content", decision.content_id))
        if decision.interaction_id:
            surfaces.append(("interaction", decision.interaction_id))

        for lane, capability_id in surfaces:
            card = _writer_card(capability_id)
            schema = card.get("payload_schema")
            if not isinstance(schema, dict):
                schema = {"$ref": card.get("payload_schema_ref")}
            definition = _complete_definition_payload(card)
            authoring_mode: Literal["new", "approved_item"] = (
                "approved_item" if source_ids and lane == "interaction" else "new"
            )
            orders.append(
                LearnWorkOrder(
                    work_order_id=f"learn::{snapshot.path}::{block.id}::{capability_id}",
                    block_id=block.id,
                    section_id=section_id,
                    lane=lane,
                    capability_id=capability_id,
                    teaching_plan_id=snapshot.teaching_plan_id,
                    teaching_plan_revision=snapshot.teaching_plan_revision,
                    teaching_plan_hash=snapshot.teaching_plan_hash,
                    capability_contract_hash=_capability_contract_hash(capability_id, card),
                    source_refs=list(source_ids),
                    dependency_ids=list(decision.dependency_ids),
                    expected_output_schema=dict(schema),
                    field_guidance=dict(card.get("field_guidance") or {}),
                    authoring_definition=definition,
                    instructions=definition.get("instructions"),
                    required_inputs=list(card.get("required_inputs") or []),
                    modes=list(card.get("modes") or []),
                    validator_refs=list(card.get("validator_refs") or []),
                    brief=block.brief,
                    intent=block.intent,
                    action=action,
                    evidence=evidence,
                    support_level=support,
                    authoring_mode=authoring_mode,
                    approved_item_ids=list(source_ids) if authoring_mode == "approved_item" else [],
                )
            )
    return orders


def build_learn_writer_request(
    order: LearnWorkOrder,
    *,
    allowed_facts: Sequence[str] | None = None,
    terminology: Sequence[str] | None = None,
    approved_item: Mapping[str, Any] | None = None,
    sibling_sentinels: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Provider request for one capability — selected schema only, no sibling leak."""
    del sibling_sentinels  # Never interpolated into the request.
    request: dict[str, Any] = {
        "work_order_id": order.work_order_id,
        "block_id": order.block_id,
        "capability_id": order.capability_id,
        "lane": order.lane,
        "brief": order.brief,
        "intent": order.intent,
        "action": order.action,
        "evidence": order.evidence,
        "support_level": order.support_level,
        "teaching_plan_hash": order.teaching_plan_hash,
        "capability_contract_hash": order.capability_contract_hash,
        "source_refs": list(order.source_refs),
        "dependency_ids": list(order.dependency_ids),
        "payload_schema": order.expected_output_schema,
        "field_guidance": order.field_guidance,
        "authoring_definition": order.authoring_definition,
        "instructions": order.instructions,
        "definition_hash": order.capability_contract_hash,
        "required_inputs": list(order.required_inputs),
        "modes": list(order.modes),
        "validator_refs": list(order.validator_refs),
        "allowed_facts": list(allowed_facts or []),
        "terminology": list(terminology or []),
        "authoring_mode": order.authoring_mode,
    }
    if order.authoring_mode == "approved_item" and approved_item is not None:
        allowed_keys = (
            "id",
            "stem",
            "prompt",
            "question",
            "options",
            "correct_key",
            "correct_keys",
            "correct_option_id",
            "correct_option_ids",
            "answer",
            "accepted_answer",
            "answers",
            "accepted_answers",
            "value",
            "tolerance",
            "unit",
            "pairs",
            "matches",
            "categories",
            "mapping",
            "assignments",
            "order",
            "sequence",
            "correct_order",
            "items",
        )
        request["approved_item"] = {
            key: approved_item[key]
            for key in allowed_keys
            if key in approved_item
        }
    assert_no_sibling_schema_leak(request, selected_capability_id=order.capability_id)
    return request


def assert_no_sibling_schema_leak(
    request: Mapping[str, Any],
    *,
    selected_capability_id: str,
    forbidden_capability_ids: Sequence[str] | None = None,
    forbidden_tokens: Sequence[str] | None = None,
) -> None:
    """Writer request must not carry sibling capability schemas or sentinel keys."""
    blob = json.dumps(request, sort_keys=True, default=str)
    for token in forbidden_tokens or ():
        if token and token in blob:
            raise WriterRequestLeakError(
                f"writer request leaked sibling sentinel {token!r} "
                f"while writing {selected_capability_id!r}"
            )
    for capability_id in forbidden_capability_ids or ():
        if capability_id == selected_capability_id:
            continue
        # Schema-bearing sibling keys only — capability names in prose briefs are ok.
        for key in (f'"{capability_id}"', f"payload_schema_{capability_id}"):
            if key in blob and f'"capability_id": "{capability_id}"' in blob:
                raise WriterRequestLeakError(
                    f"writer request leaked sibling capability {capability_id!r}"
                )
    # Full catalogue markers must never appear.
    for marker in ("full_catalogue", "all_capabilities", "sibling_payload_schema"):
        if marker in blob:
            raise WriterRequestLeakError(f"writer request leaked catalogue marker {marker!r}")


__all__ = [
    "LearnWorkOrder",
    "WriterRequestLeakError",
    "assert_no_sibling_schema_leak",
    "build_learn_writer_request",
    "compile_learn_work_orders",
]
