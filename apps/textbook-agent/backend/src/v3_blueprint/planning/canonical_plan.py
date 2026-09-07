"""Constrained component selection and code-owned canonical execution plans.

Phase 03: intent plan (empty components) → legal candidates → selection →
validated CanonicalExecutionPlan with stable IDs / revision. No content generation.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Union

from pydantic import BaseModel, ConfigDict, Field

from contracts.lectio import get_component_card, get_template_contract
from resource_specs.component_candidates import (
    DEFAULT_TEMPLATE_ID,
    RoleCandidateSet,
    resolve_role_candidates,
)
from resource_specs.loader import PRIMARY_RESOURCE_TYPE
from v3_blueprint.planning.models import (
    ComponentSlot,
    SectionPlan,
    StructuralPlan,
)

SelectorFn = Callable[[dict[str, Any]], Union["SelectorChoice", Awaitable["SelectorChoice"]]]


class SelectedComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    purpose: str
    reason: str = ""


class SelectorChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    components: list[SelectedComponent] = Field(default_factory=list)
    budget_pressure: str | None = None


class CanonicalBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    section_id: str
    component_id: str
    purpose: str
    position: int
    section_field: str
    work_kind: str  # content | items | visual | answer_key


class CanonicalSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    role: str
    title: str
    purpose: str
    position: int
    visual_required: bool
    card_id: str | None = None
    block_ids: list[str] = Field(default_factory=list)


class CanonicalExecutionPlan(BaseModel):
    """Internal-only execution plan: IDs, selections, budgets — no content."""

    model_config = ConfigDict(extra="forbid")

    generation_id: str | None = None
    lesson_id: str | None = None
    resource_type: str = PRIMARY_RESOURCE_TYPE
    template_id: str = DEFAULT_TEMPLATE_ID
    plan_revision: int = 1
    plan_hash: str
    sections: list[CanonicalSection]
    blocks: list[CanonicalBlock]
    component_budget_remaining: dict[str, int] = Field(default_factory=dict)
    max_per_section: dict[str, int] = Field(default_factory=dict)
    selection_trace: list[dict[str, Any]] = Field(default_factory=list)


@dataclass
class SelectionValidationError(ValueError):
    errors: list[str]

    def __str__(self) -> str:
        return "; ".join(self.errors)


def _lightweight_candidate_metadata(candidate_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for component_id in candidate_ids:
        card = get_component_card(component_id) or {}
        cards.append(
            {
                "component_id": component_id,
                "cognitive_job": card.get("cognitive_job"),
                "section_field": card.get("section_field") or card.get("sectionField"),
                "role": card.get("role"),
                "status": card.get("status"),
                "capabilities": card.get("capabilities") or {},
            }
        )
    return cards


def build_selector_prompt_context(
    *,
    section: SectionPlan,
    candidates: RoleCandidateSet,
    card_context: Mapping[str, Any] | None = None,
    remaining_budget: Mapping[str, int] | None = None,
    lesson_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prompt payload: narrowed candidates only — never full Lectio catalogue or schemas."""
    payload: dict[str, Any] = {
        "slot_id": section.id,
        "slot_purpose": section.purpose or section.title,
        "role": section.role,
        "must_establish": list(section.must_establish),
        "misconception_focus": list(section.misconception_focus),
        "visual_required": section.visual_required,
        "allowed_components": _lightweight_candidate_metadata(candidates.candidates),
        "card": dict(card_context or {}),
        "component_budget": dict(remaining_budget or candidates.component_budget),
        "max_per_section": dict(candidates.max_per_section),
        "remaining_budget": dict(remaining_budget or candidates.component_budget),
    }
    if lesson_context:
        payload["lesson"] = dict(lesson_context)
    return payload


def _section_field_for(component_id: str) -> str | None:
    card = get_component_card(component_id) or {}
    field = card.get("section_field") or card.get("sectionField")
    return field if isinstance(field, str) and field else None


def _work_kind_for(component_id: str) -> str:
    card = get_component_card(component_id) or {}
    if card.get("writer_excluded") is True:
        return "visual"
    caps = card.get("capabilities") or {}
    if caps.get("acceptsQuestions") and component_id in {
        "practice-stack",
        "quiz-check",
        "short-answer",
        "fill-in-blank",
        "student-textbox",
        "reflection-prompt",
    }:
        return "items"
    if component_id == "answer-key" or caps.get("producesAnswerKey"):
        return "answer_key"
    return "content"


