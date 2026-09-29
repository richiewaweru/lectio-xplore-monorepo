from __future__ import annotations

import pytest
from pydantic_ai.models.openai import OpenAIChatModel

from core.llm import ModelFamily, ModelSlot, ModelSpec, build_model
from infra.authoring.model_policy.models import (
    BOUNDARY_CONTINUITY_VALIDATOR,
    DOCUMENT_SEMANTIC_QA,
    SECTION_COMPOSER,
    SHARED_SECTION_WRITER,
    TEACHING_PLAN_SEMANTIC_REVIEWER,
    V2_LESSON_APPROACH_PLANNER,
    V2_PATH_CHAT_EDITOR,
    V2_PATH_PLANNER,
    V2_PATH_STRUCTURAL_PLANNER,
    V3_NODE_REASONING,
    V3_PROPOSE_INTENT,
    SHARED_TASK_AUTHORING,
    V3_VISUAL_QC,
    get_v3_model_settings,
    get_v3_slot,
    get_v3_spec,
)


def test_v3_slot_mapping() -> None:
    assert get_v3_slot("v3_signal_extractor") == ModelSlot.FAST
    assert get_v3_slot("v3_stage1_planner") == ModelSlot.STANDARD
    assert get_v3_slot("v3_section_writer") == ModelSlot.STANDARD
    assert get_v3_slot("v3_answer_key_generator") == ModelSlot.FAST
    assert get_v3_slot("v3_answer_key_generator_heavy") == ModelSlot.STANDARD
    assert get_v3_slot(V3_PROPOSE_INTENT) == ModelSlot.STANDARD
    assert get_v3_slot(SHARED_TASK_AUTHORING) == ModelSlot.STANDARD


def test_get_v3_spec_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "claude-sonnet-test")
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "anthropic")
    spec = get_v3_spec("v3_stage1_planner")
    assert spec.model_name == "claude-sonnet-test"


def test_get_v3_spec_defaults_to_anthropic_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "V3_FAST_PROVIDER",
        "V3_FAST_MODEL_NAME",
        "V3_FAST_BASE_URL",
        "V3_FAST_API_KEY_ENV",
        "V3_STANDARD_PROVIDER",
        "V3_STANDARD_MODEL_NAME",
        "V3_STANDARD_BASE_URL",
        "V3_STANDARD_API_KEY_ENV",
    ):
        monkeypatch.delenv(key, raising=False)

    fast_spec = get_v3_spec("v3_signal_extractor")
    standard_spec = get_v3_spec("v3_stage1_planner")

    assert fast_spec.family == ModelFamily.ANTHROPIC
    assert fast_spec.model_name == "claude-haiku-4-5-20251001"
    assert standard_spec.family == ModelFamily.ANTHROPIC
    assert standard_spec.model_name == "claude-sonnet-4-6"


def test_get_v3_spec_supports_deepseek_slot_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("V3_FAST_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_FAST_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_FAST_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_FAST_API_KEY_ENV", "DEEPSEEK_API_KEY")

    fast_spec = get_v3_spec("v3_signal_extractor")

    assert fast_spec.family == ModelFamily.OPENAI_COMPATIBLE
    assert fast_spec.model_name == "deepseek-flash"
    assert fast_spec.base_url == "https://api.deepseek.com"
    assert fast_spec.api_key_env == "DEEPSEEK_API_KEY"


def test_visual_qc_keeps_vision_default_when_fast_slot_uses_deepseek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_FAST_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_FAST_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_FAST_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_FAST_API_KEY_ENV", "DEEPSEEK_API_KEY")

    spec = get_v3_spec(V3_VISUAL_QC)

    assert spec.family == ModelFamily.ANTHROPIC
    assert spec.model_name == "claude-haiku-4-5-20251001"
    assert spec.api_key_env == "ANTHROPIC_API_KEY"


def test_get_v3_model_settings_omits_reasoning_for_fast_deepseek_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_FAST_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_FAST_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_FAST_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_FAST_API_KEY_ENV", "DEEPSEEK_API_KEY")

    assert get_v3_model_settings("v3_signal_extractor") == {
        "extra_body": {"thinking": {"type": "disabled"}},
        "max_tokens": 8000,
    }


def test_get_v3_model_settings_adds_deepseek_reasoning_for_standard_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")

    settings = get_v3_model_settings("v3_stage1_planner")

    assert settings == {
        "openai_reasoning_effort": "high",
        "extra_body": {"thinking": {"type": "enabled"}},
        "max_tokens": 16000,
    }


def test_constrained_planner_nodes_disable_provider_reasoning() -> None:
    """The structural planner must not run with DeepSeek thinking on.

    Thinking mode returns reasoning-only assistant messages with empty content.
    Replaying one is what produced the observed HTTP 400 "Invalid assistant
    message: content or tool_calls must be set" at planning_forms.
    """
    assert V3_NODE_REASONING[V2_PATH_STRUCTURAL_PLANNER] is False


def test_constrained_output_nodes_disable_provider_reasoning() -> None:
    for node in (
        "v3_section_writer",
        "v3_question_writer",
        "v3_item_executor",
        "v3_constructor",
        "v3_block_writer_standard",
        "v3_answer_key_generator_heavy",
        "v3_blueprint_adjust",
        "v2_merge_critic",
        "v2_path_chat_editor",
        "v3_stage2_expander",
    ):
        assert V3_NODE_REASONING[node] is False


