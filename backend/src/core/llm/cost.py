from __future__ import annotations

from typing import Any, Mapping

from core.llm.types import ModelFamily, ModelSpec
from core.llm.transport import endpoint_host

TOKEN_PRICE_USD_PER_1M_BY_MODEL: dict[str, tuple[float, float]] = {
    "anthropic:claude-haiku-4-5-20251001": (0.25, 1.25),
    "anthropic:claude-sonnet-4-6": (3.0, 15.0),
    "anthropic:claude-opus-4-6": (15.0, 75.0),
    "test:TestModel": (0.0, 0.0),
}


def _price_key(effective_spec: ModelSpec) -> str:
    if effective_spec.family == ModelFamily.OPENAI_COMPATIBLE:
        host = endpoint_host(effective_spec.base_url)
        if host:
            return f"{effective_spec.family.value}:{host}:{effective_spec.model_name}"
    return f"{effective_spec.family.value}:{effective_spec.model_name}"


def _price_per_1m(effective_spec: ModelSpec) -> tuple[float, float] | None:
    return TOKEN_PRICE_USD_PER_1M_BY_MODEL.get(_price_key(effective_spec))


def extract_usage(result: Any) -> tuple[int | None, int | None]:
    usage = getattr(result, "usage", None)
    if usage is None:
        return None, None

    def get_field(obj: Any, key: str) -> int | None:
        val = obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)
        if isinstance(val, (int, float)):
            return int(val)
        return None

    input_tokens = (
        get_field(usage, "input_tokens")
        or get_field(usage, "prompt_tokens")
        or get_field(usage, "input_token_count")
        or get_field(usage, "prompt_token_count")
    )
    output_tokens = (
        get_field(usage, "output_tokens")
        or get_field(usage, "completion_tokens")
        or get_field(usage, "output_token_count")
        or get_field(usage, "completion_token_count")
    )

    return input_tokens, output_tokens


def extract_thinking_tokens(result: Any) -> int | None:
    """Best-effort thinking token count across provider-specific usage.details keys."""
    usage_obj = getattr(result, "usage", None)
    if usage_obj is None:
        return None
    usage = usage_obj() if callable(usage_obj) else usage_obj
    details = getattr(usage, "details", None)
    if not isinstance(details, dict):
        return None
    for key in (
        "thinking_tokens",
        "thinking_token_count",
        "anthropic_thinking_tokens",
        "reasoning_tokens",
    ):
        val = details.get(key)
        if isinstance(val, (int, float)):
            return int(val)
    return None


def compute_cost_usd(
    effective_spec: ModelSpec,
    tokens_in: int | None,
    tokens_out: int | None,
) -> float | None:
    if tokens_in is None or tokens_out is None:
        return None

    prices = _price_per_1m(effective_spec)
    if prices is None:
        return None

    in_usd, out_usd = prices
    return (tokens_in / 1_000_000) * in_usd + (tokens_out / 1_000_000) * out_usd
