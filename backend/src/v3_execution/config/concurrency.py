from __future__ import annotations

import asyncio
import os


def lane_concurrency_max() -> int:
    return int(os.getenv("V3_CONCURRENCY_LANE_MAX", "6"))


def lane_budget_seconds() -> float:
    return float(os.getenv("V3_LANE_BUDGET_SECONDS", "240"))


def resolved_concurrency_limits() -> dict[str, int]:
    """Resolved limits for logging and visual semaphore.

    Section/question caps are retired on the lane path; lane concurrency replaces them.
    Visuals stay under V3_CONCURRENCY_VISUAL_MAX outside lane budgets.
    """
    return {
        "lane": lane_concurrency_max(),
        "visual": int(os.getenv("V3_CONCURRENCY_VISUAL_MAX", "4")),
        # Kept for any residual readers; lane path does not use these semaphores.
        "section": int(os.getenv("V3_CONCURRENCY_SECTION_MAX", "5")),
        "question": int(os.getenv("V3_CONCURRENCY_QUESTION_MAX", "5")),
    }


def make_semaphores() -> dict[str, asyncio.Semaphore]:
    limits = resolved_concurrency_limits()
    return {
        "lane": asyncio.Semaphore(limits["lane"]),
        "visual_executor": asyncio.Semaphore(limits["visual"]),
        "answer_key_generator": asyncio.Semaphore(1),
        # Aliases so older call sites do not KeyError during transition.
        "section_writer": asyncio.Semaphore(limits["lane"]),
        "question_writer": asyncio.Semaphore(limits["lane"]),
    }


__all__ = [
    "lane_budget_seconds",
    "lane_concurrency_max",
    "make_semaphores",
    "resolved_concurrency_limits",
]
