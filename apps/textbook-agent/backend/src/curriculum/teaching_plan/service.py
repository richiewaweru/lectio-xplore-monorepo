"""Curriculum-owned teaching planner entrypoints.

Print adapts to these helpers rather than owning a second planner. The
provider call still lives in print.generation.whole_lesson.teaching_agent for
packet/legality coupling; this module is the stable curriculum façade.
"""

from __future__ import annotations

from typing import Any

from curriculum.teaching_plan.consumers import accept_approved_teaching_revision
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import TeachingRevisionStore


async def plan_shared_teaching(
    packet: Any,
    *,
    legality: Any = None,
    trace_id: str | None = None,
    generation_id: str | None = None,
    require_items: bool = True,
):
    """Run the single shared teaching planner (Print-adapted call site)."""
    from print.generation.whole_lesson.teaching_agent import run_lesson_approach_planner

    return await run_lesson_approach_planner(
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
