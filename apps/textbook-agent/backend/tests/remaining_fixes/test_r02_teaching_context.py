"""R02 gates G04–G05: pinned teaching context and mode-specific validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from infra.authoring import AuthoringEngineError, AuthoringProviderCall
from learn.generation.authoring_adapter import author_learn_work_orders, run_learn_authoring
from learn.generation.native_production import build_closed_learn_production
from learn.generation.preparation_context import (
    LearnPreparationContext,
    learn_preparation_context_from_state,
)
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.work_orders import compile_learn_work_orders
from learn.resources.native_policy import default_learn_policy


PREP_FACTS = [
    "Speed v equals 5 m/s.",
    "Time t equals 10 s.",
    "Distance d equals v times t.",
]


class ContentProvider:
    async def invoke(self, call: AuthoringProviderCall) -> dict[str, object]:
        if call.capability_id == "explanation-block":
            return {"body": "Distance equals speed multiplied by time.", "emphasis": ["distance"]}
        return {"variant": "info", "body": "Use v, t and d equals v times t."}


def _explain_order() -> object:
    plan = TeachingPlan(
        arc="Distance from speed and time",
        teaching_plan_id="tp-r02-context",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent="explain",
                        brief="Explain how to calculate distance from speed and time.",
                        evidence="Learner uses v, t and d equals v times t.",
                    )
                ],
            )
        ],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=1,
        teaching_plan_hash="hash-r02-context",
        native_policy_hash="policy-r02",
        package_contract_hash="pkg-r02",
        decisions=[LearnSelectionDecision(block_id="b-explain", content_id="explanation-block")],
    ).seal()
    return compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)[0]


def test_r02_g04_preparation_context_from_pinned_state() -> None:
    """R02-G04: shared preparation packet supplies objective, facts, terminology, level."""
    state = {
        "shared_preparation_packet": {
            "objective": "Calculate distance from speed and time",
            "prior_established": PREP_FACTS[:2],
            "must_establish": [PREP_FACTS[2]],
            "scope_contract": {"terminology": ["speed", "distance"]},
            "groups": [{"profile": "core"}],
            "prerequisites": [{"path_lesson_id": "prior-1", "objective": "Know speed units"}],
            "lesson_actuals": [{"concept_id": "c1", "established": True}],
        }
    }
    prep = learn_preparation_context_from_state(state)
    assert prep.objective == "Calculate distance from speed and time"
    assert prep.allowed_facts == PREP_FACTS
    assert prep.terminology == ["speed", "distance"]
    assert prep.learner_level == "core"
    assert prep.dependency_results


@pytest.mark.asyncio
async def test_r02_g04_closed_production_threads_preparation() -> None:
    """R02-G04: build_closed_learn_production passes pinned facts to author_learn_work_orders."""
    plan = TeachingPlan(
        arc="Distance from speed and time",
        teaching_plan_id="tp-r02-prod",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent="explain",
                        brief="Explain distance.",
                        evidence="Use v, t and d.",
                    )
                ],
            )
        ],
    )
    policy = default_learn_policy()
    policy["offered_content"] = ["explanation-block"]
    captured: dict[str, object] = {}

    async def spy(*args, **kwargs):
        captured.update(kwargs)
        return await author_learn_work_orders(*args, **kwargs)

    prep = LearnPreparationContext(objective="Calculate distance", allowed_facts=PREP_FACTS, terminology=["speed"])
    with patch("learn.generation.native_production.author_learn_work_orders", spy):
        build_closed_learn_production(
            teaching_plan=plan,
            policy=policy,
            provider=ContentProvider(),
            preparation_context=prep,
        )

    assert captured["allowed_facts"] == PREP_FACTS
    assert captured["terminology"] == ["speed"]
    lesson_context = captured["lesson_context"]
    assert isinstance(lesson_context, dict)
    assert lesson_context.get("objective") == "Calculate distance"


@pytest.mark.asyncio
async def test_r02_g05_blank_objective_fails_before_provider() -> None:
    """R02-G05: generate with blank objective raises MISSING_AUTHORING_INPUT."""
    order = _explain_order()
    with pytest.raises(AuthoringEngineError, match="MISSING_AUTHORING_INPUT"):
        await run_learn_authoring(
            order,
            lesson_context={"objective": "   "},
            allowed_facts=PREP_FACTS,
        )


@pytest.mark.asyncio
async def test_r02_g05_empty_facts_fail_for_generate() -> None:
    """R02-G05: generate with empty allowed_facts raises MISSING_AUTHORING_INPUT."""
    order = _explain_order()
    with pytest.raises(AuthoringEngineError, match="MISSING_AUTHORING_INPUT"):
        await run_learn_authoring(
            order,
            lesson_context={"objective": "Explain distance"},
            allowed_facts=[],
        )


def test_r02_g05_convert_succeeds_without_duplicated_facts() -> None:
    """R02-G05: convert-approved does not require allowed_facts duplication."""
    approved = {
        "id": "choice-r02",
        **{"options": [{"id": "a", "text": "freezing"}, {"id": "b", "text": "evaporation"}]},
        "correct_key": "b",
        "stem": "What is evaporation?",
    }
    from learn.generation.interaction_writer import write_interaction_from_request
    from tests.authoring_correction.test_a04_learn_authoring import _request

    contract = write_interaction_from_request(
        _request("choice", action="select-one", approved_items=[approved]),
    )
    assert contract["prompt"] == "What is evaporation?"


@pytest.mark.asyncio
async def test_r02_g05_empty_terminology_allowed_for_generate() -> None:
    """R02-G05: empty terminology is valid when facts and objective are present."""
    order = _explain_order()
    engine = __import__(
        "learn.generation.authoring_adapter",
        fromlist=["build_learn_authoring_registry"],
    ).build_learn_authoring_registry()
    from infra.authoring import AuthoringEngine

    selected = AuthoringEngine(registry=engine, provider=ContentProvider())
    result = await run_learn_authoring(
        order,
        engine=selected,
        lesson_context={"objective": "Explain distance"},
        allowed_facts=PREP_FACTS,
        terminology=[],
    )
    assert result.mode == "generate"
