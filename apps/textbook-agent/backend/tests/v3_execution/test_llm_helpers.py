from __future__ import annotations

from pydantic import BaseModel

from core.config import settings
from core.llm import ModelFamily, ModelSpec
from pydantic_ai import PromptedOutput, ToolOutput
from v3_execution.llm_helpers import (
    get_structured_mode,
    structured_output_for_model,
)


class _ExampleModel(BaseModel):
    ok: bool


def _deepseek_spec() -> ModelSpec:
    return ModelSpec(
        family=ModelFamily.OPENAI_COMPATIBLE,
        model_name="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
    )


def test_deepseek_prompted_json_uses_prompted_output(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_structured_mode", "prompted_json")
    wrapped, _source, context = structured_output_for_model(
        output_type=_ExampleModel,
        spec=_deepseek_spec(),
    )
    assert isinstance(wrapped, PromptedOutput)
    assert context.structured_mode == "prompted_json"
    assert context.strict_fallback is True


def test_deepseek_strict_tool_uses_tool_output(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_structured_mode", "strict_tool")
    wrapped, _source, context = structured_output_for_model(
        output_type=_ExampleModel,
        spec=_deepseek_spec(),
        structured_mode="strict_tool",
    )
    assert isinstance(wrapped, ToolOutput)
    assert wrapped.strict is True
    assert context.structured_mode == "strict_tool"
    assert context.strict_fallback is False


def test_non_deepseek_models_keep_native_output_type() -> None:
    unchanged, _source, _context = structured_output_for_model(
        output_type=_ExampleModel,
        spec=ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-sonnet-4-6",
        ),
    )
    assert unchanged is _ExampleModel


def test_get_structured_mode_defaults_to_prompted_json(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_structured_mode", "prompted_json")
    assert get_structured_mode() == "prompted_json"
