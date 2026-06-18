from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from pipeline.media.providers.image_client import ImageFormat, ImageGenerationResult, ImageSize
from pipeline.media.providers.openai_image_client import OpenAICompatibleImageClient


_SIZE_TO_ASPECT: dict[str, str] = {
    "1024x1024": "1:1",
    "1024x768": "4:3",
    "768x1024": "3:4",
    "1792x1024": "16:9",
    "1024x1792": "9:16",
}


class XAIImageClient(OpenAICompatibleImageClient):
    DEFAULT_MODEL = "grok-imagine-image"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        super().__init__(api_key=api_key, model_name=model_name, base_url=base_url)

    def _request_payload(
        self,
        *,
        prompt: str,
        size: ImageSize,
        format: ImageFormat,
        seed: int | None,
    ) -> dict[str, object]:
        _ = (format, seed)
        payload: dict[str, object] = {
            "model": self.model_name,
            "prompt": prompt,
            "response_format": "b64_json",
        }
        aspect_ratio = _SIZE_TO_ASPECT.get(size)
        if aspect_ratio is not None:
            payload["aspect_ratio"] = aspect_ratio
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
            raise RuntimeError("xAI returned no image data")

        entry = data[0]
        b64_json = entry.get("b64_json")
        if b64_json:
            return ImageGenerationResult(
                bytes=base64.b64decode(b64_json),
                format="jpeg",
                mime_type="image/jpeg",
            )

        url = entry.get("url")
        if url:
            with urllib.request.urlopen(url, timeout=60) as image_response:
                return ImageGenerationResult(
                    bytes=image_response.read(),
                    format="jpeg",
                    mime_type="image/jpeg",
                )

        raise RuntimeError("xAI response contained neither b64_json nor url")
