"""Native page-block planning for Xplore v2 documents.

Feature-flagged. Fixture/mocked by default (no paid LLM).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from resource_specs.candidates import IntentCandidate, resolve_block_candidates
from resource_specs.loader import get_spec
from v3_blueprint.planning.models import PlannedBlock, SectionBlockPlan
from v3_blueprint.skeletons import load_skeleton_catalog

FIRST_SLICE_OBJECTS = frozenset(
    {"prose", "list", "table", "figure", "worked-example", "questions"}
)
CONCEPTUAL_FIRST_EXPOSURE_SLOTS = ("orient", "explain", "contrast", "confront", "check")


class PageBlockPlanError(ValueError):
    pass


def page_document_scope_matches(
    *,
    knowledge_type: str,
    lesson_mode: str,
    scope: str = "conceptual_first_exposure",
) -> bool:
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


def candidates_for_slot(slot_id: str) -> tuple[IntentCandidate, ...]:
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


def validate_block_plan_against_candidates(
    plan: SectionBlockPlan,
    candidates: tuple[IntentCandidate, ...],
    *,
    min_blocks: int = 1,
    max_blocks: int = 3,
) -> None:
    if plan.slot_concern:
        if plan.blocks:
            raise PageBlockPlanError("slot_concern requires empty blocks")
        return
    if not (min_blocks <= len(plan.blocks) <= max_blocks):
        raise PageBlockPlanError(
            f"block count {len(plan.blocks)} outside [{min_blocks}, {max_blocks}]"
        )
    allowed: dict[str, set[str]] = {
        intent.id: {obj.id for obj in intent.objects} for intent in candidates
    }
    for index, block in enumerate(plan.blocks):
        if block.position != index:
            raise PageBlockPlanError(f"position mismatch at {index}")
        if block.object == "heading":
            raise PageBlockPlanError("heading blocks are forbidden in first slice")
        if block.intent not in allowed:
            raise PageBlockPlanError(f"intent {block.intent!r} not in closed candidates")
        if block.object not in allowed[block.intent]:
            raise PageBlockPlanError(
                f"pair ({block.intent!r}, {block.object!r}) not in closed candidates"
            )
        if not block.evidence.strip() or not block.brief.strip():
            raise PageBlockPlanError("evidence and brief must be specific non-empty strings")


def _fixture_plan_for_slot(slot_id: str) -> SectionBlockPlan:
    """Deterministic fixture planner used when paid LLM tests are disabled."""
    # Prefer the authority example only when it validates against this slot's candidates.
    monorepo = Path(__file__).resolve().parents[5]
    example = (
        monorepo
        / "docs"
        / "authority"
        / "xplore-pageobject-authority"
        / "examples"
        / "conceptual-first-exposure.planned.json"
    )
    candidates = candidates_for_slot(slot_id)
    catalog = load_skeleton_catalog()
    slot = catalog.slots[slot_id]
    min_blocks = int(slot.get("min_blocks") or 1)
    max_blocks = int(slot.get("max_blocks") or 3)
    if example.exists():
        try:
            planned = SectionBlockPlan.model_validate(json.loads(example.read_text(encoding="utf-8")))
            validate_block_plan_against_candidates(
                planned, candidates, min_blocks=min_blocks, max_blocks=max_blocks
            )
            return planned
        except (PageBlockPlanError, ValueError, json.JSONDecodeError):
            pass

    first = candidates[0]
    obj = first.objects[0]
    block = PlannedBlock(
        id=f"{slot_id}-b1-{obj.id}",
        position=0,
        intent=first.id,
        object=obj.id,  # type: ignore[arg-type]
        evidence=f"Fixture chose {first.id} because it is the first closed candidate for {slot_id}.",
        brief=f"Write a {obj.id} block for the {slot_id} section that fulfils intent {first.id}.",
        source_question_ids=["q-fixture-1"] if obj.id == "questions" else [],
    )
    return SectionBlockPlan(blocks=[block])

async def plan_section_blocks(
    *,
    slot_id: str,
    context: Mapping[str, Any] | None = None,
    planner: Callable[..., Any] | None = None,
    allow_paid: bool = False,
) -> SectionBlockPlan:
    """Plan one section. Uses fixture planner unless an explicit planner is injected."""
    del context  # reserved for LLM payload assembly
    candidates = candidates_for_slot(slot_id)
    catalog = load_skeleton_catalog()
    slot = catalog.slots[slot_id]
    min_blocks = int(slot.get("min_blocks") or 1)
    max_blocks = int(slot.get("max_blocks") or 3)

    if planner is not None:
        raw = await planner(slot_id=slot_id, candidates=candidates)
        plan = SectionBlockPlan.model_validate(raw)
    elif allow_paid:
        raise PageBlockPlanError(
            "Paid section-block planner is not enabled in this environment; "
            "set ALLOW_PAID_LLM_TESTS=1 and provide a planner agent"
        )
    else:
        plan = _fixture_plan_for_slot(slot_id)

    validate_block_plan_against_candidates(
        plan, candidates, min_blocks=min_blocks, max_blocks=max_blocks
    )
    return plan


async def plan_conceptual_first_exposure_blocks(
    *,
    allow_paid: bool = False,
    planner: Callable[..., Any] | None = None,
) -> dict[str, SectionBlockPlan]:
    """Plan all conceptual first-exposure slots without invoking component selector."""
    plans: dict[str, SectionBlockPlan] = {}
    for slot_id in CONCEPTUAL_FIRST_EXPOSURE_SLOTS:
        plans[slot_id] = await plan_section_blocks(
            slot_id=slot_id,
            allow_paid=allow_paid,
            planner=planner,
        )
    return plans
