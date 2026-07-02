from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import PromptedOutput

from core.llm import ModelFamily, ModelSpec
from v3_execution.llm_helpers import structured_output_type_for_model


class _ExampleModel(BaseModel):
    ok: bool


def test_structured_output_type_wraps_deepseek_models_with_prompted_output() -> None:
    wrapped = structured_output_type_for_model(
        _ExampleModel,
        spec=ModelSpec(
            family=ModelFamily.OPENAI_COMPATIBLE,
            model_name="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
        ),
    )

    assert isinstance(wrapped, PromptedOutput)
    assert wrapped.outputs is _ExampleModel
    assert wrapped.template is not None


def test_structured_output_type_leaves_non_deepseek_models_unchanged() -> None:
    unchanged = structured_output_type_for_model(
        _ExampleModel,
        spec=ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-sonnet-4-6",
        ),
    )

    assert unchanged is _ExampleModel
