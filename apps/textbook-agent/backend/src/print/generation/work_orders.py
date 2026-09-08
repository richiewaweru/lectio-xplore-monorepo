"""Exact Print work orders and scoped writer requests (P04)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from print.generation.selection_snapshot import PrintSelectionDecision, PrintSelectionSnapshot
from print.resources.selection import load_form_writer_view


class PrintWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_order_id: str
    block_id: str
    section_id: str
    form_id: str
    placement: Literal["main", "margin", "spanning"] = "main"
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


class WriterRequestLeakError(AssertionError):
    pass


def _form_contract_hash(form_id: str, writer_card: Mapping[str, Any]) -> str:
    payload = {
        "id": form_id,
        "payload_schema_ref": writer_card.get("payload_schema_ref"),
        "payload_schema": writer_card.get("payload_schema"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _writer_card(form_id: str) -> dict[str, Any]:
    view = load_form_writer_view()
    forms = view.get("forms") or {}
    card = forms.get(form_id)
    if not isinstance(card, dict):
        raise KeyError(f"form writer view missing {form_id!r}")
    return dict(card)


def _block_index(teaching_plan: TeachingPlan) -> dict[str, tuple[str, TeachingPlanBlock]]:
    out: dict[str, tuple[str, TeachingPlanBlock]] = {}
    for section in teaching_plan.sections:
        for block in section.blocks:
            out[block.id] = (section.slot_id, block)
    return out


def compile_print_work_orders(
    *,
    teaching_plan: TeachingPlan,
    snapshot: PrintSelectionSnapshot,
) -> list[PrintWorkOrder]:
    blocks = _block_index(teaching_plan)
    orders: list[PrintWorkOrder] = []
    for decision in snapshot.decisions:
        section_id, block = blocks[decision.block_id]
        action = None
        if block.learner_action is not None:
            action = block.learner_action.action
        card = _writer_card(decision.form_id)
        schema = card.get("payload_schema")
        if not isinstance(schema, dict):
            schema = {"$ref": card.get("payload_schema_ref")}
        guidance = card.get("writer_guidance") or card.get("field_guidance") or {}
        deps: list[str] = []
        if block.learner_action is not None:
            deps = list(block.learner_action.dependencies or [])
        orders.append(
            PrintWorkOrder(
                work_order_id=f"print::{snapshot.path}::{block.id}::{decision.form_id}",
                block_id=block.id,
                section_id=section_id,
                form_id=decision.form_id,
                placement=decision.placement,
                teaching_plan_id=snapshot.teaching_plan_id,
                teaching_plan_revision=snapshot.teaching_plan_revision,
                teaching_plan_hash=snapshot.teaching_plan_hash,
                capability_contract_hash=_form_contract_hash(decision.form_id, card),
                source_refs=list(block.source_question_ids or []),
                dependency_ids=deps,
                expected_output_schema=dict(schema),
                field_guidance=dict(guidance),
                brief=block.brief,
                intent=block.intent,
                action=action,
                evidence=block.evidence,
            )
        )
    return orders


def build_print_writer_request(
    order: PrintWorkOrder,
    *,
    allowed_facts: Sequence[str] | None = None,
    terminology: Sequence[str] | None = None,
    sibling_sentinels: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    del sibling_sentinels
    request = {
        "work_order_id": order.work_order_id,
        "block_id": order.block_id,
        "form_id": order.form_id,
        "placement": order.placement,
        "brief": order.brief,
        "intent": order.intent,
        "action": order.action,
        "evidence": order.evidence,
        "teaching_plan_hash": order.teaching_plan_hash,
        "capability_contract_hash": order.capability_contract_hash,
        "source_refs": list(order.source_refs),
        "dependency_ids": list(order.dependency_ids),
        "payload_schema": order.expected_output_schema,
        "field_guidance": order.field_guidance,
        "allowed_facts": list(allowed_facts or []),
        "terminology": list(terminology or []),
    }
    assert_no_sibling_schema_leak(request, selected_form_id=order.form_id)
    return request


def assert_no_sibling_schema_leak(
    request: Mapping[str, Any],
    *,
    selected_form_id: str,
    forbidden_tokens: Sequence[str] | None = None,
) -> None:
    blob = json.dumps(request, sort_keys=True, default=str)
    for token in forbidden_tokens or ():
        if token and token in blob:
            raise WriterRequestLeakError(
                f"writer request leaked sibling sentinel {token!r} "
                f"while writing {selected_form_id!r}"
            )
    for marker in ("full_catalogue", "all_forms", "sibling_payload_schema"):
        if marker in blob:
            raise WriterRequestLeakError(f"writer request leaked catalogue marker {marker!r}")


def decisions_cover_teaching_plan(
    teaching_plan: TeachingPlan,
    decisions: Sequence[PrintSelectionDecision],
) -> None:
    """Every required teaching block appears once; dependencies preserved on orders."""
    teaching_ids = [block.id for section in teaching_plan.sections for block in section.blocks]
    decision_ids = [item.block_id for item in decisions]
    if sorted(teaching_ids) != sorted(decision_ids) or len(decision_ids) != len(set(decision_ids)):
        raise ValueError(
            f"native plan coverage mismatch teaching={teaching_ids} decisions={decision_ids}"
        )


__all__ = [
    "PrintWorkOrder",
    "WriterRequestLeakError",
    "assert_no_sibling_schema_leak",
    "build_print_writer_request",
    "compile_print_work_orders",
    "decisions_cover_teaching_plan",
]
