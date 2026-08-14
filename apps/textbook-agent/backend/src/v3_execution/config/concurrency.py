from __future__ import annotations

import asyncio
import logging
import os

from v3_execution.config.retries import V3_MAX_RETRIES
from v3_execution.config.timeouts import V3_TIMEOUTS

logger = logging.getLogger(__name__)


def lane_concurrency_max() -> int:
    return int(os.getenv("V3_CONCURRENCY_LANE_MAX", "6"))


def lane_budget_seconds() -> float:
    return float(os.getenv("V3_LANE_BUDGET_SECONDS", "420"))


def log_lane_budget_diagnostic() -> float:
    required = sum(
        V3_TIMEOUTS[name] * (1 + V3_MAX_RETRIES.get(name, 0))
        for name in ("section_writer", "question_writer")
    )
    budget = lane_budget_seconds()
    if budget >= required:
        logger.info(
            "v3 lane budget validated: budget_seconds=%s worst_case_step_seconds=%s",
            budget,
            required,
        )
    else:
        logger.warning(
            "v3 lane budget is below worst-case step timeout budget: "
            "budget_seconds=%s worst_case_step_seconds=%s",
            budget,
            required,
        )
    return required


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
        "answer_key_generator": asyncio.Semaphore(
            int(os.getenv("V3_CONCURRENCY_ANSWER_KEY_MAX", "4"))
        ),
        # Aliases so older call sites do not KeyError during transition.
        "section_writer": asyncio.Semaphore(limits["lane"]),
        "question_writer": asyncio.Semaphore(limits["lane"]),
    }


__all__ = [
    "lane_budget_seconds",
    "lane_concurrency_max",
    "log_lane_budget_diagnostic",
    "make_semaphores",
    "resolved_concurrency_limits",
]