def validate_selector_choice(
    choice: SelectorChoice,
    *,
    candidates: RoleCandidateSet,
    remaining_budget: Mapping[str, int] | None = None,
) -> list[str]:
    errors: list[str] = []
    allowed = set(candidates.candidates)
    budget = dict(remaining_budget or candidates.component_budget)
    seen_fields: dict[str, str] = {}
    seen_slugs: set[str] = set()

    if not choice.components:
        errors.append(f"role '{candidates.role}' selection is empty")
    if len(choice.components) > 4:
        errors.append(f"role '{candidates.role}' selected more than 4 components")

    for item in choice.components:
        if item.slug not in allowed:
            errors.append(f"role '{candidates.role}' selected '{item.slug}' outside candidate set")
            continue
        if item.slug in seen_slugs:
            errors.append(f"role '{candidates.role}' duplicated component '{item.slug}'")
        seen_slugs.add(item.slug)
        if not item.purpose.strip():
            errors.append(f"role '{candidates.role}' component '{item.slug}' missing purpose")
        section_field = _section_field_for(item.slug)
        if not section_field:
            errors.append(f"role '{candidates.role}' component '{item.slug}' missing section_field")
        elif section_field in seen_fields:
            errors.append(
                f"role '{candidates.role}' components '{item.slug}' and "
                f"'{seen_fields[section_field]}' share section_field '{section_field}'"
            )
        else:
            seen_fields[section_field] = item.slug
        if item.slug in budget and budget[item.slug] <= 0:
            errors.append(f"role '{candidates.role}' selected '{item.slug}' with exhausted budget")
        if item.slug in candidates.max_per_section:
            cap = candidates.max_per_section[item.slug]
            count = sum(1 for c in choice.components if c.slug == item.slug)
            if count > cap:
                errors.append(f"role '{candidates.role}' exceeds max_per_section for '{item.slug}'")
    return errors


def heuristic_select_components(context: dict[str, Any]) -> SelectorChoice:
    """Deterministic preferred-first selector for tests and offline GO paths."""
    allowed = context.get("allowed_components") or []
    purpose = str(context.get("slot_purpose") or "Perform the section role.")
    misconception_focus = context.get("misconception_focus") or []
    max_per_section = context.get("max_per_section") or {}
    budget = dict(context.get("component_budget") or {})

    selected: list[SelectedComponent] = []
    used_fields: set[str] = set()

    def try_add(component_id: str, reason: str) -> bool:
        if component_id in {item.slug for item in selected}:
            return False
        if component_id in budget and budget[component_id] <= 0:
            return False
        if component_id in max_per_section and max_per_section[component_id] <= 0:
            return False
        field = None
        for card in allowed:
            if card.get("component_id") == component_id:
                field = card.get("section_field")
                break
        if not isinstance(field, str) or field in used_fields:
            return False
        used_fields.add(field)
        selected.append(
            SelectedComponent(
                slug=component_id,
                purpose=f"{purpose} via {component_id}",
                reason=reason,
            )
        )
        if component_id in budget:
            budget[component_id] -= 1
        return True

    # Misconception-shaped roles prefer inoculation over comparison when focus is set.
    if misconception_focus:
        try_add("pitfall-alert", "misconception_focus → inoculation")
    for card in allowed:
        component_id = card.get("component_id")
        if not isinstance(component_id, str):
            continue
        if len(selected) >= 2:
            break
        try_add(component_id, f"cognitive_job={card.get('cognitive_job')}")

    if not selected and allowed:
        first = allowed[0].get("component_id")
        if isinstance(first, str):
            try_add(first, "fallback first candidate")

    return SelectorChoice(components=selected, budget_pressure=None)


def _stable_section_id(role: str, index: int, existing: str | None) -> str:
    if existing and existing.strip():
        return existing.strip()
    return f"{role}-{index + 1}"


def _stable_block_id(section_id: str, component_id: str, position: int) -> str:
    return f"{section_id}__{component_id}__{position}"


def _plan_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _selector_inputs_for_section(
    *,
    plan: StructuralPlan,
    section: SectionPlan,
    resource_type: str,
    template_id: str,
    budget: dict[str, int],
    lesson_context: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], RoleCandidateSet]:
    card_by_id = {card.id: card for card in plan.cards}
    candidates = resolve_role_candidates(
        section.role,
        resource_type=resource_type,
        template_id=template_id,
        remaining_budget=budget,
    )
    card = card_by_id.get(section.card_id) if section.card_id else None
    card_context = (
        {
            "id": card.id,
            "objective": card.objective,
            "misconceptions": [m.model_dump() for m in card.misconceptions],
            "prereqs": list(card.prereqs),
        }
        if card is not None
        else {}
    )
    context = build_selector_prompt_context(
        section=section,
        candidates=candidates,
        card_context=card_context,
        remaining_budget=budget,
        lesson_context=lesson_context,
    )
    return context, candidates


