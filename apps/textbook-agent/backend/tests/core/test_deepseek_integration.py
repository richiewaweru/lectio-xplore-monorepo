from __future__ import annotations

import pytest

from core.config import settings
from core.llm import ModelFamily, ModelSpec, build_structured_model
from pydantic import BaseModel
from pydantic_ai import ToolOutput
from v3_execution.llm_helpers import prepare_structured_agent


class _SpikeModel(BaseModel):
    title: str
    count: int = 3
    optional_note: str | None = None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_deepseek_strict_typed_schema() -> None:
    if not settings.allow_paid_llm_tests:
        pytest.skip("set ALLOW_PAID_LLM_TESTS=true to run live DeepSeek integration tests")
    import os

    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not set")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("V3_FAST_PROVIDER", "openai_compatible")
    monkeypatch.setenv("V3_FAST_MODEL_NAME", "deepseek-v4-flash")
    monkeypatch.setenv("V3_FAST_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("V3_FAST_API_KEY_ENV", "DEEPSEEK_API_KEY")
    monkeypatch.setenv("DEEPSEEK_STRUCTURED_MODE", "strict_tool")

    from pydantic_ai import Agent
    from core.llm.runner import RetryPolicy, run_llm
    from v3_execution.config import get_v3_slot, get_v3_model_settings
    from v3_execution.config.models import V3_SIGNAL_EXTRACTOR

    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=V3_SIGNAL_EXTRACTOR,
        output_type=_SpikeModel,
        structured_mode="strict_tool",
    )
    assert isinstance(provider_output, ToolOutput)
    assert structured_context.structured_mode == "strict_tool"

    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt="Return JSON only.",
        retries={"output": 0},
    )
    result = await run_llm(
        trace_id="deepseek-strict-spike",
        caller="integration_test",
        generation_id=None,
        agent=agent,
        user_prompt='Return {"title":"ok","count":3,"optional_note":null}',
        model=model,
        slot=get_v3_slot(V3_SIGNAL_EXTRACTOR),
        spec=spec,
        node=V3_SIGNAL_EXTRACTOR,
        model_settings=get_v3_model_settings(V3_SIGNAL_EXTRACTOR),
        retry_policy=RetryPolicy(max_attempts=1, call_timeout_seconds=60.0),
        structured_context=structured_context,
    )
    validated = _SpikeModel.model_validate(result.output)
    assert validated.title == "ok"
    monkeypatch.undo()


def test_prepare_structured_agent_uses_beta_model_for_deepseek_strict() -> None:
    import os

    os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
    spec = ModelSpec(
        family=ModelFamily.OPENAI_COMPATIBLE,
        model_name="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
    )
    model = build_structured_model(spec, structured_mode="strict_tool")
    assert "api.deepseek.com/beta" in str(getattr(model, "base_url", ""))
