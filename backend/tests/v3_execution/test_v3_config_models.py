from __future__ import annotations

import pytest
from pydantic_ai.models.openai import OpenAIChatModel

from core.llm import ModelFamily, ModelSlot, ModelSpec, build_model
from v3_execution.config.answer_key_node import effective_answer_key_node_name
from v3_execution.config.models import (
    V3_ANSWER_KEY_GENERATOR,
    V3_ANSWER_KEY_GENERATOR_HEAVY,
    get_v3_model_settings,
    get_v3_slot,
    get_v3_spec,
)
from v3_execution.models import AnswerKeyExecutorWorkOrder, AnswerKeyPlanSpec, WriterQuestion


def test_v3_slot_mapping() -> None:
    assert get_v3_slot("v3_signal_extractor") == ModelSlot.FAST
    assert get_v3_slot("v3_stage1_planner") == ModelSlot.STANDARD
    assert get_v3_slot("v3_section_writer") == ModelSlot.STANDARD
    assert get_v3_slot("v3_answer_key_generator") == ModelSlot.FAST
    assert get_v3_slot("v3_answer_key_generator_heavy") == ModelSlot.STANDARD


def test_get_v3_spec_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "claude-sonnet-test")
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "anthropic")
    spec = get_v3_spec("v3_stage1_planner")
    assert spec.model_name == "claude-sonnet-test"


def test_get_v3_model_settings_omits_reasoning_for_fast_deepseek_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_FAST_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_FAST_MODEL_NAME", "deepseek-v4-flash")
    monkeypatch.setenv("V3_FAST_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_FAST_API_KEY_ENV", "DEEPSEEK_API_KEY")

    assert get_v3_model_settings("v3_signal_extractor") == {"max_tokens": 120000}


def test_get_v3_model_settings_adds_deepseek_reasoning_for_standard_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-v4-pro")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")

    settings = get_v3_model_settings("v3_stage1_planner")

    assert settings == {
        "openai_reasoning_effort": "high",
        "extra_body": {"thinking": {"type": "enabled"}},
        "max_tokens": 120000,
    }


def test_get_v3_model_settings_preserves_thinking_when_base_sets_extra_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-v4-pro")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")

    settings = get_v3_model_settings(
        "v3_stage1_planner",
        base_settings={
            "extra_body": {"response_format": {"type": "json_object"}},
        },
    )

    assert settings == {
        "openai_reasoning_effort": "high",
        "extra_body": {
            "thinking": {"type": "enabled"},
            "response_format": {"type": "json_object"},
        },
        "max_tokens": 120000,
    }


def test_get_v3_model_settings_applies_safety_backstop_when_no_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-v4-pro")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")
    monkeypatch.setenv("V3_MAX_TOKENS_SAFETY", "120000")

    settings = get_v3_model_settings(
        "v3_stage1_planner",
        base_settings={"extra_body": {"response_format": {"type": "json_object"}}},
    )

    assert settings["max_tokens"] == 120000


def test_build_model_sets_reasoning_content_profile_for_deepseek() -> None:
    model = build_model(
        ModelSpec(
            family=ModelFamily.OPENAI_COMPATIBLE,
            model_name="deepseek-v4-pro",
            base_url="https://api.deepseek.com",
            api_key_env=None,
        )
    )

    assert isinstance(model, OpenAIChatModel)
    assert model.profile.openai_chat_thinking_field == "reasoning_content"


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
