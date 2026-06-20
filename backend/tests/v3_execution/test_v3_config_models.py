from __future__ import annotations

import pytest

from core.llm import ModelSlot
from v3_execution.config.answer_key_node import effective_answer_key_node_name
from v3_execution.config.models import (
    V3_ANSWER_KEY_GENERATOR,
    V3_ANSWER_KEY_GENERATOR_HEAVY,
    get_v3_slot,
    get_v3_spec,
)
from v3_execution.models import AnswerKeyExecutorWorkOrder, AnswerKeyPlanSpec, WriterQuestion


def test_v3_slot_mapping() -> None:
    assert get_v3_slot("v3_signal_extractor") == ModelSlot.FAST
    assert get_v3_slot("v3_stage1_planner") == ModelSlot.PREMIUM
    assert get_v3_slot("v3_section_writer") == ModelSlot.STANDARD
    assert get_v3_slot("v3_answer_key_generator") == ModelSlot.FAST
    assert get_v3_slot("v3_answer_key_generator_heavy") == ModelSlot.STANDARD


def test_get_v3_spec_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("V3_PREMIUM_MODEL_NAME", "claude-opus-test")
    monkeypatch.setenv("V3_PREMIUM_PROVIDER", "anthropic")
    spec = get_v3_spec("v3_stage1_planner")
    assert spec.model_name == "claude-opus-test"


def test_answer_key_effective_node_fast_when_answers_present() -> None:
    order = AnswerKeyExecutorWorkOrder(
        work_order_id="w1",
        questions=[
            WriterQuestion(
                id="q1",
                difficulty="warm",
                expected_answer="42",
                expected_working="x=42",
            )
        ],
        answer_key_plan=AnswerKeyPlanSpec(
            style="full_working",
            include_question_ids=["q1"],
        ),
    )
    assert effective_answer_key_node_name(order) == V3_ANSWER_KEY_GENERATOR


def test_answer_key_escalates_when_expected_missing() -> None:
    order = AnswerKeyExecutorWorkOrder(
        work_order_id="w1",
        questions=[
            WriterQuestion(
                id="q1",
                difficulty="warm",
                expected_answer="",
                expected_working=None,
            )
        ],
        answer_key_plan=AnswerKeyPlanSpec(
            style="answers_only",
            include_question_ids=["q1"],
        ),
    )
    assert effective_answer_key_node_name(order) == V3_ANSWER_KEY_GENERATOR_HEAVY


def test_answer_key_escalates_full_working_without_working() -> None:
    order = AnswerKeyExecutorWorkOrder(
        work_order_id="w1",
        questions=[
            WriterQuestion(
                id="q1",
                difficulty="warm",
                expected_answer="42",
                expected_working=None,
            )
        ],
        answer_key_plan=AnswerKeyPlanSpec(
            style="full_working",
            include_question_ids=["q1"],
        ),
    )
    assert effective_answer_key_node_name(order) == V3_ANSWER_KEY_GENERATOR_HEAVY
