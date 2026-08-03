from __future__ import annotations

import asyncio
import os


def resolved_concurrency_limits() -> dict[str, int]:
    return {
        "section": int(os.getenv("V3_CONCURRENCY_SECTION_MAX", "5")),
        "question": int(os.getenv("V3_CONCURRENCY_QUESTION_MAX", "5")),
        "visual": int(os.getenv("V3_CONCURRENCY_VISUAL_MAX", "4")),
    }


def make_semaphores() -> dict[str, asyncio.Semaphore]:
    limits = resolved_concurrency_limits()
    return {
        "section_writer": asyncio.Semaphore(limits["section"]),
        "question_writer": asyncio.Semaphore(limits["question"]),
        "visual_executor": asyncio.Semaphore(limits["visual"]),
        "answer_key_generator": asyncio.Semaphore(1),
    }


__all__ = ["make_semaphores", "resolved_concurrency_limits"]
