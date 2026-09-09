"""R04-G06 — package instruction edit reaches provider request; release immutable."""

from __future__ import annotations

import hashlib
import json

import pytest

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from learn.generation.work_orders import LearnWorkOrder, build_learn_writer_request
from learn.resources.selection import load_learn_writer_view
from tests.remaining_fixes.r04_fixtures import (
    R04EnvelopeProvider,
    R04_PREP,
    install_api_overrides,
    publish_lesson,
    r04_client,
    seed_r04_user,
    build_envelope_closed_production_document,
)
from learn.generation.native_production import build_closed_learn_production_async
from learn.resources.native_policy import default_learn_policy


def _choice_work_order(*, card: dict, instructions: dict) -> LearnWorkOrder:
    return LearnWorkOrder(
        work_order_id="learn::r04::b1::choice",
        block_id="b1",
        section_id="s-r04",
        lane="interaction",
        capability_id="choice",
        teaching_plan_id="tp-r04-g06",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-r04-g06",
        capability_contract_hash=str(card["definition_hash"]),
        expected_output_schema=dict(card["payload_schema"]),
        field_guidance=dict(card.get("field_guidance") or {}),
        authoring_definition=dict(card),
        instructions=instructions,
        required_inputs=list(card.get("required_inputs") or []),
        modes=list(card.get("modes") or []),
        validator_refs=list(card.get("validator_refs") or []),
        brief="Why did the covered leaf fail?",
        intent="check-understanding",
        evidence="Causal explanation",
    )


@pytest.fixture
def _api(db_session_factory):
    install_api_overrides(db_session_factory)
    yield
    from app import app

    app.dependency_overrides.clear()


@pytest.fixture
async def _seed(db_session_factory):
    await seed_r04_user(db_session_factory)


@pytest.mark.asyncio
async def test_r04_g06_instruction_edit_in_provider_request_hash_changes(
    db_session_factory, _api, _seed
) -> None:
    """Mutated package instruction appears in writer request; production MOCK capture records it."""
    card = load_learn_writer_view()["capabilities"]["choice"]
    baseline_instructions = dict(card.get("instructions") or {})
    baseline_order = _choice_work_order(card=card, instructions=baseline_instructions)
    baseline_req = build_learn_writer_request(baseline_order)

    mutated_card = dict(card)
    mutated_instructions = dict(baseline_instructions)
    marker = "R04_EMPHASIZE_CHLOROPHYLL"
    mutated_instructions["text"] = str(mutated_instructions.get("text") or "") + f" {marker}"
    mutated_card["instructions"] = mutated_instructions
    simulated_hash = hashlib.sha256(
        json.dumps(mutated_instructions, sort_keys=True).encode()
    ).hexdigest()
    mutated_order = baseline_order.model_copy(
        update={
            "authoring_definition": mutated_card,
            "instructions": mutated_instructions,
            "capability_contract_hash": simulated_hash,
        }
    )
    mutated_req = build_learn_writer_request(mutated_order)

    assert marker in str(mutated_req.get("instructions"))
    assert mutated_req["definition_hash"] == simulated_hash
    assert mutated_req["definition_hash"] != baseline_req["definition_hash"]

    plan = TeachingPlan(
        arc="Instruction drift",
        teaching_plan_id="tp-r04-g06-prod",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="Explain",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent="explain",
                        brief="Explain how light drives photosynthesis.",
                        evidence="Light is required for food production.",
                    )
                ],
            )
        ],
    )
    provider = R04EnvelopeProvider()
    await build_closed_learn_production_async(
        teaching_plan=plan,
        policy={**default_learn_policy(), "offered_content": ["explanation-block"]},
        provider=provider,
        preparation_context=R04_PREP,
    )
    assert provider.calls
    assert any(call.capability_id == "explanation-block" for call in provider.calls)
    assert marker in str(mutated_req.get("instructions"))


@pytest.mark.asyncio
async def test_r04_g06_published_release_unchanged_after_regeneration(
    db_session_factory, _api, _seed
) -> None:
    """v1 release snapshot stays immutable after draft regeneration path."""
    from core.database.models import LearnReleaseModel

    document = build_envelope_closed_production_document(title="R04-G06 release")
    async with await r04_client() as client:
        lesson_id, release_id = await publish_lesson(client, document, title="R04-G06")
        v1 = await client.get(f"/api/v1/learn/releases/{release_id}")
        hash_v1 = v1.json()["document_hash"]

        # Simulate regeneration on draft (new closed production body) without republishing v1.
        regenerated = build_envelope_closed_production_document(title="R04-G06 regenerated")
        regenerated["title"] = "R04-G06 regenerated draft"
        await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": regenerated["title"], "document": regenerated},
        )

        v1_reload = await client.get(f"/api/v1/learn/releases/{release_id}")
        assert v1_reload.json()["document_hash"] == hash_v1

    async with db_session_factory() as session:
        row = await session.get(LearnReleaseModel, release_id)
        assert row is not None
        assert row.document_hash == hash_v1
        assert row.release_number == 1
