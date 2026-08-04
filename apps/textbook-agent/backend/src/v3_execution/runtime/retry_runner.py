from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from v3_execution.models import ExecutorOutcome

T = TypeVar("T")


async def run_with_retries(
    label: str,
    factory: Callable[[bool], Awaitable[ExecutorOutcome]],
    *,
    max_retries: int,
) -> ExecutorOutcome:
    """Run factory up to (1 + max_retries) attempts; set retried when a later attempt succeeds or all fail."""
    total_attempts = max(1, max_retries + 1)
    last: ExecutorOutcome | None = None
    for attempt in range(total_attempts):
        already_retried = attempt > 0
        last = await factory(already_retried)
        if last.ok:
            if already_retried:
                last.warnings.insert(0, f"{label}: succeeded after retry")
            last.retried = already_retried
            return last
    assert last is not None
    if total_attempts > 1:
        last.warnings.insert(0, f"{label}: failed after retry — flagged for coherence review")
    last.retried = True
    return last


async def run_with_single_retry(
    label: str,
    factory: Callable[[bool], Awaitable[ExecutorOutcome]],
) -> ExecutorOutcome:
    """Backward-compatible wrapper: at most one retry."""
    return await run_with_retries(label, factory, max_retries=1)


__all__ = ["run_with_retries", "run_with_single_retry"]
