from __future__ import annotations

import os
from dataclasses import dataclass

from pipeline.media.providers.gemini_image_client import GeminiImageClient, get_gemini_image_client
from pipeline.media.providers.openai_image_client import OpenAIImageClient
from pipeline.media.providers.xai_image_client import XAIImageClient


@dataclass(frozen=True)
class ImageProviderSpec:
    provider: str
    model_name: str
    base_url: str | None
    api_key_env: str | None


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return None


def load_image_provider_spec() -> ImageProviderSpec:
    provider = (_first_env("PIPELINE_IMAGE_PROVIDER") or "gemini").strip().lower()
    model_name = _first_env("PIPELINE_IMAGE_MODEL_NAME")
    base_url = _first_env("PIPELINE_IMAGE_BASE_URL")
    api_key_env = _first_env("PIPELINE_IMAGE_API_KEY_ENV")

    if provider == "gemini":
        return ImageProviderSpec(
            provider="gemini",
            model_name=model_name or GeminiImageClient.MODEL,
            base_url=base_url,
            api_key_env=api_key_env,
        )
    if provider == "openai":
        return ImageProviderSpec(
            provider="openai",
            model_name=model_name or OpenAIImageClient.DEFAULT_MODEL,
            base_url=base_url or OpenAIImageClient.DEFAULT_BASE_URL,
            api_key_env=api_key_env or "OPENAI_API_KEY",
        )
    if provider == "xai":
        if not base_url:
            raise RuntimeError(
                "PIPELINE_IMAGE_BASE_URL is required when PIPELINE_IMAGE_PROVIDER=xai"
            )
        if not api_key_env:
            raise RuntimeError(
                "PIPELINE_IMAGE_API_KEY_ENV is required when PIPELINE_IMAGE_PROVIDER=xai"
            )
        return ImageProviderSpec(
            provider="xai",
            model_name=model_name or XAIImageClient.DEFAULT_MODEL,
            base_url=base_url,
            api_key_env=api_key_env,
        )
    raise RuntimeError(
        "Unsupported PIPELINE_IMAGE_PROVIDER. Expected one of: gemini, openai, xai."
    )


def get_image_client():
    spec = load_image_provider_spec()
    if spec.provider == "gemini":
        return get_gemini_image_client()

    api_key = os.getenv(spec.api_key_env or "")
    if not api_key:
        raise RuntimeError(
            f"{spec.provider} image client expects env var '{spec.api_key_env}', but it is not set."
        )

    if spec.provider == "openai":
        return OpenAIImageClient(
            api_key=api_key,
            model_name=spec.model_name,
            base_url=spec.base_url or OpenAIImageClient.DEFAULT_BASE_URL,
        )
    if spec.provider == "xai":
        return XAIImageClient(
            api_key=api_key,
            model_name=spec.model_name,
            base_url=spec.base_url or "",
        )
    raise RuntimeError(f"Unsupported image provider '{spec.provider}'.")
