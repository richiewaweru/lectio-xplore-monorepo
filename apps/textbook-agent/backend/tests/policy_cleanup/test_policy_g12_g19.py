"""Policy cleanup v4 — G12 repair/resume and G19 dual-path policy identity."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from infra.authoring import AuthoringEngine, AuthoringProviderCall, AuthoringValidationError
from learn.generation.authoring_adapter import (
    build_learn_authoring_registry,
    run_learn_authoring,
)
from learn.generation.native_production import build_closed_learn_production
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.preparation_context import LearnPreparationContext
from learn.generation.work_orders import compile_learn_work_orders
from learn.resources.native_policy import default_learn_policy
from tests.remaining_fixes.r04_fixtures import (
    build_envelope_closed_production_document,
    install_api_overrides,
    publish_lesson,
    r04_client,
    seed_r04_user,
)


EVAP_FACT = (
    "Evaporation changes liquid water into water vapour and can occur below boiling point."
)


class RepairThenOkProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []

    async def invoke(self, call: AuthoringProviderCall) -> dict[str, Any]:
        self.calls += 1
        self.prompts.append(call.prompt)
        if self.calls == 1:
            return {"body": "", "emphasis": []}  # invalid → repair
        return {
            "body": "Evaporation turns liquid water into vapour.",
            "emphasis": ["evaporation"],
        }


@pytest.mark.asyncio
async def test_g12_repair_preserves_policy_in_prompt() -> None:
    plan = TeachingPlan(
        arc="Explain evaporation",
        teaching_plan_id="tp-g12",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                blocks=[
                    TeachingPlanBlock(
                        id="b1",
                        position=0,
                        intent="explain",
                        brief="Explain evaporation.",
                        evidence="Learner explains.",
                    )
                ],
            )
        ],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=1,
        teaching_plan_hash="h",
        native_policy_hash="p",
        package_contract_hash="c",
        decisions=[LearnSelectionDecision(block_id="b1", content_id="explanation-block")],
    ).seal()
    order = compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)[0]
    provider = RepairThenOkProvider()
    engine = AuthoringEngine(registry=build_learn_authoring_registry(), provider=provider)
    result = await run_learn_authoring(
        order,
        engine=engine,
        provider=provider,
        lesson_context={"objective": "Explain evaporation"},
        allowed_facts=[EVAP_FACT],
        requested_knowledge_policy="supplied_preferred",
    )
    assert result.provenance.policy["effective_knowledge_policy"] == "supplied_preferred"
    assert any("resolved_policy" in p or "KNOWLEDGE POLICY" in p for p in provider.prompts)
    # Provider cannot alter trusted mode — policy remains code-owned
    assert result.provenance.policy["policy_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_g19_saved_learn_document_retains_policy_identity(
    db_session_factory,
) -> None:
    """Closed Learn production persists policy on interaction provenance; reload via publish."""
    install_api_overrides(db_session_factory)
    await seed_r04_user(db_session_factory)
    document = build_envelope_closed_production_document(title="Policy G19")
    # Stamp policy on any short-response or first interaction
    for block in document["blocks"].values():
        contract = block.get("learn_interaction")
        if isinstance(contract, dict):
            contract.setdefault("provenance", {})
            contract["provenance"]["policy"] = {
                "policy_version": "1.0.0",
                "effective_knowledge_policy": "supplied_preferred",
                "effective_assessment_policy": "automatic_preferred",
                "definition_hash": contract.get("provenance", {}).get("definition_hash"),
                "input_revision": "prep-rev-g19",
            }
            break

    async with await r04_client() as client:
        lesson_id, release_id = await publish_lesson(client, document, title="Policy G19")
        reloaded = await client.get(f"/api/v1/learn/releases/{release_id}")
        assert reloaded.status_code == 200
        found = False
        for block in reloaded.json()["document"]["blocks"].values():
            contract = block.get("learn_interaction")
            if isinstance(contract, dict) and contract.get("provenance", {}).get("policy"):
                policy = contract["provenance"]["policy"]
                assert policy["policy_version"] == "1.0.0"
                assert policy["effective_knowledge_policy"] == "supplied_preferred"
                assert policy.get("input_revision") == "prep-rev-g19"
                found = True
                break
        assert found

    from app import app

    app.dependency_overrides.clear()
