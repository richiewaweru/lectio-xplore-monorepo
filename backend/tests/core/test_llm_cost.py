from __future__ import annotations

from types import SimpleNamespace

from core.llm.cost import extract_thinking_tokens


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
