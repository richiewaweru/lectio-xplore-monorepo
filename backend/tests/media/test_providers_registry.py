from __future__ import annotations

import base64
import asyncio
import inspect
import os
from pathlib import Path
from contextlib import contextmanager

import httpx

from media.providers.openai_image_client import OpenAICompatibleImageClient
from media.providers.registry import get_image_client, load_image_provider_spec
from media.providers.xai_image_client import XAIImageClient


_IMAGE_ENV_KEYS = (
    "IMAGE_PROVIDER",
    "IMAGE_MODEL_NAME",
    "IMAGE_BASE_URL",
    "IMAGE_API_KEY_ENV",
    "PIPELINE_IMAGE_PROVIDER",
    "PIPELINE_IMAGE_MODEL_NAME",
    "PIPELINE_IMAGE_BASE_URL",
    "PIPELINE_IMAGE_API_KEY_ENV",
    "OPENAI_API_KEY",
    "XAI_API_KEY",
)


@contextmanager
def _env(**kwargs: str | None):
    old = {k: os.environ.get(k) for k in _IMAGE_ENV_KEYS}
    try:
        for key in _IMAGE_ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in kwargs.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key in _IMAGE_ENV_KEYS:
            if old[key] is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old[key]


def test_image_provider_uses_image_env_names_first():
    with _env(
        IMAGE_PROVIDER="openai",
        IMAGE_MODEL_NAME="gpt-image-1",
        IMAGE_BASE_URL="https://api.openai.com/v1",
        IMAGE_API_KEY_ENV="OPENAI_API_KEY",
        PIPELINE_IMAGE_PROVIDER="xai",
        PIPELINE_IMAGE_MODEL_NAME="grok-imagine-image",
        PIPELINE_IMAGE_BASE_URL="https://api.x.ai/v1",
        PIPELINE_IMAGE_API_KEY_ENV="XAI_API_KEY",
        OPENAI_API_KEY="sk-test",
        XAI_API_KEY="sk-test",
    ):
        spec = load_image_provider_spec()
        client = get_image_client()

    assert spec.provider == "openai"
    assert spec.model_name == "gpt-image-1"
    assert spec.base_url == "https://api.openai.com/v1"
    assert spec.api_key_env == "OPENAI_API_KEY"
    assert client.__class__.__name__ == "OpenAIImageClient"


def test_image_provider_falls_back_to_pipeline_image_env_names():
    with _env(
        PIPELINE_IMAGE_PROVIDER="xai",
        PIPELINE_IMAGE_MODEL_NAME=None,
        PIPELINE_IMAGE_BASE_URL="https://api.x.ai/v1",
        PIPELINE_IMAGE_API_KEY_ENV="XAI_API_KEY",
        XAI_API_KEY="sk-test",
    ):
        spec = load_image_provider_spec()
        client = get_image_client()

    assert spec.provider == "xai"
    assert spec.base_url == "https://api.x.ai/v1"
    assert spec.model_name == "grok-imagine-image"
    assert client.__class__.__name__ == "XAIImageClient"


def test_pipeline_provider_does_not_mix_in_image_base_url_override():
    with _env(
        IMAGE_BASE_URL="https://storage.googleapis.com/lectio-bucket-1",
        PIPELINE_IMAGE_PROVIDER="xai",
        PIPELINE_IMAGE_MODEL_NAME="grok-imagine-image",
        PIPELINE_IMAGE_BASE_URL="https://api.x.ai/v1",
        PIPELINE_IMAGE_API_KEY_ENV="XAI_API_KEY",
        XAI_API_KEY="sk-test",
    ):
        spec = load_image_provider_spec()
        client = get_image_client()

    assert spec.provider == "xai"
    assert spec.base_url == "https://api.x.ai/v1"
    assert client.base_url == "https://api.x.ai/v1"


def test_image_provider_selects_openai_with_image_env_names():
    with _env(
        IMAGE_PROVIDER="openai",
        IMAGE_MODEL_NAME="gpt-image-1",
        IMAGE_BASE_URL=None,
        IMAGE_API_KEY_ENV=None,
        OPENAI_API_KEY="sk-test",
    ):
        client = get_image_client()

    assert client.__class__.__name__ == "OpenAIImageClient"


