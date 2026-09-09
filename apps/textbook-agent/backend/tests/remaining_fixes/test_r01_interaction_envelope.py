"""R01 gates: complete interaction authoring envelope (prompt, config, feedback)."""

from __future__ import annotations

import pytest

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringEngine, AuthoringProviderCall
from learn.generation.authoring_adapter import run_learn_work_order_authoring
from learn.generation.interaction_writer import InteractionWriterError, write_interaction_from_request
from learn.generation.native_production import build_closed_learn_production
from learn.generation.native_selection import LearnSelectionDecision, LearnSelectionSnapshot
from learn.generation.work_orders import compile_learn_work_orders
from learn.resources.native_policy import default_learn_policy
from learn.runtime.evaluation import evaluate_interaction
from tests.authoring_correction.test_a04_learn_authoring import (
    CORE_CONFIG,
    _interaction_envelope,
    _request,
)

PLANNING_BRIEF = "Create a distance calculation using speed and time"
STUDENT_PROMPT = "A cyclist travels at 5 m/s for 10 seconds. How far does she travel?"
FEEDBACK_INCORRECT = (
    "Multiply speed by time: distance equals v times t, so 5 times 10 equals 50 metres."
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


class EnvelopeProvider:
    """Returns full activity envelopes with distinct prompt and feedback."""

    def __init__(self, *, prompt: str = STUDENT_PROMPT, feedback_incorrect: str = FEEDBACK_INCORRECT) -> None:
        self.prompt = prompt
        self.feedback_incorrect = feedback_incorrect
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> dict[str, object]:
        self.calls.append(call)
        if call.capability_id == "numeric":
            return {
                "prompt": self.prompt,
                "config": {"value": 50, "tolerance": 0, "unit": "m"},
                "feedback": {
                    "correct": "Correct — the distance is 50 metres.",
                    "incorrect": self.feedback_incorrect,
                },
                "id": "model-should-not-own",
                "assessment_mode": "graded",
            }
        if call.capability_id in CORE_CONFIG:
            return _interaction_envelope(
                call.capability_id,
                prompt=self.prompt,
                feedback={"correct": "Correct.", "incorrect": self.feedback_incorrect},
            )
        if call.capability_id == "explanation-block":
            return {"body": "Distance equals speed multiplied by time.", "emphasis": ["distance"]}
        return {"variant": "info", "body": "Context."}


def _numeric_order() -> object:
    plan = TeachingPlan(
        arc="Distance with speed and time",
        teaching_plan_id="tp-r01-numeric",
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
        teaching_plan_hash="hash-r01-numeric",
        native_policy_hash="policy-r01",
        package_contract_hash="pkg-r01",
        decisions=[LearnSelectionDecision(block_id="b-numeric", interaction_id="numeric")],
    ).seal()
    return compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)[0]


@pytest.mark.asyncio
async def test_r01_g01_provider_prompt_feedback_survive_work_order_authoring() -> None:
    """R01-G01: authored prompt/config/feedback survive run_learn_work_order_authoring."""
    provider = EnvelopeProvider()
    order = _numeric_order()
    result = await run_learn_work_order_authoring(order, provider=provider)
    contract = result.payload

    assert contract["prompt"] == STUDENT_PROMPT
    assert contract["prompt"] != PLANNING_BRIEF
    assert FEEDBACK_INCORRECT in contract["feedback"]["incorrect"]
    assert contract["config"]["value"] == 50


def test_r01_g01_provider_prompt_feedback_survive_closed_production() -> None:
    """R01-G01: authored prompt survives build_closed_learn_production."""
    plan = TeachingPlan(
        arc="Distance",
        teaching_plan_id="tp-r01-prod",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="practice",
                blocks=[
                    TeachingPlanBlock(
                        id="b1",
                        position=0,
                        intent="check-understanding",
                        brief=PLANNING_BRIEF,
                        evidence="Calculate distance.",
                        learner_action=LearnerActionBrief(
                            action="enter-number",
                            support_level="guided",
                            evidence="Calculate distance.",
                        ),
                    )
                ],
            )
        ],
    )
    policy = default_learn_policy()
    policy["offered_interactions"] = ["numeric"]
    provider = EnvelopeProvider()

    production = build_closed_learn_production(teaching_plan=plan, policy=policy, provider=provider)
    block = next(iter(production["document"]["blocks"].values()))
    interaction = block["learn_interaction"]

    assert interaction["prompt"] == STUDENT_PROMPT
    assert interaction["prompt"] != PLANNING_BRIEF
    assert FEEDBACK_INCORRECT in interaction["feedback"]["incorrect"]


