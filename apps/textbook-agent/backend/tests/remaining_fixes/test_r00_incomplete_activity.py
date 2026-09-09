"""R00 regression: numeric generate must preserve provider-authored question and feedback."""

from __future__ import annotations

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringEngine, AuthoringProviderCall, AuthoringRequest
from learn.generation.authoring_adapter import run_learn_work_order_authoring
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.work_orders import compile_learn_work_orders
from learn.runtime.evaluation import evaluate_numeric


PLANNING_BRIEF = "Create a distance calculation using speed and time"
SCOPED_FACTS = [
    "Speed v equals 5 m/s.",
    "Time t equals 10 s.",
    "Distance d equals v times t.",
]
EXPECTED_STUDENT_QUESTION = (
    "A cyclist travels at 5 m/s for 10 seconds. How far does she travel?"
)
EXPECTED_FEEDBACK_INCORRECT = (
    "Multiply speed by time: distance equals v times t, so 5 times 10 equals 50 metres."
)
EXPECTED_ANSWER = 50


class CaptureEngine(AuthoringEngine):
    captured: AuthoringRequest | None = None

    async def execute(self, request: AuthoringRequest, *, provider=None):
        CaptureEngine.captured = request
        return await super().execute(request, provider=provider)


class NumericProvider:
    async def invoke(self, call: AuthoringProviderCall) -> dict[str, object]:
        return {"value": EXPECTED_ANSWER, "tolerance": 0, "unit": "m"}


def _numeric_order() -> object:
    plan = TeachingPlan(
        arc="Distance with speed and time",
        teaching_plan_id="tp-r00-numeric",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="practice",
                specific_purpose="Calculate distance",
                blocks=[
                    TeachingPlanBlock(
                        id="b-numeric",
                        position=0,
                        intent="check-understanding",
                        brief=PLANNING_BRIEF,
                        evidence="Learner calculates distance from speed and time.",
                        learner_action=LearnerActionBrief(
                            action="enter-number",
                            support_level="guided",
                            evidence="Learner calculates distance from speed and time.",
                        ),
                    )
                ],
            )
        ],
    )
    snapshot = LearnSelectionSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=1,
        teaching_plan_hash="hash-r00-numeric",
        native_policy_hash="policy-r00",
        package_contract_hash="pkg-r00",
        decisions=[LearnSelectionDecision(block_id="b-numeric", interaction_id="numeric")],
    ).seal()
    return compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)[0]


@pytest.mark.asyncio
async def test_r00_numeric_generate_preserves_provider_question_feedback_and_facts() -> None:
    """Scenario 1 partial: brief is context; student question, feedback and facts must survive."""
    order = _numeric_order()
    engine = CaptureEngine(
        registry=__import__(
            "learn.generation.authoring_adapter",
            fromlist=["build_learn_authoring_registry"],
        ).build_learn_authoring_registry(),
        provider=NumericProvider(),
    )

    result = await run_learn_work_order_authoring(
        order,
        engine=engine,
        allowed_facts=SCOPED_FACTS,
    )
    contract = result.payload
    request = CaptureEngine.captured
    assert request is not None

    assert request.inputs["allowed_facts"] == SCOPED_FACTS
    assert contract["config"]["value"] == EXPECTED_ANSWER
    assert contract["prompt"] == EXPECTED_STUDENT_QUESTION
    assert EXPECTED_FEEDBACK_INCORRECT in str(contract["feedback"]["incorrect"])

    correct = evaluate_numeric(contract, {"value": EXPECTED_ANSWER})
    incorrect = evaluate_numeric(contract, {"value": 5})
    assert correct.outcome == "correct"
    assert incorrect.outcome == "incorrect"