def test_xai_requires_explicit_base_url():
    with _env(
        IMAGE_PROVIDER="xai",
        IMAGE_BASE_URL=None,
        IMAGE_API_KEY_ENV="XAI_API_KEY",
        XAI_API_KEY="sk-test",
    ):
        try:
            load_image_provider_spec()
        except RuntimeError as exc:
            assert "IMAGE_BASE_URL is required" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError for missing xAI base URL")


def test_xai_payload_omits_unsupported_params():
    client = XAIImageClient(api_key="test", base_url="https://api.x.ai/v1")

    payload = client._request_payload(
        prompt="test",
        size="1024x1024",
        format="png",
        seed=None,
    )

    assert payload["model"] == "grok-imagine-image"
    assert payload["response_format"] == "b64_json"
    assert payload["aspect_ratio"] == "1:1"
    assert "size" not in payload
    assert "output_format" not in payload


def test_xai_payload_maps_size_to_aspect_ratio():
    client = XAIImageClient(api_key="test", base_url="https://api.x.ai/v1")

    widescreen_payload = client._request_payload(
        prompt="test",
        size="1792x1024",  # type: ignore[arg-type]
        format="png",
        seed=None,
    )
    unmapped_payload = client._request_payload(
        prompt="test",
        size="512x512",
        format="png",
        seed=None,
    )

    assert widescreen_payload["aspect_ratio"] == "16:9"
    assert "aspect_ratio" not in unmapped_payload


def test_xai_call_api_decodes_b64_json_as_jpeg(monkeypatch):
    client = XAIImageClient(api_key="test", base_url="https://api.x.ai/v1")
    encoded = base64.b64encode(b"jpeg-bytes").decode("ascii")

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.x.ai/v1/images/generations"
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    _patch_async_client(monkeypatch, _handler)

    result = asyncio.run(
        client._call_api(prompt="test", size="1024x1024", format="png", seed=None)
    )

    assert result.bytes == b"jpeg-bytes"
    assert result.format == "jpeg"
    assert result.mime_type == "image/jpeg"


def test_xai_call_api_downloads_url_response_as_jpeg(monkeypatch):
    client = XAIImageClient(api_key="test", base_url="https://api.x.ai/v1")

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://cdn.x.ai/generated.jpg":
            return httpx.Response(200, content=b"remote-jpeg")
        return httpx.Response(200, json={"data": [{"url": "https://cdn.x.ai/generated.jpg"}]})

    _patch_async_client(monkeypatch, _handler)

    result = asyncio.run(
        client._call_api(prompt="test", size="1024x1024", format="png", seed=None)
    )

    assert result.bytes == b"remote-jpeg"
    assert result.format == "jpeg"
    assert result.mime_type == "image/jpeg"


def test_openai_compatible_http_error_includes_response_body(monkeypatch):
    client = OpenAICompatibleImageClient(
        api_key="test",
        model_name="gpt-image-1",
        base_url="https://api.openai.com/v1",
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.openai.com/v1/images/generations"
        return httpx.Response(400, content=b'{"error":"unsupported"}')

    _patch_async_client(monkeypatch, _handler)

    try:
        asyncio.run(client._call_api(prompt="test", size="1024x1024", format="png", seed=None))
    except RuntimeError as exc:
        assert 'HTTP Error 400: Bad Request | Body: {"error":"unsupported"}' in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for OpenAI-compatible HTTP error")


def test_xai_http_error_includes_response_body(monkeypatch):
    client = XAIImageClient(api_key="test", base_url="https://api.x.ai/v1")

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.x.ai/v1/images/generations"
        return httpx.Response(400, content=b'{"error":"size not supported"}')

    _patch_async_client(monkeypatch, _handler)

    try:
        asyncio.run(client._call_api(prompt="test", size="1024x1024", format="png", seed=None))
    except RuntimeError as exc:
        assert 'HTTP Error 400: Bad Request | Body: {"error":"size not supported"}' in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for xAI HTTP error")


def test_image_clients_are_coroutines_and_provider_code_does_not_call_urlopen():
    assert inspect.iscoroutinefunction(OpenAICompatibleImageClient._call_api)
    assert inspect.iscoroutinefunction(XAIImageClient._call_api)

    provider_dir = Path(__file__).resolve().parents[2] / "src" / "media" / "providers"
    provider_source = "\n".join(path.read_text(encoding="utf-8") for path in provider_dir.glob("*.py"))
    assert "urllib.request.urlopen" not in provider_source


def _patch_async_client(monkeypatch, handler) -> None:
    original_async_client = httpx.AsyncClient

    def _factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
