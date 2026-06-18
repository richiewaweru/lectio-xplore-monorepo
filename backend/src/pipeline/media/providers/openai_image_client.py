from __future__ import annotations

import asyncio
import base64
import json
import urllib.error
import urllib.request

from pipeline.media.providers.image_client import ImageFormat, ImageGenerationResult, ImageSize


class OpenAICompatibleImageClient:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")

    def _request_payload(
        self,
        *,
        prompt: str,
        size: ImageSize,
        format: ImageFormat,
        seed: int | None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model_name,
            "prompt": prompt,
            "size": size,
            "response_format": "b64_json",
            "output_format": format,
        }
        if seed is not None:
            payload["seed"] = seed
        return payload

    def _call_api(
        self,
        *,
        prompt: str,
        size: ImageSize,
        format: ImageFormat,
        seed: int | None,
    ) -> ImageGenerationResult:
        payload = json.dumps(
            self._request_payload(prompt=prompt, size=size, format=format, seed=seed)
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/images/generations",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise RuntimeError(
                f"HTTP Error {exc.code}: {exc.reason} | Body: {body[:500]}"
            ) from exc

        data = parsed.get("data") or []
        if not data:
            raise RuntimeError("Image provider returned no image data")
        b64_json = data[0].get("b64_json")
        if not b64_json:
            raise RuntimeError("Image provider response was missing b64_json")

        return ImageGenerationResult(
            bytes=base64.b64decode(b64_json),
            format=format,
            mime_type=f"image/{format}",
        )

    async def generate_image(
        self,
        *,
        prompt: str,
        size: ImageSize = "1024x1024",
        format: ImageFormat = "png",
        seed: int | None = None,
    ) -> ImageGenerationResult:
        return await asyncio.to_thread(
            self._call_api,
            prompt=prompt,
            size=size,
            format=format,
            seed=seed,
        )


class OpenAIImageClient(OpenAICompatibleImageClient):
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-image-1"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        super().__init__(api_key=api_key, model_name=model_name, base_url=base_url)
