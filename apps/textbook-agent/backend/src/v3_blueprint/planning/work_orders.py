"""Exact Lectio work orders compiled from a CanonicalExecutionPlan (Phase 04)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from contracts.lectio import (
    get_component_card,
    get_component_schema_shape,
    get_planner_index,
)
from v3_blueprint.planning.canonical_plan import CanonicalExecutionPlan


class ExactWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_order_id: str
    block_id: str
    section_id: str
    component_id: str
    purpose: str
    lane: str
    plan_revision: int
    plan_hash: str
    component_card: dict[str, Any]
    field_contracts: dict[str, Any] = Field(default_factory=dict)
    schema_shape: dict[str, Any] | None = None
    locked_component_id: str
    forbidden_sibling_fields: list[str] = Field(default_factory=list)

    @property
    def section_field(self) -> str:
        card = self.component_card if isinstance(self.component_card, dict) else {}
        field = card.get("section_field") or card.get("sectionField")
        if isinstance(field, str) and field.strip():
            return field.strip()
        return ""


def _is_generatable(component_id: str, card: dict[str, Any]) -> bool:
    if card.get("writer_excluded") is True:
        return False
    if component_id in {"image-block", "video-embed"}:
        return False
    return True


def build_component_contract_matrix() -> list[dict[str, Any]]:
    """Programmatic matrix from Lectio planner_index — not a hand-maintained registry."""
    index = get_planner_index()
    component_ids = index.get("component_ids") or []
    rows: list[dict[str, Any]] = []
    for component_id in component_ids:
        if not isinstance(component_id, str):
            continue
        card = get_component_card(component_id) or {}
        rows.append(
            {
                "component_id": component_id,
                "section_field": card.get("section_field") or card.get("sectionField"),
                "cognitive_job": card.get("cognitive_job"),
                "writer_excluded": bool(card.get("writer_excluded")),
                "generatable": _is_generatable(component_id, card),
                "has_field_contracts": bool(card.get("field_contracts")),
                "capabilities": card.get("capabilities") or {},
            }
        )
    return rows


def compile_exact_work_orders(
    plan: CanonicalExecutionPlan,
    *,
    include_visual: bool = True,
) -> list[ExactWorkOrder]:
    orders: list[ExactWorkOrder] = []
    for block in plan.blocks:
        card = get_component_card(block.component_id) or {}
        if not include_visual and block.work_kind == "visual":
            continue
        field_contracts = card.get("field_contracts") if isinstance(card.get("field_contracts"), dict) else {}
        schema_shape = get_component_schema_shape(block.component_id)
        sibling_fields: list[str] = []
        if isinstance(schema_shape, dict):
            props = schema_shape.get("properties")
            if isinstance(props, dict):
                sibling_fields = sorted(key for key in props if isinstance(key, str))
            elif isinstance(props, list):
                sibling_fields = sorted(
                    str(item.get("name") or item.get("key") or item)
                    for item in props
                    if item is not None
                )
        orders.append(
            ExactWorkOrder(
                work_order_id=f"wo::{block.block_id}",
                block_id=block.block_id,
                section_id=block.section_id,
                component_id=block.component_id,
                purpose=block.purpose,
                lane=block.work_kind,
                plan_revision=plan.plan_revision,
                plan_hash=plan.plan_hash,
                component_card={
                    "component_id": block.component_id,
                    "cognitive_job": card.get("cognitive_job"),
                    "section_field": card.get("section_field") or card.get("sectionField"),
                    "capabilities": card.get("capabilities") or {},
                    "writer_excluded": bool(card.get("writer_excluded")),
                    "field_contracts": field_contracts,
                },
                field_contracts=field_contracts,
                schema_shape=schema_shape if isinstance(schema_shape, dict) else None,
                locked_component_id=block.component_id,
                forbidden_sibling_fields=sibling_fields,
            )
        )
    return orders


def assert_writer_cannot_change_component(
    order: ExactWorkOrder,
    emitted_component_id: str,
) -> None:
    if emitted_component_id != order.locked_component_id:
        raise ValueError(
            f"Writer attempted to change component_id from "
            f"'{order.locked_component_id}' to '{emitted_component_id}'"
        )


PROMPT_INVENTORY: list[dict[str, str]] = [
    {"prompt": "structural-planner.md", "action": "modified", "phase": "02", "note": "intent-only"},
    {"prompt": "component-selector-v1.txt", "action": "keep", "phase": "03", "note": "narrowed candidates"},
    {"prompt": "section writer prompts", "action": "modify", "phase": "04", "note": "exact work order only"},
    {"prompt": "question writer prompts", "action": "keep", "phase": "04", "note": "items lane"},
    {"prompt": "visual generator prompts", "action": "keep", "phase": "04", "note": "visual lane"},
]
