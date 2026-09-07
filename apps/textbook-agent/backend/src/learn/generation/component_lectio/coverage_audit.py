"""Derive production-selectable components and audit payload strategy coverage."""

from __future__ import annotations

from typing import Any

from contracts.lectio import get_component_card
from generation.component_lectio.payload_strategies import (
    EXACT_CONTRACT_TEST_MARKERS,
    ITEM_COMPONENT_IDS,
    VISUAL_COMPONENT_IDS,
    strategy_for,
)
from resource_specs.component_candidates import DEFAULT_TEMPLATE_ID, resolve_role_candidates
from resource_specs.loader import get_spec


def _work_kind_for(component_id: str) -> str:
    card = get_component_card(component_id) or {}
    if card.get("writer_excluded") is True:
        return "visual"
    if component_id in ITEM_COMPONENT_IDS:
        return "items"
    if component_id == "answer-key":
        return "answer_key"
    if component_id in VISUAL_COMPONENT_IDS:
        return "visual"
    return "content"


def production_selectable_components(
    *,
    resource_type: str = "lesson",
    template_id: str = DEFAULT_TEMPLATE_ID,
) -> list[dict[str, Any]]:
    """Union of candidates across all roles in the production lesson resource spec."""
    spec = get_spec(resource_type)
    roles: list[str] = []
    for section in list(spec.sections.required) + list(spec.sections.optional):
        if section.role not in roles:
            roles.append(section.role)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for role in roles:
        candidates = resolve_role_candidates(
            role,
            resource_type=resource_type,
            template_id=template_id,
        )
        for component_id in candidates.candidates:
            if component_id in seen:
                # Still record additional roles.
                for row in rows:
                    if row["component_id"] == component_id and role not in row["roles"]:
                        row["roles"].append(role)
                continue
            seen.add(component_id)
            card = get_component_card(component_id) or {}
            section_field = card.get("section_field") or card.get("sectionField")
            lane = _work_kind_for(component_id)
            rows.append(
                {
                    "component_id": component_id,
                    "roles": [role],
                    "lane": lane,
                    "section_field": section_field,
                    "strategy": strategy_for(lane, component_id),
                    "exact_contract_test": EXACT_CONTRACT_TEST_MARKERS.get(component_id),
                    "has_card": bool(card),
                }
            )
    return rows


def coverage_gaps(
    *,
    resource_type: str = "lesson",
    template_id: str = DEFAULT_TEMPLATE_ID,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for row in production_selectable_components(
        resource_type=resource_type,
        template_id=template_id,
    ):
        missing: list[str] = []
        if not row["has_card"]:
            missing.append("card")
        if not row["section_field"]:
            missing.append("section_field")
        if not row["lane"]:
            missing.append("lane")
        if not row["strategy"]:
            missing.append("strategy")
        if not row["exact_contract_test"]:
            missing.append("exact_contract_test")
        if missing:
            gaps.append({**row, "missing": missing})
    return gaps


__all__ = ["coverage_gaps", "production_selectable_components"]
