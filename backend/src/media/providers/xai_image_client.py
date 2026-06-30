from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request

from media.providers.image_client import ImageFormat, ImageGenerationResult, ImageSize
from media.providers.openai_image_client import OpenAICompatibleImageClient


_SIZE_TO_ASPECT: dict[str, str] = {
    "1024x1024": "1:1",
    "1024x768": "4:3",
    "768x1024": "3:4",
    "1792x1024": "16:9",
    "1024x1792": "9:16",
}
logger = logging.getLogger(__name__)


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
        logger.info(
            "xai image request start",
            extra={
                "node_name": "visual_executor",
                "provider": "xai",
                "request_url": request.full_url,
                "image_model": self.model_name,
                "api_key_present": bool(self.api_key),
                "prompt_length": len(prompt),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw_body = response.read()
                logger.info(
                    "xai image response received",
                    extra={
                        "node_name": "visual_executor",
                        "provider": "xai",
                        "request_url": request.full_url,
                        "image_model": self.model_name,
                        "status_code": getattr(response, "status", None),
                        "body_length": len(raw_body),
                    },
                )
                parsed = json.loads(raw_body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            logger.error(
                "xai image request failed",
                extra={
                    "node_name": "visual_executor",
                    "provider": "xai",
                    "request_url": request.full_url,
                    "image_model": self.model_name,
                    "status_code": exc.code,
                    "body_length": len(body),
                    "response_body_preview": body[:500],
                },
                exc_info=exc,
            )
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
            logger.info(
                "xai image asset fetch start",
                extra={
                    "node_name": "visual_executor",
                    "provider": "xai",
                    "asset_url": url,
                    "image_model": self.model_name,
                },
            )
            try:
                with urllib.request.urlopen(url, timeout=60) as image_response:
                    image_bytes = image_response.read()
                    logger.info(
                        "xai image asset fetch received",
                        extra={
                            "node_name": "visual_executor",
                            "provider": "xai",
                            "asset_url": url,
                            "image_model": self.model_name,
                            "status_code": getattr(image_response, "status", None),
                            "body_length": len(image_bytes),
                        },
                    )
                    return ImageGenerationResult(
                        bytes=image_bytes,
                        format="jpeg",
                        mime_type="image/jpeg",
                    )
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                logger.error(
                    "xai image asset fetch failed",
                    extra={
                        "node_name": "visual_executor",
                        "provider": "xai",
                        "asset_url": url,
                        "image_model": self.model_name,
                        "status_code": exc.code,
                        "body_length": len(body),
                        "response_body_preview": body[:500],
                    },
                    exc_info=exc,
                )
                raise

        raise RuntimeError("xAI response contained neither b64_json nor url")

