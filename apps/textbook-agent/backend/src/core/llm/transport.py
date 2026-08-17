from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.profiles.openai import OpenAIModelProfile

from core.llm.deepseek_schema import DeepSeekJsonSchemaTransformer
from core.llm.types import ModelFamily, ModelSpec

DEEPSEEK_BETA_BASE_URL = "https://api.deepseek.com/beta"
StructuredMode = str  # "strict_tool" | "prompted_json"

_OPENAI_COMPATIBLE_SYSTEMS = {
    "openai",
    "openai-chat",
    "openai-responses",
    "alibaba",
    "azure",
    "cerebras",
    "deepseek",
    "fireworks",
    "github",
    "grok",
    "heroku",
    "litellm",
    "moonshotai",
    "nebius",
    "ollama",
    "openrouter",
    "ovhcloud",
    "sambanova",
    "together",
    "vercel",
}


def _normalize_family(raw: str) -> ModelFamily:
    value = raw.strip().lower()
    if value == "anthropic":
        return ModelFamily.ANTHROPIC
    if value in {"google", "gemini"}:
        return ModelFamily.GOOGLE
    if value in {"openai_compatible", "openai-compatible", "openai"}:
        return ModelFamily.OPENAI_COMPATIBLE
    if value == "test":
        return ModelFamily.TEST
    raise ValueError(
        f"Unsupported model family '{raw}'. "
        "Expected one of: anthropic, google, openai_compatible."
    )


def _read_api_key(spec: ModelSpec) -> str | None:
    if spec.api_key_env is None:
        return None
    api_key = os.getenv(spec.api_key_env)
    if not api_key:
        raise ValueError(
            f"Model spec for '{spec.model_name}' expects env var "
            f"'{spec.api_key_env}', but it is not set."
        )
    return api_key


def _build_anthropic_model(spec: ModelSpec):
    api_key = _read_api_key(spec)
    if api_key is None and spec.base_url is None:
        return AnthropicModel(spec.model_name)

    from pydantic_ai.providers.anthropic import AnthropicProvider

    provider = AnthropicProvider(api_key=api_key, base_url=spec.base_url)
    return AnthropicModel(spec.model_name, provider=provider)


def _build_google_model(spec: ModelSpec):
    api_key = _read_api_key(spec)
    if api_key is None and spec.base_url is None:
        return GoogleModel(spec.model_name)

    from pydantic_ai.providers.google import GoogleProvider

    provider = GoogleProvider(api_key=api_key, base_url=spec.base_url)
    return GoogleModel(spec.model_name, provider=provider)


def is_deepseek_spec(spec: ModelSpec) -> bool:
    return (
        spec.family == ModelFamily.OPENAI_COMPATIBLE
        and spec.model_name.startswith("deepseek-")
    )


def structured_base_url(spec: ModelSpec, *, structured_mode: StructuredMode) -> str | None:
    if is_deepseek_spec(spec) and structured_mode == "strict_tool":
        return DEEPSEEK_BETA_BASE_URL
    return spec.base_url


def _deepseek_profile(*, structured_mode: StructuredMode) -> OpenAIModelProfile:
    if structured_mode == "strict_tool":
        return OpenAIModelProfile(
            openai_chat_thinking_field="reasoning_content",
            json_schema_transformer=DeepSeekJsonSchemaTransformer,
            supports_json_schema_output=True,
        )
    return OpenAIModelProfile(openai_chat_thinking_field="reasoning_content")


def _build_openai_compatible_model(
    spec: ModelSpec,
    *,
    structured_mode: StructuredMode | None = None,
):
    from pydantic_ai.providers.openai import OpenAIProvider

    base_url = structured_base_url(spec, structured_mode=structured_mode or "prompted_json")
    effective_spec = ModelSpec(
        family=spec.family,
        model_name=spec.model_name,
        base_url=base_url,
        api_key_env=spec.api_key_env,
    )

    api_key = _read_api_key(effective_spec)
    if effective_spec.base_url is not None:
        provider = OpenAIProvider(
            base_url=effective_spec.base_url,
            api_key=api_key or "api-key-not-set",
        )
    elif api_key is not None:
        provider = OpenAIProvider(api_key=api_key)
    else:
        provider = OpenAIProvider()

    profile = None
    if spec.model_name.startswith("deepseek-"):
        profile = _deepseek_profile(structured_mode=structured_mode or "prompted_json")

    return OpenAIChatModel(spec.model_name, provider=provider, profile=profile)


def build_structured_model(spec: ModelSpec, *, structured_mode: StructuredMode):
    """Build a model for structured DeepSeek calls (Beta endpoint when strict)."""
    if spec.family == ModelFamily.ANTHROPIC:
        return _build_anthropic_model(spec)
    if spec.family == ModelFamily.GOOGLE:
        return _build_google_model(spec)
    if spec.family == ModelFamily.OPENAI_COMPATIBLE:
        return _build_openai_compatible_model(spec, structured_mode=structured_mode)
    if spec.family == ModelFamily.TEST:
        return TestModel()
    raise NotImplementedError(f"Text family '{spec.family.value}' is not wired for use.")


def build_model(spec: ModelSpec):
    if spec.family == ModelFamily.ANTHROPIC:
        return _build_anthropic_model(spec)
    if spec.family == ModelFamily.GOOGLE:
        return _build_google_model(spec)
    if spec.family == ModelFamily.OPENAI_COMPATIBLE:
        return _build_openai_compatible_model(spec, structured_mode="prompted_json")
    if spec.family == ModelFamily.TEST:
        return TestModel()
    raise NotImplementedError(f"Text family '{spec.family.value}' is not wired for use.")


def endpoint_host(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlparse(base_url)
    return parsed.netloc or None


def describe_text_model(model: Any) -> ModelSpec | None:
    cls = getattr(model, "__class__", type(model))
    module = getattr(cls, "__module__", "")
    name = getattr(cls, "__name__", "unknown")
    runtime_name = getattr(model, "model_name", None)
    runtime_system = getattr(model, "system", None)
    runtime_base_url = getattr(model, "base_url", None)
    base_url = str(runtime_base_url) if runtime_base_url is not None else None
    model_name = str(runtime_name) if runtime_name is not None else name

    if module.startswith("pydantic_ai.models.test") or isinstance(model, TestModel):
        return ModelSpec(family=ModelFamily.TEST, model_name=name)

    if isinstance(model, AnthropicModel) or runtime_system == "anthropic":
        return ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name=model_name,
            base_url=base_url,
        )

    if (
        isinstance(model, GoogleModel)
        or name == "GeminiModel"
        or runtime_system in {"google", "google-gla", "google-vertex"}
        or module.startswith("pydantic_ai.models.google")
        or module.startswith("pydantic_ai.models.gemini")
    ):
        return ModelSpec(
            family=ModelFamily.GOOGLE,
            model_name=model_name,
            base_url=base_url,
        )

    if (
        isinstance(model, OpenAIChatModel)
        or runtime_system in _OPENAI_COMPATIBLE_SYSTEMS
        or module.startswith("pydantic_ai.models.openai")
    ):
        return ModelSpec(
            family=ModelFamily.OPENAI_COMPATIBLE,
            model_name=model_name,
            base_url=base_url,
        )

    return None


def effective_text_spec(*, catalog_spec: ModelSpec, model: Any | None) -> ModelSpec:
    if model is None:
        return catalog_spec
    described = describe_text_model(model)
    return described if described is not None else catalog_spec