def test_reasoning_policy_can_be_overridden_per_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_SECTION_WRITER_REASONING", "medium")
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")

    settings = get_v3_model_settings("v3_section_writer")

    assert settings is not None
    assert settings["openai_reasoning_effort"] == "medium"


def test_invalid_reasoning_policy_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_SECTION_WRITER_REASONING", "sometimes")
    with pytest.raises(ValueError, match="Invalid reasoning policy"):
        get_v3_model_settings("v3_section_writer")


def test_constrained_planner_nodes_send_no_thinking_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for tier in ("FAST", "STANDARD"):
        monkeypatch.setenv(f"V3_{tier}_PROVIDER", "openai_compatible")
        monkeypatch.setenv(f"V3_{tier}_BASE_URL", "https://api.deepseek.com")
        monkeypatch.setenv(f"V3_{tier}_API_KEY_ENV", "DEEPSEEK_API_KEY")
    monkeypatch.setenv("V3_FAST_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-flash")

    for node in (V2_PATH_STRUCTURAL_PLANNER,):
        settings = get_v3_model_settings(node)
        assert settings == {
            "extra_body": {"thinking": {"type": "disabled"}},
            "max_tokens": 16000,
        }, node
        assert "openai_reasoning_effort" not in settings
        assert settings["extra_body"] == {"thinking": {"type": "disabled"}}


def test_constrained_path_planner_disables_provider_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V2_PATH_PLANNER's constrained JSON route must not enter DeepSeek thinking.

    This is the node that previously held the UI in planning for minutes with
    thinking enabled (see the V3_NODE_REASONING comment). It is distinct from
    V2_LESSON_APPROACH_PLANNER (the shared/V2 Teaching Plan planner), which is
    intentionally enabled for thinking below.
    """
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")

    settings = get_v3_model_settings(V2_PATH_PLANNER)
    assert "openai_reasoning_effort" not in settings
    assert settings["extra_body"] == {"thinking": {"type": "disabled"}}


def test_lesson_approach_planner_enables_provider_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shared/V2 Teaching Plan planner runs with DeepSeek thinking on."""
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")

    settings = get_v3_model_settings(V2_LESSON_APPROACH_PLANNER)
    assert settings == {
        "openai_reasoning_effort": "medium",
        "extra_body": {"thinking": {"type": "enabled"}},
        "max_tokens": 16000,
    }


def test_get_v3_model_settings_preserves_thinking_when_base_sets_extra_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-flash")
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
        "max_tokens": 16000,
    }


def test_get_v3_model_settings_applies_safety_backstop_when_no_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")
    monkeypatch.setenv("V3_MAX_TOKENS_SAFETY", "32000")

    settings = get_v3_model_settings(
        "v3_stage1_planner",
        base_settings={"extra_body": {"response_format": {"type": "json_object"}}},
    )

    assert settings["max_tokens"] == 16000


def test_document_semantic_qa_uses_standard_slot() -> None:
    assert get_v3_slot(DOCUMENT_SEMANTIC_QA) == ModelSlot.STANDARD


def test_thinking_enabled_capabilities_use_deepseek_reasoning() -> None:
    """WORK PACKAGE A: these four capabilities run with DeepSeek thinking on."""
    for node in (
        V2_LESSON_APPROACH_PLANNER,
        TEACHING_PLAN_SEMANTIC_REVIEWER,
        SHARED_SECTION_WRITER,
        DOCUMENT_SEMANTIC_QA,
    ):
        assert V3_NODE_REASONING[node] == "medium", node


def test_thinking_unchanged_capabilities_stay_disabled() -> None:
    """Composer, shared task/sourcebook authoring, and boundary validation
    are explicitly excluded from WORK PACKAGE A and must stay unchanged."""
    for node in (
        SECTION_COMPOSER,
        SHARED_TASK_AUTHORING,
        BOUNDARY_CONTINUITY_VALIDATOR,
        V2_PATH_PLANNER,
        V2_PATH_STRUCTURAL_PLANNER,
        V2_PATH_CHAT_EDITOR,
    ):
        assert V3_NODE_REASONING[node] is False, node


def test_get_v3_model_settings_enables_deepseek_reasoning_for_document_semantic_qa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_STANDARD_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_STANDARD_MODEL_NAME", "deepseek-flash")
    monkeypatch.setenv("V3_STANDARD_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_STANDARD_API_KEY_ENV", "DEEPSEEK_API_KEY")

    settings = get_v3_model_settings(DOCUMENT_SEMANTIC_QA)

    assert settings == {
        "openai_reasoning_effort": "medium",
        "extra_body": {"thinking": {"type": "enabled"}},
        "max_tokens": 16000,
    }


def test_build_model_sets_reasoning_content_profile_for_deepseek() -> None:
    model = build_model(
        ModelSpec(
            family=ModelFamily.OPENAI_COMPATIBLE,
            model_name="deepseek-flash",
            base_url="https://api.deepseek.com",
            api_key_env=None,
        )
    )

    assert isinstance(model, OpenAIChatModel)
    assert model.profile.openai_chat_thinking_field == "reasoning_content"






