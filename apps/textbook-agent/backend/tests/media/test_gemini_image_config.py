from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from media.providers import gemini_image_client as gemini
from media.providers.registry import load_image_provider_spec

_ENV_NAMES = (
    "IMAGE_PROVIDER",
    "IMAGE_MODEL_NAME",
    "IMAGE_BASE_URL",
    "IMAGE_API_KEY_ENV",
    "PIPELINE_IMAGE_PROVIDER",
    "GEMINI_IMAGE_API_KEY",
    "GEMINI_IMAGE_MODEL",
    "GEMINI_IMAGE_THINKING_LEVEL",
    "GOOGLE_CLOUD_NANO_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    gemini.get_gemini_image_client.cache_clear()
    yield
    gemini.get_gemini_image_client.cache_clear()


def test_spec_uses_gemini_variables_and_ignores_generic_ones(monkeypatch):
    # Generic variables may still hold another provider's values.
    monkeypatch.setenv("IMAGE_PROVIDER", "gemini")
    monkeypatch.setenv("IMAGE_MODEL_NAME", "grok-imagine-image")
    monkeypatch.setenv("IMAGE_BASE_URL", "https://api.x.ai/v1")
    monkeypatch.setenv("IMAGE_API_KEY_ENV", "XAI_API_KEY")

    spec = load_image_provider_spec()

    assert spec.provider == "gemini"
    assert spec.model_name == "gemini-3.1-flash-lite-image"
    assert spec.base_url is None
    assert spec.api_key_env == "GEMINI_IMAGE_API_KEY"


def test_gemini_image_model_overrides_default(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")

    assert load_image_provider_spec().model_name == "gemini-3.1-flash-image"


def test_new_api_key_name_wins_over_legacy_names(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy")
    monkeypatch.setenv("GEMINI_API_KEY", "legacy-2")
    monkeypatch.setenv("GEMINI_IMAGE_API_KEY", "new")

    assert gemini.resolve_gemini_image_api_key() == "new"


def test_legacy_api_key_names_still_work(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "legacy")

    assert gemini.resolve_gemini_image_api_key() == "legacy"


def test_missing_api_key_error_names_the_new_variable():
    with pytest.raises(RuntimeError, match="GEMINI_IMAGE_API_KEY"):
        gemini.get_gemini_image_client()


def test_thinking_level_defaults_to_minimal_and_accepts_high(monkeypatch):
    assert gemini.resolve_gemini_thinking_level() == "MINIMAL"

    monkeypatch.setenv("GEMINI_IMAGE_THINKING_LEVEL", "High")
    assert gemini.resolve_gemini_thinking_level() == "HIGH"


def test_invalid_thinking_level_is_rejected(monkeypatch):
    monkeypatch.setenv("GEMINI_IMAGE_THINKING_LEVEL", "medium")

    with pytest.raises(RuntimeError, match="GEMINI_IMAGE_THINKING_LEVEL"):
        gemini.resolve_gemini_thinking_level()


def test_generate_image_sends_configured_model_and_thinking_level(monkeypatch):
    calls: list[dict] = []

    class _Models:
        def generate_content_stream(self, *, model, contents, config):
            calls.append({"model": model, "config": config})
            part = SimpleNamespace(
                inline_data=SimpleNamespace(data=b"png-bytes", mime_type="image/png")
            )
            yield SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])

    class _FakeGenai:
        def __init__(self, **_kwargs):
            self.models = _Models()

    monkeypatch.setattr(gemini.genai, "Client", _FakeGenai)
    monkeypatch.setenv("GEMINI_IMAGE_API_KEY", "key")
    monkeypatch.setenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
    monkeypatch.setenv("GEMINI_IMAGE_THINKING_LEVEL", "minimal")

    client = gemini.get_gemini_image_client()
    result = asyncio.run(client.generate_image(prompt="an L-shaped floor plan"))

    assert result.bytes == b"png-bytes"
    assert result.format == "png"
    assert calls[0]["model"] == "gemini-3.1-flash-image"
    assert str(calls[0]["config"].thinking_config.thinking_level).endswith("MINIMAL")
