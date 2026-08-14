"""Native page-block legality for whole-lesson teaching plans.

Closed candidate fences and fixture planners are removed. Intent legality uses
permitted / typical / excluded with departure_reason rules (v1.1 §8.1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from resource_specs.candidates import (
    IntentCandidate,
    SlotGuidance,
    assemble_slot_guidance,
    resolve_block_candidates,
)
from resource_specs.loader import get_spec
from v3_blueprint.planning.models import SectionBlockPlan
from v3_blueprint.skeletons import load_skeleton_catalog

FIRST_SLICE_OBJECTS = frozenset(
    {"prose", "list", "table", "figure", "worked-example", "questions"}
)
CONCEPTUAL_FIRST_EXPOSURE_SLOTS = ("orient", "explain", "confront", "check")


class PageBlockPlanError(ValueError):
    pass


def page_document_scope_matches(
    *,
    knowledge_type: str,
    lesson_mode: str,
    scope: str = "conceptual_first_exposure",
) -> bool:
    if scope == "all":
        return True
    if scope == "conceptual_first_exposure":
        return knowledge_type == "conceptual" and lesson_mode == "first_exposure"
    return False


def _catalogues() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    contracts = Path(__file__).resolve().parents[2] / "contracts" / "lectio-page"
    intents = json.loads((contracts / "intent-catalogue.v1.json").read_text(encoding="utf-8"))[
        "intents"
    ]
    objects = json.loads((contracts / "object-catalogue.v1.json").read_text(encoding="utf-8"))[
        "objects"
    ]
    return intents, objects


def guidance_for_slot(slot_id: str) -> SlotGuidance:
    intents, objects = _catalogues()
    spec = get_spec("lesson")
    catalog = load_skeleton_catalog()
    slot = dict(catalog.slots[slot_id])
    slot["slot_id"] = slot_id
    return assemble_slot_guidance(
        resource_spec=spec,
        skeleton_slot=slot,
        intent_catalogue=intents,
        object_catalogue=objects,
        implemented_objects=set(FIRST_SLICE_OBJECTS),
    )


def candidates_for_slot(slot_id: str) -> tuple[IntentCandidate, ...]:
    """Return permitted intents that still expose at least one object."""
    intents, objects = _catalogues()
    spec = get_spec("lesson")
    catalog = load_skeleton_catalog()
    slot = dict(catalog.slots[slot_id])
    slot["slot_id"] = slot_id
    return resolve_block_candidates(
        resource_spec=spec,
        skeleton_slot=slot,
        intent_catalogue=intents,
        object_catalogue=objects,
        implemented_objects=set(FIRST_SLICE_OBJECTS),
    )


def intent_is_atypical(*, intent: str, typical_intents: set[str] | frozenset[str]) -> bool:
    """from_typical is computed by code: atypical when intent not in typical_intents."""
    return intent not in typical_intents


def validate_intent_departure(
    *,
    intent: str,
    typical_intents: set[str] | frozenset[str],
    permitted_intents: set[str] | frozenset[str],
    excluded_intents: set[str] | frozenset[str],
    departure_reason: str | None,
) -> None:
    if intent in excluded_intents:
        raise PageBlockPlanError(f"intent {intent!r} is excluded")
    if intent not in permitted_intents:
        raise PageBlockPlanError(f"intent {intent!r} is not permitted")
    # Patch 01 permissive architecture: slots with no typical_intents steering may
    # still use any permitted intent without a departure_reason. Creativity stays
    # inside permitted/excluded bounds; incomplete YAML must not block the gate.
    if not typical_intents:
        return
    atypical = intent_is_atypical(intent=intent, typical_intents=typical_intents)
    reason = (departure_reason or "").strip()
    if atypical and not reason:
        raise PageBlockPlanError(
            f"intent {intent!r} is atypical for this slot and requires departure_reason"
        )
    if not atypical and reason:
        raise PageBlockPlanError(
            f"intent {intent!r} is typical; departure_reason must be empty"
        )


def validate_block_plan_against_guidance(
    plan: SectionBlockPlan,
    guidance: SlotGuidance,
    *,
    min_blocks: int = 1,
    max_blocks: int = 3,
    require_objects: bool = True,
) -> None:
    if plan.slot_concern:
        if plan.blocks:
            raise PageBlockPlanError("slot_concern requires empty blocks")
        return
    if not (min_blocks <= len(plan.blocks) <= max_blocks):
        raise PageBlockPlanError(
            f"block count {len(plan.blocks)} outside [{min_blocks}, {max_blocks}]"
        )
    permitted = {intent.id: intent for intent in guidance.permitted_intents}
    typical = set(guidance.typical_intents)
    excluded = {intent_id for intent_id, _ in guidance.excluded_intents}
    for index, block in enumerate(plan.blocks):
        if block.position != index:
            raise PageBlockPlanError(f"position mismatch at {index}")
        if block.object == "heading":
            raise PageBlockPlanError("heading blocks are forbidden in first slice")
        departure = getattr(block, "departure_reason", None)
        validate_intent_departure(
            intent=block.intent,
            typical_intents=typical,
            permitted_intents=set(permitted.keys()),
            excluded_intents=excluded,
            departure_reason=departure,
        )
        intent_row = permitted[block.intent]
        allowed_objects = {obj.id for obj in intent_row.objects}
        if require_objects and block.object not in allowed_objects:
            raise PageBlockPlanError(
                f"pair ({block.intent!r}, {block.object!r}) is not compatible"
            )
        if not block.evidence.strip() or not block.brief.strip():
            raise PageBlockPlanError("evidence and brief must be specific non-empty strings")


def validate_block_plan_against_candidates(
    plan: SectionBlockPlan,
    candidates: tuple[IntentCandidate, ...],
    *,
    min_blocks: int = 1,
    max_blocks: int = 3,
) -> None:
    """Compatibility wrapper around departure-rule validation."""
    typical = tuple(intent.id for intent in candidates if getattr(intent, "typical", False))
    if not typical:
        typical = tuple(intent.id for intent in candidates)
    guidance = SlotGuidance(
        slot_id="compat",
        typical_intents=typical,
        permitted_intents=candidates,
        excluded_intents=(),
    )
    validate_block_plan_against_guidance(
        plan,
        guidance,
        min_blocks=min_blocks,
        max_blocks=max_blocks,
        require_objects=True,
    )
