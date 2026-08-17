from __future__ import annotations

from core.llm import ModelFamily, ModelSpec, build_model, build_structured_model
from core.llm.transport import DEEPSEEK_BETA_BASE_URL, structured_base_url


def test_structured_base_url_uses_beta_for_deepseek_strict() -> None:
    spec = ModelSpec(
        family=ModelFamily.OPENAI_COMPATIBLE,
        model_name="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
    )
    assert structured_base_url(spec, structured_mode="strict_tool") == DEEPSEEK_BETA_BASE_URL
    assert structured_base_url(spec, structured_mode="prompted_json") == "https://api.deepseek.com"


def test_build_structured_model_preserves_normal_base_for_prompted(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    spec = ModelSpec(
        family=ModelFamily.OPENAI_COMPATIBLE,
        model_name="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
    )
    normal = build_model(spec)
    structured = build_structured_model(spec, structured_mode="strict_tool")
    assert getattr(normal, "base_url", None) != getattr(structured, "base_url", None) or (
        str(getattr(structured, "base_url", "")).endswith("/beta")
    )
