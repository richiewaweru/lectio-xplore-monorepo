"""Shared generation prompt fragments."""

from __future__ import annotations

from functools import lru_cache

from contracts.lectio import get_component_card, get_planner_index, get_template_contract


@lru_cache(maxsize=1)
def build_shared_generation_prefix() -> str:
    """Stable prefix reused across planning and writing nodes."""

    return """TEXTBOOK V3 PIPELINE RULES
- Work only within the responsibility of the current node.
- Preserve fixed facts, identifiers, and structural commitments from context.
- Return only the format requested for this node.
"""


@lru_cache(maxsize=1)
def planner_index_block() -> str:
    """Build the component palette block shared by the planner."""

    template = get_template_contract("guided-concept-path") or {}
    planner = get_planner_index()
    always_present = set(template.get("always_present", []))
    available = set(template.get("available_components", []))
    all_available = always_present | available
    component_budget: dict = template.get("component_budget", {})
    max_per_section: dict = template.get("max_per_section", {})
    lines: list[str] = [
        "TEMPLATE: guided-concept-path",
        f"REQUIRED in every section: {', '.join(sorted(always_present)) or 'none'}",
        "AVAILABLE COMPONENTS (use only these slugs):",
    ]
    phase_map: dict = planner.get("phase_map", {})
    for phase_num in sorted(phase_map.keys(), key=lambda key: int(key)):
        phase = phase_map[phase_num]
        lines.append(f"\nPhase {phase_num} - {phase.get('name', f'Phase {phase_num}') }:")
        for component_id in phase.get("components", []):
            if component_id not in all_available:
                continue
            card = get_component_card(component_id) or {}
            required = " | required=true" if component_id in always_present else ""
            lines.append(
                f"  {component_id} | section_field={card.get('section_field', '-')} "
                f"| cognitive_job={card.get('cognitive_job', '')} "
                f"| role={card.get('role', '')}{required}"
            )
    if component_budget:
        lines.append("\nCOMPONENT BUDGETS (max across entire lesson):")
        lines.extend(f"  {slug}: max {limit}" for slug, limit in component_budget.items())
    if max_per_section:
        lines.append("\nPER-SECTION LIMITS:")
        lines.extend(f"  {slug}: max {limit} per section" for slug, limit in max_per_section.items())
    return "\n".join(lines)


__all__ = ["build_shared_generation_prefix", "planner_index_block"]
