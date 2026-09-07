"""Stage-2 lanes: brief → prose → questions with no global brief barrier.

Each section runs as an independent lane. Briefs no longer complete for every
section before any prose starts; assembly of the full blueprint happens after
lanes finish (reshape deferred item: move brief into run_lane).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from learn.generation.contracts import GenerationInputForm as V3InputForm
from learn.generation.contracts import GenerationSignalSummary as V3SignalSummary
from v3_blueprint.planning.assembler import assemble_blueprint
from v3_blueprint.planning.models import SectionBrief, StructuralPlan
from v3_blueprint.planning.persistence import (
    load_chunked_state,
    persist_section_brief,
)
from v3_blueprint.planning.retry import (
    _failed_placeholder,
    _run_stage2_section,
)
from v3_execution.compile_orders import compile_execution_bundle
from v3_execution.config.policy import ship_with_holes_enabled
from v3_execution.config.timeouts import V3_TIMEOUTS
from v3_execution.executors.question_writer import execute_questions
from v3_execution.executors.section_writer import execute_section
from v3_execution.runtime.lanes import (
    LaneOutcome,
    resolved_lane_limits,
    run_all_lanes,
    run_lane,
)

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def _brief_from_payload(payload: Any, *, section_id: str) -> SectionBrief:
    if isinstance(payload, SectionBrief):
        return payload
    if isinstance(payload, dict):
        try:
            return SectionBrief.model_validate(payload)
        except Exception:  # noqa: BLE001
            return _failed_placeholder(section_id, ["stored brief payload invalid"])
    return _failed_placeholder(section_id, ["missing brief payload"])


async def run_stage2_lanes(
    generation_id: str,
    *,
    plan: StructuralPlan,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict[str, Any],
    emit_event: EmitFn | None = None,
    template_id: str = "guided-concept-path",
) -> list[SectionBrief]:
    """Run per-section lanes (brief → prose → questions) in parallel.

    Returns briefs in plan section order for full-blueprint assembly. Prose and
    question blocks are stored as generation_steps so the later runner pass can
    skip and reload them.
    """
    limits = resolved_lane_limits()
    print(
        f"\n[STAGE2 LANES START] generation_id={generation_id}"
        f" sections={[s.id for s in plan.sections]}"
        f" lane_concurrency={limits['lane']}"
        f" lane_budget_seconds={limits['budget_seconds']}",
        flush=True,
    )

    # Resume: reuse any briefs already folded into chunked state.
    state = await load_chunked_state(generation_id)
    existing_briefs: dict[str, SectionBrief] = {}
    raw_briefs = state.get("section_briefs") or {}
    if isinstance(raw_briefs, dict):
        for section_id, raw in raw_briefs.items():
            if isinstance(raw, dict):
                try:
                    existing_briefs[str(section_id)] = SectionBrief.model_validate(raw)
                except Exception:  # noqa: BLE001
                    continue

    persistence_lock = asyncio.Lock()
    subject = form.subject.strip() or "General"
    title = form.topic.strip() or "Generated Lesson"
    resource_type = str(resource_spec.get("resource_type") or "lesson")
    blueprint_id = str(uuid.uuid4())

    def _lane_factory_for(section) -> Callable[[], Awaitable[LaneOutcome]]:  # noqa: ANN001
        part_id = section.id

        async def _factory() -> LaneOutcome:
            brief_holder: dict[str, SectionBrief] = {}

            async def _brief() -> SectionBrief:
                if part_id in existing_briefs:
                    brief = existing_briefs[part_id]
                    brief_holder["brief"] = brief
                    return brief

                async def persist_brief(brief: SectionBrief) -> None:
                    async with persistence_lock:
                        await persist_section_brief(generation_id, brief)

                brief = await _run_stage2_section(
                    plan,
                    section,
                    [],  # plan-derived continuity only (parallel lanes)
                    signals=signals,
                    form=form,
                    resource_spec=resource_spec,
                    emit_event=emit_event,
                    generation_id=generation_id,
                    trace_id=None,
                    persist_brief=persist_brief,
                    persistence_lock=None,  # persist_brief already locks
                )
                brief_holder["brief"] = brief
                return brief

            async def _resolve_brief() -> SectionBrief:
                brief = brief_holder.get("brief")
                if brief is not None:
                    return brief
                if part_id in existing_briefs:
                    brief = existing_briefs[part_id]
                    brief_holder["brief"] = brief
                    return brief
                # Resume path: brief step exists but was not in the folded map yet.
                refreshed = await load_chunked_state(generation_id)
                raw = (refreshed.get("section_briefs") or {}).get(part_id)
                brief = _brief_from_payload(raw, section_id=part_id)
                brief_holder["brief"] = brief
                return brief

            async def _prose() -> list[Any]:
                brief = await _resolve_brief()
                if getattr(brief, "_failed", False):
                    return []
                single_bp = assemble_blueprint(
                    plan,
                    [brief],
                    subject=subject,
                    title=title,
                    resource_type=resource_type,
                    ship_with_holes=ship_with_holes_enabled(),
                )
                if not single_bp.sections:
                    return []
                bundle = compile_execution_bundle(
                    single_bp,
                    generation_id=generation_id,
                    blueprint_id=blueprint_id,
                    template_id=template_id,
                )
                if not bundle.section_orders:
                    return []
                order = bundle.section_orders[0]
                return await asyncio.wait_for(
                    execute_section(
                        order,
                        emit_event or _noop_emit,
                        trace_id=None,
                        generation_id=generation_id,
                    ),
                    timeout=V3_TIMEOUTS["section_writer"],
                )

            async def _questions() -> list[Any]:
                brief = await _resolve_brief()
                if getattr(brief, "_failed", False):
                    return []
                single_bp = assemble_blueprint(
                    plan,
                    [brief],
                    subject=subject,
                    title=title,
                    resource_type=resource_type,
                    ship_with_holes=ship_with_holes_enabled(),
                )
                bundle = compile_execution_bundle(
                    single_bp,
                    generation_id=generation_id,
                    blueprint_id=blueprint_id,
                    template_id=template_id,
                )
                if not bundle.question_orders:
                    return []
                order = bundle.question_orders[0]
                return await asyncio.wait_for(
                    execute_questions(
                        order,
                        emit_event or _noop_emit,
                        trace_id=None,
                        generation_id=generation_id,
                    ),
                    timeout=V3_TIMEOUTS["question_writer"],
                )

            return await run_lane(
                generation_id=generation_id,
                part_id=part_id,
                variant_id="everyone",
                brief_coro_factory=_brief,
                prose_coro_factory=_prose,
                questions_coro_factory=_questions,
                emit_event=emit_event,
            )

        return _factory

    async def _noop_emit(_event: str, _payload: dict[str, Any]) -> None:
        return None

    outcomes = await run_all_lanes(
        lane_factories=[_lane_factory_for(section) for section in plan.sections],
    )
    by_part = {outcome.part_id: outcome for outcome in outcomes}

    briefs: list[SectionBrief] = []
    for section in plan.sections:
        outcome = by_part.get(section.id)
        if outcome is None:
            briefs.append(
                _failed_placeholder(section.id, ["lane outcome missing"])
            )
            continue
        if outcome.brief is not None:
            brief = _brief_from_payload(outcome.brief, section_id=section.id)
        elif section.id in existing_briefs:
            brief = existing_briefs[section.id]
        else:
            brief = _failed_placeholder(
                section.id,
                [f"lane failed at {outcome.failed_step or 'unknown'}"],
            )
            brief._failed = True
        if outcome.failed_step == "brief":
            brief._failed = True
        briefs.append(brief)

    failed = [b.section_id for b in briefs if getattr(b, "_failed", False)]
    print(
        f"\n[STAGE2 LANES COMPLETE] generation_id={generation_id}"
        f" total={len(briefs)} failed={failed}",
        flush=True,
    )
    if emit_event:
        await emit_event(
            "stage2_complete",
            {
                "generation_id": generation_id,
                "failed_sections": failed,
            },
        )
    return briefs


__all__ = ["run_stage2_lanes"]
