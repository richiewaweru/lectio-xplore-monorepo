from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache

from google import genai
from google.genai import types

from media.providers.image_client import ImageFormat, ImageGenerationResult, ImageSize

logger = logging.getLogger(__name__)

# Gemini image configuration. These are the only variables an operator needs:
#   GEMINI_IMAGE_API_KEY         the API key (required)
#   GEMINI_IMAGE_MODEL           model id (optional, cheap and fast by default)
#   GEMINI_IMAGE_THINKING_LEVEL  "minimal" (default) or "high" (optional)
# The older key names stay as a fallback so existing deployments keep working,
# but GEMINI_IMAGE_API_KEY always wins when it is set.
API_KEY_ENV = "GEMINI_IMAGE_API_KEY"
MODEL_ENV = "GEMINI_IMAGE_MODEL"
THINKING_LEVEL_ENV = "GEMINI_IMAGE_THINKING_LEVEL"
DEFAULT_MODEL = "gemini-3.1-flash-lite-image"
DEFAULT_THINKING_LEVEL = "minimal"
_THINKING_LEVELS = {"minimal": "MINIMAL", "high": "HIGH"}
_API_KEY_ENV_NAMES = (
    API_KEY_ENV,
    "GOOGLE_CLOUD_NANO_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
)
_MIME_TO_FORMAT: dict[str, ImageFormat] = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/webp": "webp",
}


def _provider_image_config(size: ImageSize) -> types.ImageConfig:
    _ = size
    return types.ImageConfig(
        aspect_ratio="1:1",
        image_size="1K",
    )


def resolve_gemini_image_model() -> str:
    """Model id from GEMINI_IMAGE_MODEL, else the cheap/fast default."""
    return (os.environ.get(MODEL_ENV) or "").strip() or DEFAULT_MODEL


def resolve_gemini_thinking_level() -> str:
    """Provider enum value for GEMINI_IMAGE_THINKING_LEVEL (minimal or high)."""
    raw = (os.environ.get(THINKING_LEVEL_ENV) or "").strip().lower()
    level = raw or DEFAULT_THINKING_LEVEL
    if level not in _THINKING_LEVELS:
        raise RuntimeError(
            f"{THINKING_LEVEL_ENV} must be one of: {', '.join(sorted(_THINKING_LEVELS))}"
        )
    return _THINKING_LEVELS[level]


class GeminiImageClient:
    MODEL = DEFAULT_MODEL

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        thinking_level: str | None = None,
    ) -> None:
        self._client = genai.Client(vertexai=False, api_key=api_key)
        self._model = model or resolve_gemini_image_model()
        self._thinking_level = thinking_level or resolve_gemini_thinking_level()
        logger.info(
            "GeminiImageClient: initialised model=%s thinking_level=%s vertexai=False",
            self._model,
            self._thinking_level,
        )

    def _resolve_result_format(
        self,
        *,
        requested_format: ImageFormat,
        provider_mime_type: str | None,
    ) -> tuple[ImageFormat, str]:
        if provider_mime_type:
            normalized_mime = provider_mime_type.strip().lower()
            resolved_format = _MIME_TO_FORMAT.get(normalized_mime)
            if resolved_format is not None:
                return resolved_format, normalized_mime

            logger.warning(
                "GeminiImageClient: unsupported provider mime_type=%s; falling back to %s",
                provider_mime_type,
                requested_format,
            )
        else:
            logger.warning(
                "GeminiImageClient: provider returned no mime_type; falling back to %s",
                requested_format,
            )

        return requested_format, f"image/{requested_format}"

    async def generate_image(
        self,
        *,
        prompt: str,
        size: ImageSize = "1024x1024",
        format: ImageFormat = "png",
        seed: int | None = None,
    ) -> ImageGenerationResult:
        _ = seed
        config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            max_output_tokens=32768,
            response_modalities=["TEXT", "IMAGE"],
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
            ],
            image_config=_provider_image_config(size),
            thinking_config=types.ThinkingConfig(thinking_level=self._thinking_level),
        )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            )
        ]

        def _call() -> tuple[bytes, str | None]:
            image_bytes: bytes | None = None
            image_mime_type: str | None = None
            for chunk in self._client.models.generate_content_stream(
                model=self._model,
                contents=contents,
                config=config,
            ):
                if not chunk.candidates:
                    continue
                for part in chunk.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image_bytes = part.inline_data.data
                        image_mime_type = part.inline_data.mime_type
                        break
                if image_bytes is not None:
                    break

            if image_bytes is None:
                raise RuntimeError("Gemini returned no image data in response")
            return image_bytes, image_mime_type

        image_bytes, provider_mime_type = await asyncio.to_thread(_call)
        result_format, result_mime_type = self._resolve_result_format(
            requested_format=format,
            provider_mime_type=provider_mime_type,
        )

        return ImageGenerationResult(
            bytes=image_bytes,
            format=result_format,
            mime_type=result_mime_type,
        )


def resolve_gemini_image_api_key() -> str | None:
    for env_name in _API_KEY_ENV_NAMES:
        value = os.environ.get(env_name)
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def get_gemini_image_client() -> GeminiImageClient:
    api_key = resolve_gemini_image_api_key()
    if not api_key:
        raise RuntimeError(
            f"No Gemini API key found. Set {API_KEY_ENV}."
        )
    return GeminiImageClient(api_key=api_key)

