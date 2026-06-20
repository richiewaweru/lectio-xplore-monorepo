from __future__ import annotations

import asyncio
import os


def make_semaphores() -> dict[str, asyncio.Semaphore]:
    return {
        "section_writer": asyncio.Semaphore(int(os.getenv("V3_CONCURRENCY_SECTION_MAX", "3"))),
        "question_writer": asyncio.Semaphore(int(os.getenv("V3_CONCURRENCY_QUESTION_MAX", "3"))),
        "visual_executor": asyncio.Semaphore(int(os.getenv("V3_CONCURRENCY_VISUAL_MAX", "2"))),
        "answer_key_generator": asyncio.Semaphore(1),
    }


__all__ = ["make_semaphores"]