def _preselected_choice(section: SectionPlan) -> SelectorChoice:
    return SelectorChoice(
        components=[
            SelectedComponent(slug=c.slug, purpose=c.purpose, reason="preselected")
            for c in section.components
        ]
    )


def _finalize_canonical_plan(
    plan: StructuralPlan,
    selections: dict[str, SelectorChoice],
    *,
    generation_id: str | None,
    lesson_id: str | None,
    resource_type: str,
    template_id: str,
    plan_revision: int,
    budget: dict[str, int],
    selection_inputs: Mapping[str, dict[str, Any]],
) -> tuple[CanonicalExecutionPlan, StructuralPlan]:
    filled = apply_selection_to_structural_plan(plan, selections)
    canonical_sections: list[CanonicalSection] = []
    canonical_blocks: list[CanonicalBlock] = []

    for index, section in enumerate(filled.sections):
        section_id = _stable_section_id(section.role, index, section.id)
        block_ids: list[str] = []
        for position, component in enumerate(section.components):
            block_id = _stable_block_id(section_id, component.slug, position)
            block_ids.append(block_id)
            field = _section_field_for(component.slug) or "unknown"
            canonical_blocks.append(
                CanonicalBlock(
                    block_id=block_id,
                    section_id=section_id,
                    component_id=component.slug,
                    purpose=component.purpose,
                    position=position,
                    section_field=field,
                    work_kind=_work_kind_for(component.slug),
                )
            )
        canonical_sections.append(
            CanonicalSection(
                section_id=section_id,
                role=section.role,
                title=section.title,
                purpose=section.purpose,
                position=index,
                visual_required=section.visual_required,
                card_id=section.card_id,
                block_ids=block_ids,
            )
        )

    template = get_template_contract(template_id) or {}
    hash_payload = {
        "generation_id": generation_id,
        "lesson_id": lesson_id,
        "resource_type": resource_type,
        "template_id": template_id,
        "plan_revision": plan_revision,
        "sections": [s.model_dump() for s in canonical_sections],
        "blocks": [b.model_dump() for b in canonical_blocks],
    }
    selection_trace: list[dict[str, Any]] = []
    blocks_by_section_component = {
        (block.section_id, block.component_id): block for block in canonical_blocks
    }
    for index, section in enumerate(plan.sections):
        section_id = _stable_section_id(section.role, index, section.id)
        choice = selections[section.id]
        trace_input = selection_inputs.get(section.id, {})
        selected: list[dict[str, Any]] = []
        for item in choice.components:
            block = blocks_by_section_component.get((section_id, item.slug))
            selected.append(
                {
                    "component_id": item.slug,
                    "purpose": item.purpose,
                    "reason": item.reason,
                    "block_id": block.block_id if block is not None else None,
                    "lane": block.work_kind if block is not None else None,
                    "section_field": block.section_field if block is not None else None,
                }
            )
        selection_trace.append(
            {
                "section_id": section_id,
                "role": section.role,
                "intent": section.purpose or section.title,
                "candidate_set": list(trace_input.get("candidate_set") or []),
                "budget_before": dict(trace_input.get("budget_before") or {}),
                "selected": selected,
                "budget_pressure": choice.budget_pressure,
                "legal": True,
            }
        )

    canonical = CanonicalExecutionPlan(
        generation_id=generation_id,
        lesson_id=lesson_id,
        resource_type=resource_type,
        template_id=template_id,
        plan_revision=plan_revision,
        plan_hash=_plan_hash(hash_payload),
        sections=canonical_sections,
        blocks=canonical_blocks,
        component_budget_remaining=budget,
        max_per_section={
            str(key): int(value) for key, value in (template.get("max_per_section") or {}).items()
        },
        selection_trace=selection_trace,
    )
    return canonical, filled


def apply_selection_to_structural_plan(
    plan: StructuralPlan,
    selections: Mapping[str, SelectorChoice],
) -> StructuralPlan:
    """Fill ComponentSlot lists from validated selections (mutates a deep copy)."""
    updated = plan.model_copy(deep=True)
    for section in updated.sections:
        choice = selections.get(section.id)
        if choice is None:
            continue
        section.components = [
            ComponentSlot(slug=item.slug, purpose=item.purpose) for item in choice.components
        ]
    return updated


