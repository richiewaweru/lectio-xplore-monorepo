"""Deterministic Lectio-legal candidate intersection for resource-spec roles.

Candidate calculation (GENERAL_LESSON_SPEC_TARGET):

    (preferred ∪ allowed)
    ∩ template available_components
    − role forbidden
    − global forbidden
    − manual-only / generation-excluded
    then apply remaining component_budget + max_per_section

Lectio owns component metadata (cognitive_job, capabilities, field contracts).
This module only intersects IDs and budget constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from contracts.lectio import (
    MANUAL_ONLY_COMPONENT_IDS,
    get_component_card,
    get_planner_index,
    get_template_contract,
)
from resource_specs.loader import PRIMARY_RESOURCE_TYPE, get_spec
from resource_specs.schema import ResourceSpec, SectionSpec

# Page-level pseudo-components that must never appear in AI candidate sets.
PAGE_PSEUDO_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "prose",
        "table",
        "aside",
        "figure",
        "generic-card",
        "page-block",
    }
)

DEFAULT_TEMPLATE_ID = "guided-concept-path"

_EXCLUSION_NOT_IN_PLANNER = "not_in_planner_index"
_EXCLUSION_NOT_IN_TEMPLATE = "not_in_template"
_EXCLUSION_ROLE_FORBIDDEN = "role_forbidden"
_EXCLUSION_GLOBAL_FORBIDDEN = "global_forbidden"
_EXCLUSION_MANUAL_ONLY = "manual_only"
_EXCLUSION_GENERATION_EXCLUDED = "generation_excluded"
_EXCLUSION_BUDGET_EXHAUSTED = "budget_exhausted"
_EXCLUSION_MAX_PER_SECTION = "max_per_section_zero"
_EXCLUSION_UNKNOWN_CARD = "unknown_component_card"
_EXCLUSION_PAGE_PSEUDO = "page_pseudo_component"


@dataclass(frozen=True, slots=True)
class RoleCandidateSet:
    """Legal, ordered candidate IDs for one section role after intersection."""

    role: str
    resource_type: str
    template_id: str
    preferred: tuple[str, ...]
    allowed: tuple[str, ...]
    candidates: tuple[str, ...]
    component_budget: dict[str, int]
    max_per_section: dict[str, int]
    excluded: dict[str, str]

    @property
    def is_empty(self) -> bool:
        return not self.candidates


def _planner_component_ids() -> set[str]:
    index = get_planner_index()
    raw = index.get("component_ids") if isinstance(index, dict) else None
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if isinstance(item, str) and item}


def _template_availability(template_id: str) -> tuple[set[str], dict[str, int], dict[str, int]]:
    contract = get_template_contract(template_id)
    if not isinstance(contract, dict):
        raise KeyError(f"Unknown Lectio template_id: {template_id}")
    available_raw = contract.get("available_components") or []
    available = {str(item) for item in available_raw if isinstance(item, str) and item}
    budget_raw = contract.get("component_budget") or {}
    max_raw = contract.get("max_per_section") or {}
    budget = {
        str(key): int(value)
        for key, value in budget_raw.items()
        if isinstance(key, str) and isinstance(value, (int, float))
    }
    max_per_section = {
        str(key): int(value)
        for key, value in max_raw.items()
        if isinstance(key, str) and isinstance(value, (int, float))
    }
    return available, budget, max_per_section


def _is_generation_excluded(component_id: str) -> bool:
    """True when Lectio marks the component off-limits for AI planning.

    ``writer_excluded`` means the generic text writer must not emit the payload;
    visual components remain selectable so the visual lane can execute them.
    """
    if component_id in MANUAL_ONLY_COMPONENT_IDS:
        return True
    card = get_component_card(component_id)
    if not isinstance(card, dict):
        return True
    return False


def _exclusion_reason(
    component_id: str,
    *,
    planner_ids: set[str],
    template_available: set[str],
    role_forbidden: set[str],
    global_forbidden: set[str],
    remaining_budget: Mapping[str, int],
    max_per_section: Mapping[str, int],
) -> str | None:
    if component_id in PAGE_PSEUDO_COMPONENT_IDS:
        return _EXCLUSION_PAGE_PSEUDO
    if component_id in MANUAL_ONLY_COMPONENT_IDS:
        return _EXCLUSION_MANUAL_ONLY
    if component_id not in planner_ids:
        return _EXCLUSION_NOT_IN_PLANNER
    if component_id not in template_available:
        return _EXCLUSION_NOT_IN_TEMPLATE
    if component_id in role_forbidden:
        return _EXCLUSION_ROLE_FORBIDDEN
    if component_id in global_forbidden:
        return _EXCLUSION_GLOBAL_FORBIDDEN
    card = get_component_card(component_id)
    if not isinstance(card, dict):
        return _EXCLUSION_UNKNOWN_CARD
    if _is_generation_excluded(component_id):
        # Prefer the more specific manual_only label when both apply.
        if component_id in MANUAL_ONLY_COMPONENT_IDS:
            return _EXCLUSION_MANUAL_ONLY
        return _EXCLUSION_GENERATION_EXCLUDED
    if component_id in remaining_budget and remaining_budget[component_id] <= 0:
        return _EXCLUSION_BUDGET_EXHAUSTED
    if component_id in max_per_section and max_per_section[component_id] <= 0:
        return _EXCLUSION_MAX_PER_SECTION
    return None


def _filter_ordered(
    ordered_ids: list[str],
    *,
    planner_ids: set[str],
    template_available: set[str],
    role_forbidden: set[str],
    global_forbidden: set[str],
    remaining_budget: Mapping[str, int],
    max_per_section: Mapping[str, int],
    excluded: dict[str, str],
) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for component_id in ordered_ids:
        if component_id in seen:
            continue
        seen.add(component_id)
        reason = _exclusion_reason(
            component_id,
            planner_ids=planner_ids,
            template_available=template_available,
            role_forbidden=role_forbidden,
            global_forbidden=global_forbidden,
            remaining_budget=remaining_budget,
            max_per_section=max_per_section,
        )
        if reason is not None:
            excluded.setdefault(component_id, reason)
            continue
        kept.append(component_id)
    return kept


def resolve_section_candidates(
    section: SectionSpec,
    *,
    spec: ResourceSpec,
    template_id: str = DEFAULT_TEMPLATE_ID,
    remaining_budget: Mapping[str, int] | None = None,
) -> RoleCandidateSet:
    """Intersect one section's preferred/allowed lists with Lectio legality constraints."""
    template_available, template_budget, template_max = _template_availability(template_id)
    planner_ids = _planner_component_ids()
    role_forbidden = set(section.forbidden_components)
    global_forbidden = set(spec.forbidden_components)

    budget: dict[str, int] = dict(template_budget)
    if remaining_budget is not None:
        for key, value in remaining_budget.items():
            budget[str(key)] = int(value)

    excluded: dict[str, str] = {}
    preferred = _filter_ordered(
        list(section.preferred_components),
        planner_ids=planner_ids,
        template_available=template_available,
        role_forbidden=role_forbidden,
        global_forbidden=global_forbidden,
        remaining_budget=budget,
        max_per_section=template_max,
        excluded=excluded,
    )
    preferred_set = set(preferred)
    allowed = [
        component_id
        for component_id in _filter_ordered(
            list(section.allowed_components),
            planner_ids=planner_ids,
            template_available=template_available,
            role_forbidden=role_forbidden,
            global_forbidden=global_forbidden,
            remaining_budget=budget,
            max_per_section=template_max,
            excluded=excluded,
        )
        if component_id not in preferred_set
    ]
    candidates = preferred + allowed

    relevant_budget = {
        component_id: budget[component_id]
        for component_id in candidates
        if component_id in budget
    }
    relevant_max = {
        component_id: template_max[component_id]
        for component_id in candidates
        if component_id in template_max
    }

    return RoleCandidateSet(
        role=section.role,
        resource_type=spec.id,
        template_id=template_id,
        preferred=tuple(preferred),
        allowed=tuple(allowed),
        candidates=tuple(candidates),
        component_budget=relevant_budget,
        max_per_section=relevant_max,
        excluded=dict(sorted(excluded.items())),
    )


