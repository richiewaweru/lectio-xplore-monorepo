"""Exact Print work orders and scoped writer requests (P04)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Mapping, Sequence, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from print.generation.selection_snapshot import PrintSelectionDecision, PrintSelectionSnapshot
from print.resources.selection import load_form_writer_view

if TYPE_CHECKING:
    from v3_blueprint.planning.models import PlannedBlock

REGISTERED_PRINT_VALIDATOR_REFS = frozenset(
    {
        "print.payload_schema",
        "print.validate_content",
        "print.validate_answer_key_integrity",
    }
)


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
    authoring_definition: dict[str, Any] = Field(default_factory=dict)
    instructions: dict[str, Any] | str | None = None
    required_inputs: list[str] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)
    validator_refs: list[str] = Field(default_factory=list)
    brief: str = ""
    intent: str = ""
    action: str | None = None
    evidence: str = ""


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
            "writer_guidance",
            "required_inputs",
            "capacity",
            "negative_cases",
            "validator_refs",
            "converter_ref",
            "postprocessor_ref",
            "knowledge",
            "fragmentation",
            "emphasis",
            "placement",
        )
        if writer_card.get(key) is not None
    }


def _form_contract_hash(form_id: str, writer_card: Mapping[str, Any]) -> str:
    payload = _complete_definition_payload(writer_card)
    payload.setdefault("capability_id", form_id)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _writer_card(form_id: str) -> dict[str, Any]:
    view = load_form_writer_view()
    forms = view.get("forms") or {}
    card = forms.get(form_id)
    if not isinstance(card, dict):
        raise KeyError(f"form writer view missing {form_id!r}")
    out = dict(card)
    _assert_authoring_definition_ready(form_id, out)
    return out


def _assert_authoring_definition_ready(form_id: str, card: Mapping[str, Any]) -> None:
    instructions = card.get("instructions")
    text = ""
    if isinstance(instructions, Mapping):
        text = str(instructions.get("text") or "").strip()
    elif isinstance(instructions, str):
        text = instructions.strip()
    if not text:
        raise ValueError(f"print/{form_id}: missing authoring instructions")
    if not card.get("payload_schema") and not card.get("payload_schema_ref"):
        raise ValueError(f"print/{form_id}: missing payload schema")
    if not card.get("required_inputs"):
        raise ValueError(f"print/{form_id}: missing required_inputs")
    if "generate" not in set(card.get("modes") or ()) and "convert-approved" not in set(
        card.get("modes") or ()
    ):
        raise ValueError(f"print/{form_id}: missing supported authoring modes")
    refs = [str(ref) for ref in (card.get("validator_refs") or [])]
    if not refs:
        raise ValueError(f"print/{form_id}: missing validator_refs")
    unknown = sorted(set(refs) - REGISTERED_PRINT_VALIDATOR_REFS)
    if unknown:
        raise ValueError(f"print/{form_id}: unknown validator_refs {unknown}")


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
        definition = _complete_definition_payload(card)
        deps = list(block.stimulus_dependencies or [])
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
                authoring_definition=definition,
                instructions=definition.get("instructions"),
                required_inputs=list(card.get("required_inputs") or []),
                modes=list(card.get("modes") or []),
                validator_refs=list(card.get("validator_refs") or []),
                brief=block.brief,
                intent=block.intent,
                action=action,
                evidence=block.evidence,
            )
        )
    return orders


def build_print_work_order_from_planned_block(
    planned: PlannedBlock,
    *,
    section_id: str | None = None,
    teaching_plan_id: str = "ad-hoc",
    teaching_plan_revision: int = 1,
    teaching_plan_hash: str = "ad-hoc",
) -> PrintWorkOrder:
    """Build a package-backed work order for direct writer tests/tools."""
    form_id = str(planned.object)
    card = _writer_card(form_id)
    schema = card.get("payload_schema")
    if not isinstance(schema, dict):
        schema = {"$ref": card.get("payload_schema_ref")}
    guidance = card.get("writer_guidance") or card.get("field_guidance") or {}
    definition = _complete_definition_payload(card)
    return PrintWorkOrder(
        work_order_id=f"print::ad-hoc::{planned.id}::{form_id}",
        block_id=str(planned.id),
        section_id=str(section_id or ""),
        form_id=form_id,
        placement=getattr(planned, "placement", "main") or "main",
        teaching_plan_id=teaching_plan_id,
        teaching_plan_revision=teaching_plan_revision,
        teaching_plan_hash=teaching_plan_hash,
        capability_contract_hash=_form_contract_hash(form_id, card),
        source_refs=list(getattr(planned, "source_question_ids", None) or []),
        dependency_ids=[],
        expected_output_schema=dict(schema),
        field_guidance=dict(guidance),
        authoring_definition=definition,
        instructions=definition.get("instructions"),
        required_inputs=list(card.get("required_inputs") or []),
        modes=list(card.get("modes") or []),
        validator_refs=list(card.get("validator_refs") or []),
        brief=str(planned.brief or ""),
        intent=str(planned.intent or ""),
        action=None,
        evidence=str(getattr(planned, "evidence", "") or ""),
    )


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
        "authoring_definition": order.authoring_definition,
        "instructions": order.instructions,
        "definition_hash": order.capability_contract_hash,
        "required_inputs": list(order.required_inputs),
        "modes": list(order.modes),
        "validator_refs": list(order.validator_refs),
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
    "build_print_work_order_from_planned_block",
    "build_print_writer_request",
    "compile_print_work_orders",
    "decisions_cover_teaching_plan",
]
