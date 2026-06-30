from __future__ import annotations

from types import SimpleNamespace

from core.llm.cost import extract_thinking_tokens, extract_usage


def test_extract_thinking_tokens_reads_deepseek_reasoning_tokens() -> None:
    result = SimpleNamespace(
        usage=SimpleNamespace(
            details={
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 20,
                "reasoning_tokens": 47,
            }
        )
    )

    assert extract_thinking_tokens(result) == 47


def test_extract_usage_reads_cache_hit_and_miss_tokens() -> None:
    result = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=20,
            completion_tokens=8,
            details={
                "prompt_cache_hit_tokens": 14,
                "prompt_cache_miss_tokens": 6,
            },
        )
    )

    usage = extract_usage(result)

    assert usage.tokens_in == 20
    assert usage.tokens_out == 8
    assert usage.prompt_cache_hit_tokens == 14
    assert usage.prompt_cache_miss_tokens == 6


def test_extract_usage_handles_missing_usage() -> None:
    usage = extract_usage(SimpleNamespace())

    assert usage.tokens_in is None
    assert usage.tokens_out is None
    assert usage.prompt_cache_hit_tokens is None
    assert usage.prompt_cache_miss_tokens is None