def resolve_role_candidates(
    role: str,
    *,
    resource_type: str = PRIMARY_RESOURCE_TYPE,
    template_id: str = DEFAULT_TEMPLATE_ID,
    remaining_budget: Mapping[str, int] | None = None,
    prefer_required: bool = True,
) -> RoleCandidateSet:
    """Resolve candidates for the first matching section with ``role``."""
    spec = get_spec(resource_type)
    sections = (
        [*spec.sections.required, *spec.sections.optional]
        if prefer_required
        else [*spec.sections.optional, *spec.sections.required]
    )
    for section in sections:
        if section.role == role:
            return resolve_section_candidates(
                section,
                spec=spec,
                template_id=template_id,
                remaining_budget=remaining_budget,
            )
    raise KeyError(f"No section with role '{role}' in resource spec '{resource_type}'")


def resolve_required_role_candidates(
    *,
    resource_type: str = PRIMARY_RESOURCE_TYPE,
    template_id: str = DEFAULT_TEMPLATE_ID,
    remaining_budget: Mapping[str, int] | None = None,
) -> dict[str, RoleCandidateSet]:
    """Map each required role to its deterministic candidate set (first occurrence wins)."""
    spec = get_spec(resource_type)
    result: dict[str, RoleCandidateSet] = {}
    for section in spec.sections.required:
        if section.role in result:
            continue
        result[section.role] = resolve_section_candidates(
            section,
            spec=spec,
            template_id=template_id,
            remaining_budget=remaining_budget,
        )
    return result


def iter_spec_component_ids(spec: ResourceSpec) -> list[str]:
    """Stable ordered unique component IDs referenced by preferred/allowed/forbidden lists."""
    ordered: list[str] = []
    seen: set[str] = set()
    for section in [*spec.sections.required, *spec.sections.optional]:
        for field_name in (
            "preferred_components",
            "allowed_components",
            "forbidden_components",
        ):
            for component_id in getattr(section, field_name, []):
                if component_id not in seen:
                    seen.add(component_id)
                    ordered.append(component_id)
    for component_id in spec.forbidden_components:
        if component_id not in seen:
            seen.add(component_id)
            ordered.append(component_id)
    return ordered