def test_r01_g02_convert_preserves_approved_stem() -> None:
    """R01-G02: convert-approved uses approved stem, not planning brief."""
    approved = {
        "id": "choice-r01",
        **CORE_CONFIG["choice"],
        "correct_key": "b",
        "stem": "Which process turns liquid water into vapour?",
    }
    contract = write_interaction_from_request(
        _request("choice", action="select-one", approved_items=[approved]),
    )
    assert contract["prompt"] == "Which process turns liquid water into vapour?"
    assert contract["prompt"] != "Author choice"


def test_r01_g02_missing_stem_fails_without_brief_fallback() -> None:
    """R01-G02: missing approved stem raises INCOMPATIBLE_APPROVED_ITEM."""
    approved = {
        "id": "choice-r01-missing",
        **CORE_CONFIG["choice"],
        "correct_key": "b",
    }
    with pytest.raises(InteractionWriterError, match="INCOMPATIBLE_APPROVED_ITEM|stem"):
        write_interaction_from_request(
            _request("choice", action="select-one", approved_items=[approved]),
        )


def test_r01_g03_model_trusted_fields_stripped() -> None:
    """R01-G03: model-supplied id/assessment_mode do not override assembly."""
    provider = EnvelopeProvider()
    contract = write_interaction_from_request(
        _request("numeric", action="enter-number"),
        provider=provider,
    )
    assert contract["id"].startswith("ix-")
    assert contract["id"] != "model-should-not-own"
    assert contract["assessment_mode"] == "practice"
    assert "concept_refs" not in contract["config"]


@pytest.mark.parametrize("capability_id", list(CORE_CONFIG.keys()))
def test_r01_g04_core_interactions_generate_and_convert(capability_id: str) -> None:
    """R01-G04: each core interaction passes generate and convert with canonical config."""
    action = CORE_ACTIONS[capability_id]
    provider = EnvelopeProvider(prompt=f"Question for {capability_id}?")

    generated = write_interaction_from_request(
        _request(capability_id, action=action),
        provider=provider,
    )
    assert generated["config"] == CORE_CONFIG[capability_id]
    assert generated["prompt"] == f"Question for {capability_id}?"

    approved: dict[str, object] = {
        "id": f"{capability_id}-approved",
        **CORE_CONFIG[capability_id],
        "stem": f"Approved stem for {capability_id}?",
    }
    if capability_id == "choice":
        approved["correct_key"] = approved.pop("correct_option_id")
    elif capability_id == "multi-select":
        approved["correct_keys"] = approved.pop("correct_option_ids")
    elif capability_id == "classify":
        approved["mapping"] = {pair["left"]: pair["right"] for pair in CORE_CONFIG["classify"]["pairs"]}
    elif capability_id == "sequence":
        approved["correct_order"] = CORE_CONFIG["sequence"]["order"]
        approved.pop("items", None)
        approved.pop("order", None)
    elif capability_id == "match-pairs":
        approved["pairs"] = {p["left"]: p["right"] for p in CORE_CONFIG["match-pairs"]["pairs"]}
    elif capability_id == "short-response":
        approved.pop("evaluation", None)
        approved.pop("review_guidance", None)
    elif capability_id == "fill-blank":
        approved["blank_ids"] = CORE_CONFIG["fill-blank"]["blank_ids"]

    converted = write_interaction_from_request(
        _request(capability_id, action=action, approved_items=[approved]),
    )
    assert converted["prompt"] == f"Approved stem for {capability_id}?"
    if capability_id == "short-response":
        assert converted["config"]["evaluation"] == "teacher-review"
        assert converted["config"]["review_guidance"] == f"Approved stem for {capability_id}?"
    else:
        assert converted["config"] == CORE_CONFIG[capability_id]

    if capability_id == "short-response":
        result = evaluate_interaction(converted, {"text": "Light drives photosynthesis."})
        assert result.outcome == "pending-review"
    elif capability_id == "choice":
        result = evaluate_interaction(converted, {"selected_option_id": "b"})
        assert result.outcome == "correct"
    elif capability_id == "multi-select":
        result = evaluate_interaction(
            converted,
            {"selected_option_ids": CORE_CONFIG["multi-select"]["correct_option_ids"]},
        )
        assert result.outcome == "correct"
