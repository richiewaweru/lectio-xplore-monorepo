from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelSlot(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"


class ModelFamily(str, Enum):
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENAI_COMPATIBLE = "openai_compatible"
    TEST = "test"


@dataclass(frozen=True)
class ModelSpec:
    family: ModelFamily
    model_name: str
    base_url: str | None = None
    api_key_env: str | None = None

