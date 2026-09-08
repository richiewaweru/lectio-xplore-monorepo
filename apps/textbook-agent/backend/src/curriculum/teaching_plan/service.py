"""Curriculum-owned teaching planner entrypoints.

Print adapts to these helpers rather than owning a second planner. The
provider call lives in print.generation.whole_lesson.teaching_agent and is
bound at composition time so curriculum never imports print product modules.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from curriculum.teaching_plan.consumers import accept_approved_teaching_revision
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import TeachingRevisionStore

SharedTeachingRunner = Callable[..., Awaitable[Any]]
_shared_teaching_runner: SharedTeachingRunner | None = None


def bind_shared_teaching_runner(runner: SharedTeachingRunner) -> None:
    """Register the Print-owned teaching planner implementation."""
    global _shared_teaching_runner
    _shared_teaching_runner = runner


async def plan_shared_teaching(
    packet: Any,
    *,
    legality: Any = None,
    trace_id: str | None = None,
    generation_id: str | None = None,
    require_items: bool = True,
):
    """Run the single shared teaching planner (Print-adapted call site)."""
    runner = _shared_teaching_runner
    if runner is None:
        raise RuntimeError(
            "shared teaching planner is not bound; call "
            "bind_shared_teaching_runner from the Print composition root"
        )
    return await runner(
        packet,
        legality=legality,
        trace_id=trace_id,
        generation_id=generation_id,
        require_items=require_items,
    )


def load_approved_teaching_for_consumer(
    state: dict[str, Any],
    *,
    consumer: str,
    revision: int | None = None,
) -> TeachingPlan:
    return accept_approved_teaching_revision(
        state,
        consumer=consumer,  # type: ignore[arg-type]
        revision=revision,
    )


def edit_teaching_plan(
    state: dict[str, Any],
    plan: TeachingPlan | dict[str, Any],
    *,
    preparation_hash: str,
    teacher_note: str | None = None,
):
    store = TeachingRevisionStore(state)
    return store.edit_plan(
        plan,
        preparation_hash=preparation_hash,
        teacher_note=teacher_note,
    )
