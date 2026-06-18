from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


ImageSize = Literal["256x256", "512x512", "1024x1024", "1792x1024"]
ImageFormat = Literal["png", "jpeg", "webp"]


@dataclass(frozen=True)
class ImageGenerationResult:
    bytes: bytes
    format: ImageFormat
    mime_type: str


class ImageModelClient(Protocol):
    async def generate_image(
        self,
        *,
        prompt: str,
        size: ImageSize = "1024x1024",
        format: ImageFormat = "png",
        seed: int | None = None,
    ) -> ImageGenerationResult:
        ...
