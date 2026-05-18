from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning.models import SectionBrief, SectionPlan, Stage1PlanFailure, StructuralPlan
from v3_blueprint.planning.persistence import persist_section_brief, persist_structural_plan
from v3_blueprint.planning.section_expander import (
    _call_stage2_section,
    _load_component_cards_for_section,
)
from v3_blueprint.planning.structural_planner import _call_stage1
from v3_blueprint.planning.validators import validate_section_brief, validate_structural_plan

EmitFn = Callable[[str, dict], Awaitable[None]]
log = logging.getLogger(__name__)


async def run_stage1_with_retry(
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    *,
    emit_event: EmitFn | None = None,
    generation_id: str | None = None,
    trace_id: str | None = None,
) -> StructuralPlan:

    errors: list[str] = []
    for attempt in range(1, 3):  # max 2 attempts
        try:
            plan = await _call_stage1(
                signals,
                form,
                resource_spec,
                generation_id=generation_id,
                trace_id=trace_id,
                previous_errors=errors if attempt == 2 else None,
            )
        except Exception as exc:
            import traceback
            print(
                f"\n[STAGE1 ATTEMPT {attempt} EXCEPTION]"
                f" generation_id={generation_id}"
                f" type={type(exc).__name__}"
                f"\n{traceback.format_exc()}",
                flush=True,
            )
            raise
        errors = validate_structural_plan(plan)

        if not errors:
            if generation_id:
                await persist_structural_plan(
                    generation_id,
                    plan,
                    signals=signals,
                    form=form,
                    resource_spec=resource_spec,
                )
            if emit_event:
                await emit_event("plan_ready", {
                    "generation_id": generation_id,
                    "plan": plan.model_dump(),
                })
            return plan

        if attempt == 1:
            log.warning("Stage 1 attempt 1 failed: %s", errors)
            # inject errors into next call — append to user message
            continue

    # Both attempts failed
    raise Stage1PlanFailure(errors=errors)
    # Caller surfaces to teacher immediately:
    # "Could not generate a valid lesson plan."
    # [Regenerate] [Edit inputs]
    # Max ~40s. Never silent.


async def run_stage2(
    plan: StructuralPlan,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    *,
    emit_event: EmitFn | None = None,
    generation_id: str | None = None,
    trace_id: str | None = None,
) -> list[SectionBrief]:

    completed_briefs: list[SectionBrief] = []

    for section in plan.sections:
        if emit_event:
            await emit_event("stage2_section_start", {
                "section_id": section.id,
                "generation_id": generation_id,
            })

        brief = await _run_section_with_retry(
            plan=plan,
            section=section,
            prior_briefs=completed_briefs,
            signals=signals,
            form=form,
            resource_spec=resource_spec,
            emit_event=emit_event,
            generation_id=generation_id,
            trace_id=trace_id,
        )

        if getattr(brief, "_failed", False):
            if emit_event:
                await emit_event("stage2_section_failed", {
                    "section_id": section.id,
                    "generation_id": generation_id,
                    "errors": getattr(brief, "_errors", []),
                })
        else:
            if emit_event:
                await emit_event("stage2_section_done", {
                    "section_id": section.id,
                    "generation_id": generation_id,
                })

        completed_briefs.append(brief)

        # Persist immediately after each section
        if generation_id:
            await persist_section_brief(generation_id, brief)

    failed = [b.section_id for b in completed_briefs if getattr(b, "_failed", False)]
    if emit_event:
        await emit_event("stage2_complete", {
            "generation_id": generation_id,
            "failed_sections": failed,
        })

    return completed_briefs


async def _run_section_with_retry(
    plan: StructuralPlan,
    section: SectionPlan,
    prior_briefs: list[SectionBrief],
    *,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    emit_event: EmitFn | None,
    generation_id: str | None,
    trace_id: str | None = None,
) -> SectionBrief:

    component_cards = _load_component_cards_for_section(section)
    errors: list[str] = []

    for attempt in range(1, 3):  # max 2 attempts
        if attempt == 2 and emit_event:
            await emit_event("stage2_section_retry", {
                "section_id": section.id,
                "attempt": 2,
                "generation_id": generation_id,
            })

        brief = await _call_stage2_section(
            plan=plan,
            section=section,
            prior_briefs=prior_briefs,
            component_cards=component_cards,
            signals=signals,
            form=form,
            resource_spec=resource_spec,
            generation_id=generation_id,
            trace_id=trace_id,
            previous_errors=errors if attempt == 2 else None,
        )
        errors = validate_section_brief(brief, section, plan.question_plan)

        if not errors:
            return brief

        if attempt == 1:
            log.warning(
                "Section '%s' attempt 1 failed: %s",
                section.id,
                errors,
            )
            continue

    # Both attempts failed — return placeholder
    placeholder = SectionBrief(
        section_id=section.id,
        components=[],
        question_briefs=[],
        visual_strategy=None,
    )
    placeholder._failed = True
    placeholder._errors = errors
    return placeholder


async def retry_failed_section(
    section_id: str,
    plan: StructuralPlan,
    stored_briefs: list[SectionBrief],
    *,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    emit_event: EmitFn | None = None,
    generation_id: str | None = None,
    trace_id: str | None = None,
) -> list[SectionBrief]:

    section = next(s for s in plan.sections if s.id == section_id)

    section_index = next(
        i for i, s in enumerate(plan.sections) if s.id == section_id
    )

    # Rebuild prior_briefs from stored successful briefs only
    # (only sections that come before this one and did not fail)
    prior_briefs = [
        b for b in stored_briefs
        if (
            next(i for i, s in enumerate(plan.sections) if s.id == b.section_id)
            < section_index
        )
        and not getattr(b, "_failed", False)
    ]

    new_brief = await _run_section_with_retry(
        plan=plan,
        section=section,
        prior_briefs=prior_briefs,
        signals=signals,
        form=form,
        resource_spec=resource_spec,
        emit_event=emit_event,
        generation_id=generation_id,
        trace_id=trace_id,
    )

    # Replace placeholder in stored list
    updated = [
        new_brief if b.section_id == section_id else b
        for b in stored_briefs
    ]

    # Persist updated brief
    if generation_id:
        await persist_section_brief(generation_id, new_brief)

    return updated
    # Caller re-attempts assemble_blueprint()
    # If still blocked: teacher sees remaining failed sections
    # If clear: proceed to _validate_blueprint() → execution


__all__ = [
    "_run_section_with_retry",
    "retry_failed_section",
    "run_stage1_with_retry",
    "run_stage2",
]
