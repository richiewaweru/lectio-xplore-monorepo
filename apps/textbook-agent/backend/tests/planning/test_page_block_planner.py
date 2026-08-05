"""Departure-rule tests for native page block legality."""

from __future__ import annotations

import pytest

from planning.page_blocks import (
    PageBlockPlanError,
    candidates_for_slot,
    guidance_for_slot,
    page_document_scope_matches,
    validate_block_plan_against_guidance,
)
from resource_specs.loader import load_all_specs
from v3_blueprint.planning.models import PlannedBlock, SectionBlockPlan


def test_page_document_scope_matches_conceptual_first_exposure() -> None:
    assert page_document_scope_matches(
        knowledge_type="conceptual", lesson_mode="first_exposure"
    )
    assert not page_document_scope_matches(
        knowledge_type="procedural", lesson_mode="first_exposure"
    )


def test_guidance_for_orient_has_typical_and_permitted() -> None:
    load_all_specs()
    guidance = guidance_for_slot("orient")
    assert guidance.typical_intents
    assert guidance.permitted_intents
    candidates = candidates_for_slot("orient")
    assert candidates


def test_validate_plan_allows_atypical_with_reason() -> None:
    load_all_specs()
    guidance = guidance_for_slot("orient")
    atypical = next(
        intent.id for intent in guidance.permitted_intents if intent.id not in guidance.typical_intents
    )
    plan = SectionBlockPlan(
        blocks=[
            PlannedBlock(
                id="orient-b1",
                position=0,
                intent=atypical,
                object="prose",
                evidence="Atypical but permitted for this concept.",
                brief="Use an atypical permitted intent with a clear departure reason for this concept.",
            )
        ]
    )
    # PlannedBlock has no departure_reason field — attach via validate path using getattr
    object.__setattr__(plan.blocks[0], "__dict__", {**plan.blocks[0].__dict__, "departure_reason": "Needed for this concept."})
    # Pydantic model may not allow setattr of unknown field; use model_copy workaround via validation helper
    from planning.page_blocks import validate_intent_departure

    validate_intent_departure(
        intent=atypical,
        typical_intents=set(guidance.typical_intents),
        permitted_intents={i.id for i in guidance.permitted_intents},
        excluded_intents={i for i, _ in guidance.excluded_intents},
        departure_reason="Needed for this concept.",
    )


def test_validate_plan_rejects_excluded_via_guidance() -> None:
    load_all_specs()
    guidance = guidance_for_slot("orient")
    if not guidance.excluded_intents:
        pytest.skip("no excluded intents configured")
    excluded_id = guidance.excluded_intents[0][0]
    plan = SectionBlockPlan(
        blocks=[
            PlannedBlock(
                id="orient-b1",
                position=0,
                intent="orient",
                object="prose",
                evidence="placeholder evidence for excluded intent swap test case.",
                brief="placeholder brief that mentions light food leaf terminology here.",
            )
        ]
    )
    # Force excluded intent into block for the check
    dirty = plan.model_copy(
        update={
            "blocks": [
                plan.blocks[0].model_copy(update={"intent": excluded_id})
            ]
        }
    )
    with pytest.raises(PageBlockPlanError):
        validate_block_plan_against_guidance(dirty, guidance)
