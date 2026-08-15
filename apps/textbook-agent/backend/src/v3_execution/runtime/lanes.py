"""Per-section lanes: steps sequential inside, lanes parallel outside."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from v3_blueprint.planning.persistence import (
    insert_step,
    load_step_payload,
    step_exists,
)
from v3_execution.config.concurrency import lane_budget_seconds, lane_concurrency_max

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]
logger = logging.getLogger(__name__)
FailureKind = Literal["timeout", "validation", "provider", "persistence", "network", "unknown"]


@dataclass
class LaneOutcome:
    part_id: str
    component_blocks: list[Any] = field(default_factory=list)
    question_blocks: list[Any] = field(default_factory=list)
    failed_step: str | None = None
    failure_kind: FailureKind | None = None
    prose_complete: bool = False
    questions_complete: bool = False
    warnings: list[str] = field(default_factory=list)


def resolved_lane_limits() -> dict[str, int | float]:
    """Lane concurrency; V3_STAGE2_PARALLEL=false forces concurrency 1 (no separate path)."""
    if os.getenv("V3_STAGE2_PARALLEL", "true").strip().lower() == "false":
        concurrency = 1
    else:
        concurrency = lane_concurrency_max()
    return {
        "lane": concurrency,
        "budget_seconds": lane_budget_seconds(),
    }


async def run_lane(
    *,
    generation_id: str,
    part_id: str,
    variant_id: str,
    prose_coro_factory: Callable[[], Awaitable[list[Any]]],
    questions_coro_factory: Callable[[], Awaitable[list[Any]]] | None,
    emit_event: EmitFn | None = None,
    kind: str = "lesson",
) -> LaneOutcome:
    """Run prose then questions for one part; skip steps that already exist."""
    outcome = LaneOutcome(part_id=part_id)
    current_step = "prose"

    async def _load_step(step: str) -> list[Any] | None:
        try:
            if not await step_exists(
                generation_id, part_id=part_id, step=step, variant_id=variant_id
            ):
                return None
            payload = await load_step_payload(
                generation_id, part_id=part_id, step=step, variant_id=variant_id
            )
            blocks = payload.get("blocks") if payload else None
            return list(blocks) if isinstance(blocks, list) else []
        except Exception:  # noqa: BLE001
            logger.warning(
                "lane checkpoint lookup failed",
                extra={"generation_id": generation_id, "part_id": part_id, "step": step},
                exc_info=True,
            )
            raise

    async def _save(step: str, blocks: list[Any]) -> None:
        try:
            await insert_step(
                generation_id,
                part_id=part_id,
                step=step,
                variant_id=variant_id,
                kind=kind,
                payload={
                    "blocks": [
                        b.model_dump(mode="json") if hasattr(b, "model_dump") else b
                        for b in blocks
                    ]
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "lane checkpoint save failed",
                extra={"generation_id": generation_id, "part_id": part_id, "step": step},
                exc_info=True,
            )
            raise

    def _failure_kind(exc: BaseException) -> FailureKind:
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return "timeout"
        if isinstance(exc, ValidationError):
            return "validation"
        try:
            import httpx

            if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError)):
                return "network"
        except ImportError:
            pass
        return "provider" if "model" in type(exc).__name__.lower() else "unknown"

    try:
        persisted_prose = await _load_step("prose")
        if persisted_prose is None:
            current_step = "prose"
            blocks = await prose_coro_factory()
            outcome.component_blocks = list(blocks or [])
            await _save("prose", outcome.component_blocks)
            outcome.prose_complete = True
            if emit_event:
                await emit_event(
                    "lane_step_complete",
                    {
                        "generation_id": generation_id,
                        "part_id": part_id,
                        "step": "prose",
                    },
                )
        else:
            outcome.component_blocks = persisted_prose
            outcome.prose_complete = True
        if questions_coro_factory is not None:
            persisted_questions = await _load_step("questions")
            if persisted_questions is None:
                current_step = "questions"
                qblocks = await questions_coro_factory()
                outcome.question_blocks = list(qblocks or [])
                await _save("questions", outcome.question_blocks)
                outcome.questions_complete = True
                if emit_event:
                    await emit_event(
                        "lane_step_complete",
                        {
                            "generation_id": generation_id,
                            "part_id": part_id,
                        "step": "questions",
                    },
                )
            else:
                outcome.question_blocks = persisted_questions
                outcome.questions_complete = True
        else:
            outcome.questions_complete = True
    except TimeoutError:
        outcome.failed_step = "budget"
        outcome.failure_kind = "timeout"
        outcome.warnings.append(
            f"lane:{part_id}:budget exhausted during {current_step}"
        )
    except Exception as exc:  # noqa: BLE001
        outcome.failed_step = current_step
        outcome.failure_kind = _failure_kind(exc)
        outcome.warnings.append(
            f"lane:{part_id}:{current_step}: {type(exc).__name__}: {exc}"
        )
    return outcome


async def run_all_lanes(
    *,
    lane_factories: list[Callable[[], Awaitable[LaneOutcome]]],
    concurrency: int | None = None,
    budget_seconds: float | None = None,
) -> list[LaneOutcome]:
    limits = resolved_lane_limits()
    conc = concurrency if concurrency is not None else int(limits["lane"])
    budget = (
        budget_seconds
        if budget_seconds is not None
        else float(limits["budget_seconds"])
    )
    sem = asyncio.Semaphore(max(1, conc))

    async def _wrap(factory: Callable[[], Awaitable[LaneOutcome]]) -> LaneOutcome:
        async with sem:
            try:
                async with asyncio.timeout(budget):
                    return await factory()
            except TimeoutError:
                # Factory may already have recorded budget; synthesize if it never ran.
                return LaneOutcome(
                    part_id="unknown",
                    failed_step="budget",
                    failure_kind="timeout",
                    warnings=[f"lane:budget exhausted ({budget}s)"],
                )

    results = await asyncio.gather(
        *[_wrap(factory) for factory in lane_factories],
        return_exceptions=True,
    )
    outcomes: list[LaneOutcome] = []
    for result in results:
        if isinstance(result, LaneOutcome):
            outcomes.append(result)
        elif isinstance(result, Exception):
            outcomes.append(
                LaneOutcome(
                    part_id="unknown",
                    failed_step="prose",
                    failure_kind="unknown",
                    warnings=[f"lane: {type(result).__name__}: {result}"],
                )
            )
        else:
            outcomes.append(
                LaneOutcome(part_id="unknown", warnings=["lane: unexpected result"])
            )
    return outcomes


__all__ = [
    "LaneOutcome",
    "resolved_lane_limits",
    "run_all_lanes",
    "run_lane",
]
