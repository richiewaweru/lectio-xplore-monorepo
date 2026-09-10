"""Legacy dual-path convenience for scripts and integration tests (P08).

Not the product default. Production admits one explicitly selected path at a
time via ``admit_single_path`` / ``admit_realization``. Do not wire new
curriculum or units generation through this module; Phase M retires it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import admit_realization
from curriculum.teaching_plan.consumers import (
    accept_approved_teaching_revision,
    assert_identical_consumer_handoffs,
)
from curriculum.teaching_plan.coverage import instructional_coverage
from print.generation.native_production import teaching_plan_content_hash as print_hash
from print.generation.whole_lesson.repository import PageDocumentRepository


async def accept_shared_teaching_for_both(
    state: dict[str, Any],
) -> tuple[Any, Any]:
    """Both consumers accept the identical approved revision (no fixture swap)."""
    print_plan = accept_approved_teaching_revision(state, consumer="print")
    learn_plan = accept_approved_teaching_revision(state, consumer="learn")
    assert_identical_consumer_handoffs(state)
    return print_plan, learn_plan


async def link_print_realization(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    teaching_plan: Any,
    preparation_generation_id: str,
    pack_id: str | None = None,
    output_id: str | None = None,
    status: str = "ready",
) -> Any:
    """Admit/update the Print realization for the shared teaching revision."""
    plan_hash = print_hash(teaching_plan)
    row, _ = await admit_realization(
        session,
        path_lesson_id=path_lesson_id,
        path="print",
        teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        teaching_plan_revision=int(teaching_plan.revision or 1),
        teaching_plan_hash=plan_hash,
        preparation_generation_id=preparation_generation_id,
        pack_id=pack_id or preparation_generation_id,
        output_id=output_id or preparation_generation_id,
    )
    row.status = status
    if output_id:
        row.output_id = output_id
    await session.flush()
    return row


async def load_shared_teaching_state(
    session: AsyncSession,
    preparation_generation_id: str,
) -> dict[str, Any]:
    repo = PageDocumentRepository(session, preparation_generation_id)
    return await repo.load_page_generation_state()


__all__ = [
    "accept_shared_teaching_for_both",
    "instructional_coverage",
    "link_print_realization",
    "load_shared_teaching_state",
]