def _initial_budget(
    template_id: str,
    remaining_budget: Mapping[str, int] | None,
) -> dict[str, int]:
    template = get_template_contract(template_id) or {}
    budget = {
        str(key): int(value) for key, value in (template.get("component_budget") or {}).items()
    }
    if remaining_budget is not None:
        budget.update({str(k): int(v) for k, v in remaining_budget.items()})
    return budget


def build_canonical_execution_plan(
    plan: StructuralPlan,
    *,
    generation_id: str | None = None,
    lesson_id: str | None = None,
    resource_type: str = PRIMARY_RESOURCE_TYPE,
    template_id: str = DEFAULT_TEMPLATE_ID,
    plan_revision: int = 1,
    selector: SelectorFn | None = None,
    remaining_budget: Mapping[str, int] | None = None,
    lesson_context: Mapping[str, Any] | None = None,
) -> tuple[CanonicalExecutionPlan, StructuralPlan]:
    """Intent StructuralPlan → validated selections → canonical plan + filled StructuralPlan."""
    select = selector or heuristic_select_components
    budget = _initial_budget(template_id, remaining_budget)
    selections: dict[str, SelectorChoice] = {}
    selection_inputs: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for section in plan.sections:
        if section.components:
            choice = _preselected_choice(section)
            selection_inputs[section.id] = {
                "candidate_set": [component.slug for component in section.components],
                "budget_before": dict(budget),
            }
        else:
            context, candidates = _selector_inputs_for_section(
                plan=plan,
                section=section,
                resource_type=resource_type,
                template_id=template_id,
                budget=budget,
                lesson_context=lesson_context,
            )
            choice = select(context)
            if inspect.isawaitable(choice):
                raise TypeError("Async selector requires build_canonical_execution_plan_async")
            errors.extend(
                validate_selector_choice(
                    choice,
                    candidates=candidates,
                    remaining_budget=budget,
                )
            )
            selection_inputs[section.id] = {
                "candidate_set": list(candidates.candidates),
                "budget_before": dict(budget),
            }
            for item in choice.components:
                if item.slug in budget:
                    budget[item.slug] = max(0, budget[item.slug] - 1)
        selections[section.id] = choice

    if errors:
        raise SelectionValidationError(errors)
    return _finalize_canonical_plan(
        plan,
        selections,
        generation_id=generation_id,
        lesson_id=lesson_id,
        resource_type=resource_type,
        template_id=template_id,
        plan_revision=plan_revision,
        budget=budget,
        selection_inputs=selection_inputs,
    )


async def build_canonical_execution_plan_async(
    plan: StructuralPlan,
    *,
    generation_id: str | None = None,
    lesson_id: str | None = None,
    resource_type: str = PRIMARY_RESOURCE_TYPE,
    template_id: str = DEFAULT_TEMPLATE_ID,
    plan_revision: int = 1,
    selector: SelectorFn | None = None,
    remaining_budget: Mapping[str, int] | None = None,
    lesson_context: Mapping[str, Any] | None = None,
) -> tuple[CanonicalExecutionPlan, StructuralPlan]:
    """Async variant: production semantic selector may await an LLM."""
    select = selector or heuristic_select_components
    budget = _initial_budget(template_id, remaining_budget)
    selections: dict[str, SelectorChoice] = {}
    selection_inputs: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for section in plan.sections:
        if section.components:
            choice = _preselected_choice(section)
            selection_inputs[section.id] = {
                "candidate_set": [component.slug for component in section.components],
                "budget_before": dict(budget),
            }
        else:
            context, candidates = _selector_inputs_for_section(
                plan=plan,
                section=section,
                resource_type=resource_type,
                template_id=template_id,
                budget=budget,
                lesson_context=lesson_context,
            )
            raw = select(context)
            choice = await raw if inspect.isawaitable(raw) else raw
            errors.extend(
                validate_selector_choice(
                    choice,
                    candidates=candidates,
                    remaining_budget=budget,
                )
            )
            selection_inputs[section.id] = {
                "candidate_set": list(candidates.candidates),
                "budget_before": dict(budget),
            }
            for item in choice.components:
                if item.slug in budget:
                    budget[item.slug] = max(0, budget[item.slug] - 1)
        selections[section.id] = choice

    if errors:
        raise SelectionValidationError(errors)
    return _finalize_canonical_plan(
        plan,
        selections,
        generation_id=generation_id,
        lesson_id=lesson_id,
        resource_type=resource_type,
        template_id=template_id,
        plan_revision=plan_revision,
        budget=budget,
        selection_inputs=selection_inputs,
    )
