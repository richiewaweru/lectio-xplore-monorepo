"""R04 shared fixtures — envelope production and API helpers (MOCK provider labelled)."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringProviderCall
from learn.generation.authoring_adapter import run_learn_work_order_authoring
from learn.generation.native_production import build_closed_learn_production
from learn.generation.preparation_context import LearnPreparationContext
from learn.generation.native_selection import build_learn_selection_snapshot
from learn.generation.ordered_assemble import assemble_ordered_learn_document
from learn.generation.work_orders import compile_learn_work_orders
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash

# Eight core interaction kinds exercised by R04-G05 and envelope production.
CORE_INTERACTIONS = (
    "choice",
    "multi-select",
    "fill-blank",
    "numeric",
    "short-response",
    "match-pairs",
    "classify",
    "sequence",
)

CORE_ACTIONS = {
    "choice": "select-one",
    "multi-select": "select-many",
    "fill-blank": "complete-missing-values",
    "numeric": "enter-number",
    "short-response": "enter-text",
    "match-pairs": "match-pairs",
    "classify": "classify-items",
    "sequence": "order-items",
}

CORE_PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "choice": {
        "options": [{"id": "a", "text": "No light"}, {"id": "b", "text": "Light required"}],
        "correct_option_id": "b",
    },
    "multi-select": {
        "options": [
            {"id": "light", "text": "light"},
            {"id": "co2", "text": "carbon dioxide"},
            {"id": "noise", "text": "noise"},
        ],
        "correct_option_ids": ["light", "co2"],
    },
    "fill-blank": {"answers": ["chlorophyll"], "blank_ids": ["pigment"], "case_sensitive": False},
    "numeric": {"value": 50, "tolerance": 0, "unit": "m"},
    "short-response": {"evaluation": "teacher-review", "review_guidance": "Explain why light is required."},
    "match-pairs": {
        "pairs": [{"left": "lit leaf", "right": "makes food"}, {"left": "covered leaf", "right": "no food"}],
    },
    "classify": {
        "categories": [{"id": "input", "label": "input"}, {"id": "output", "label": "output"}],
        "pairs": [{"left": "light", "right": "input"}, {"left": "sugar", "right": "output"}],
    },
    "sequence": {
        "items": [
            {"id": "light", "label": "Absorb light"},
            {"id": "water", "label": "Split water"},
            {"id": "carbon", "label": "Fix carbon into sugar"},
        ],
        "order": ["light", "water", "carbon"],
    },
}

CONTENT_PAYLOADS: dict[str, dict[str, Any]] = {
    "explanation-block": {"body": "Plants use light energy to make food.", "emphasis": ["light"]},
    "callout-block": {"variant": "info", "body": "Covered leaves cannot make food without light."},
}

R04_PREP = LearnPreparationContext(
    objective="Plants use light to make food through photosynthesis.",
    allowed_facts=[
        "Light is required for food production in leaves.",
        "Covered leaves cannot make food without light.",
    ],
    terminology=["photosynthesis", "chlorophyll"],
)


def _interaction_envelope(capability_id: str, *, prompt: str | None = None) -> dict[str, Any]:
    return {
        "prompt": prompt or f"Student task for {capability_id.replace('-', ' ')}.",
        "config": dict(CORE_PROVIDER_CONFIG[capability_id]),
        "feedback": {"correct": "Correct.", "incorrect": "Try again."},
    }


class R04EnvelopeProvider:
    """MOCK — schema-valid envelope payloads for closed Learn production."""

    def __init__(self) -> None:
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> dict[str, Any]:
        self.calls.append(call)
        if call.capability_id in CORE_PROVIDER_CONFIG:
            return _interaction_envelope(call.capability_id)
        return dict(
            CONTENT_PAYLOADS.get(call.capability_id, CONTENT_PAYLOADS["explanation-block"])
        )


async def _author_all_async(
    orders: list,
    *,
    prep: LearnPreparationContext = R04_PREP,
) -> dict[str, Any]:
    provider = R04EnvelopeProvider()
    lesson_context = {"objective": prep.objective, "subject": "biology"}
    return {
        order.work_order_id: await run_learn_work_order_authoring(
            order,
            provider=provider,
            lesson_context=lesson_context,
            allowed_facts=prep.allowed_facts,
            terminology=prep.terminology,
        )
        for order in orders
    }


def author_all_work_orders(orders: list) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_author_all_async(orders))
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(_author_all_async(orders))).result()


def _block(
    block_id: str,
    *,
    intent: str,
    brief: str,
    action: str | None = None,
    position: int = 0,
) -> TeachingPlanBlock:
    learner = None
    if action is not None:
        learner = LearnerActionBrief(
            action=action,
            support_level="guided",
            evidence=brief,
            source_item_ids=[],
            dependencies=[],
        )
    return TeachingPlanBlock(
        id=block_id,
        position=position,
        intent=intent,
        brief=brief,
        evidence=brief,
        source_question_ids=[],
        learner_action=learner,
    )


def sequence_teaching_plan(*, plan_id: str = "tp-r04-seq") -> TeachingPlan:
    return TeachingPlan(
        arc="R04 sequence fixture",
        teaching_plan_id=plan_id,
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="practice",
                specific_purpose="Order the cycle",
                blocks=[
                    _block("b-intro", intent="explain", brief="Intro prose", position=0),
                    _block(
                        "b-cycle",
                        intent="sequence",
                        brief="Absorb light; Split water; Fix carbon into sugar",
                        action="order-items",
                        position=1,
                    ),
                ],
            )
        ],
    )


def _snapshot(plan: TeachingPlan, *, package_hash: str = "pkg-r04") -> object:
    _, policy_hash = policy_version_and_hash()
    return build_learn_selection_snapshot(
        plan,
        teaching_plan_hash=f"hash-{plan.teaching_plan_id}",
        native_policy_hash=policy_hash,
        package_contract_hash=package_hash,
        policy=default_learn_policy(),
    )


def build_envelope_sequence_document(
    *,
    lesson_id: str = "doc-r04-seq",
    assessment_mode: str = "graded",
    concept_refs: list[dict] | None = None,
) -> dict[str, Any]:
    """Learn document via closed production (MOCK provider), safe inside async tests."""
    document = dict(build_envelope_closed_production_document(title="R04 Sequence"))
    document["id"] = lesson_id
    for block in document["blocks"].values():
        contract = block.get("learn_interaction")
        if not isinstance(contract, dict) or contract.get("kind") != "sequence":
            continue
        contract["assessment_mode"] = assessment_mode
        contract["completion"] = {"type": "submitted"}
        if concept_refs is not None:
            contract["concept_refs"] = concept_refs
        block["component_id"] = "explanation-block"
    return document


def build_envelope_closed_production_document(*, title: str = "R04 closed") -> dict[str, Any]:
    """Full closed production path with MOCK provider."""
    plan = sequence_teaching_plan(plan_id="tp-r04-closed")
    return build_closed_learn_production(
        teaching_plan=plan,
        policy={**default_learn_policy(), "offered_interactions": ["sequence"]},
        title=title,
        provider=R04EnvelopeProvider(),
        preparation_context=R04_PREP,
    )["document"]


def interaction_id(document: dict, *, kind: str = "sequence") -> str:
    for block in document["blocks"].values():
        contract = block.get("learn_interaction")
        if isinstance(contract, dict) and contract.get("kind") == kind:
            return str(contract["id"])
    raise AssertionError(f"no {kind} interaction in document")


def correct_order(document: dict, *, kind: str = "sequence") -> list[str]:
    for block in document["blocks"].values():
        contract = block.get("learn_interaction")
        if isinstance(contract, dict) and contract.get("kind") == kind:
            return list(contract["config"]["order"])
    raise AssertionError(f"no {kind} order in document")


def section_id(document: dict) -> str:
    return str(document["sections"][0]["id"])


R04_USER = SimpleNamespace(id="r04-user", email="r04@example.invalid", name="R04 User")


async def r04_client() -> AsyncClient:
    from app import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def publish_lesson(client: AsyncClient, document: dict, *, title: str = "R04") -> tuple[str, str]:
    created = await client.post(
        "/api/v1/builder/lessons",
        json={"title": title, "document": document},
    )
    assert created.status_code == 201, created.text
    lesson_id = created.json()["id"]
    pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
    assert pub.status_code == 201, pub.text
    return lesson_id, pub.json()["id"]


def install_api_overrides(db_session_factory):
    from app import app
    from core.entities.user import User
    from infra.auth.middleware import get_current_user
    from infra.database.session import get_async_session

    user = User(
        id=R04_USER.id,
        email=R04_USER.email,
        name=R04_USER.name,
        picture_url=None,
        has_profile=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def override_current_user():
        return user

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_async_session] = override_session


async def seed_r04_user(db_session_factory) -> None:
    from core.database.models import UserModel

    async with db_session_factory() as session:
        session.add(UserModel(id=R04_USER.id, email=R04_USER.email, name=R04_USER.name))
        await session.commit()
