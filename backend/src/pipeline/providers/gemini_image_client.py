from functools import lru_cache

from google import genai

from pipeline.media.providers.gemini_image_client import (
    GeminiImageClient,
    _provider_image_config,
    resolve_gemini_image_api_key,
)


@lru_cache(maxsize=1)
def get_gemini_image_client() -> GeminiImageClient:
    api_key = resolve_gemini_image_api_key()
    if not api_key:
        raise RuntimeError(
            "No Gemini API key found. Set GOOGLE_CLOUD_NANO_API_KEY, GOOGLE_API_KEY, or GEMINI_API_KEY."
        )
    return GeminiImageClient(api_key=api_key)

__all__ = [
    "GeminiImageClient",
    "_provider_image_config",
    "genai",
    "get_gemini_image_client",
    "resolve_gemini_image_api_key",
]
