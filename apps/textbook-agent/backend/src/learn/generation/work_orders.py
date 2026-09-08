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
    brief: str = ""
    intent: str = ""
    action: str | None = None
    evidence: str = ""
    support_level: str | None = None
    authoring_mode: Literal["new", "approved_item"] = "new"
    approved_item_ids: list[str] = Field(default_factory=list)


class WriterRequestLeakError(AssertionError):
    pass


def _capability_contract_hash(capability_id: str, writer_card: Mapping[str, Any]) -> str:
    payload = {
        "id": capability_id,
        "payload_schema_ref": writer_card.get("payload_schema_ref"),
        "payload_schema": writer_card.get("payload_schema"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _writer_card(capability_id: str) -> dict[str, Any]:
    view = load_learn_writer_view()
    cards = view.get("capabilities") or {}
    card = cards.get(capability_id)
    if not isinstance(card, dict):
        raise KeyError(f"writer view missing capability {capability_id!r}")
    return dict(card)


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
        str(getattr(item, "id", "") or ""): item for item in (approved_items or [])
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
        "allowed_facts": list(allowed_facts or []),
        "terminology": list(terminology or []),
        "authoring_mode": order.authoring_mode,
    }
    if order.authoring_mode == "approved_item" and approved_item is not None:
        request["approved_item"] = {
            key: approved_item[key]
            for key in ("id", "stem", "prompt", "options", "correct_key")
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
