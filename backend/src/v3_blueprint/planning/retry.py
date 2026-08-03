from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from pydantic_ai.exceptions import UnexpectedModelBehavior

from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from core.config import settings
from core.llm.runner import TruncatedCompletionError
from v3_blueprint.planning.models import (
    ComponentBrief,
    SectionBrief,
    SectionPlan,
    Stage1PlanFailure,
    StructuralPlan,
    stage2_brief_preview_payload,
)
from v3_blueprint.planning.persistence import persist_section_brief, persist_structural_plan
from v3_blueprint.planning.section_expander import (
    _call_stage2_section,
    _load_component_cards_for_section,
)
from v3_blueprint.planning.structural_planner import _call_stage1
from v3_blueprint.planning.validators import validate_section_brief, validate_structural_plan
from v3_blueprint.skeletons import load_skeleton_catalog
from v3_blueprint.shadow import record_skeleton_shadow

EmitFn = Callable[[str, dict], Awaitable[None]]
log = logging.getLogger(__name__)


def _stage2_parallel_enabled() -> bool:
    return os.getenv("V3_STAGE2_PARALLEL", "true").strip().lower() != "false"


def skip_expander_enabled() -> bool:
    """Phase 0 experiment: skip Stage 2 expander LLM when true (default false)."""
    return os.getenv("V3_SKIP_EXPANDER", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def synthesize_section_brief(section: SectionPlan) -> SectionBrief:
    """Build a reversible brief from plan slots so assembler/writer keep working.

    content_intent is the ComponentSlot.purpose; visual_strategy is left unset
    (Phase 0 A/B should prefer lessons without visual_required).
    """
    return SectionBrief(
        section_id=section.id,
        components=[
            ComponentBrief(component_id=slot.slug, content_intent=slot.purpose)
            for slot in section.components
        ],
        visual_strategy=None,
    )


def _failed_placeholder(section_id: str, errors: list[str]) -> SectionBrief:
    placeholder = SectionBrief(
        section_id=section_id,
        components=[],
        visual_strategy=None,
    )
    placeholder._failed = True
    placeholder._errors = errors
    return placeholder


def _is_structured_output_validation_failure(exc: UnexpectedModelBehavior) -> bool:
    """Keep output-schema failures retryable without masking provider failures."""
    message = exc.message.lower()
    return "maximum retries" in message and (
        "result validation" in message or "output validation" in message
    )


async def run_stage1_with_retry(
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    *,
    emit_event: EmitFn | None = None,
    generation_id: str | None = None,
    trace_id: str | None = None,
) -> StructuralPlan:

    skeleton_catalog = load_skeleton_catalog().data
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
                skeleton_catalog=skeleton_catalog,
            )
        except TruncatedCompletionError as exc:
            import traceback

            print(
                f"\n[STAGE1 ATTEMPT {attempt} EXCEPTION]"
                f" generation_id={generation_id}"
                f" type={type(exc).__name__}"
                f"\n{traceback.format_exc()}",
                flush=True,
            )
            if attempt == 1:
                log.warning("Stage 1 attempt 1 truncated: %s", exc)
                continue
            raise Stage1PlanFailure(errors=[str(exc)]) from exc
        except UnexpectedModelBehavior as exc:
            import traceback

            print(
                f"\n[STAGE1 ATTEMPT {attempt} EXCEPTION]"
                f" generation_id={generation_id}"
                f" type={type(exc).__name__}"
                f"\n{traceback.format_exc()}",
                flush=True,
            )
            if not _is_structured_output_validation_failure(exc):
                raise
            errors = [f"Stage 1 structured output could not be validated: {exc}"]
            if attempt == 1:
                log.warning("Stage 1 attempt 1 output validation failed: %s", exc)
                continue
            raise Stage1PlanFailure(errors=errors) from exc
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
        errors = validate_structural_plan(
            plan,
            resource_spec,
            skeleton_catalog=skeleton_catalog,
        )

        if not errors:
            if generation_id:
                await persist_structural_plan(
                    generation_id,
                    plan,
                    signals=signals,
                    form=form,
                    resource_spec=resource_spec,
                )
                if settings.v2_skeleton_shadow_enabled:
                    try:
                        await record_skeleton_shadow(
                            generation_id=generation_id,
                            plan=plan,
                            form=form,
                        )
                    except Exception:  # noqa: BLE001
                        log.exception(
                            "Skeleton shadow recording failed; generation continues; generation_id=%s",
                            generation_id,
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
    from core.config import settings

    print(
        f"\n[STAGE2 START] generation_id={generation_id}"
        f" sections={[s.id for s in plan.sections]}"
        f" parallel={_stage2_parallel_enabled()}"
        f" skip_expander={skip_expander_enabled()}"
        f" timeout_stage2_section={settings.v3_timeout_stage2_section_seconds}s",
        flush=True,
    )

    async def persist_brief(brief: SectionBrief) -> None:
        if generation_id:
            await persist_section_brief(generation_id, brief)

    if not _stage2_parallel_enabled() or len(plan.sections) <= 1:
        completed_briefs = await _run_stage2_serial(
            plan,
            plan.sections,
            signals=signals,
            form=form,
            resource_spec=resource_spec,
            emit_event=emit_event,
            generation_id=generation_id,
            trace_id=trace_id,
            persist_brief=persist_brief,
        )
    else:
        persistence_lock = asyncio.Lock()

        async def run_section(section: SectionPlan) -> SectionBrief:
            # Parallel mode: plan-derived continuity only; never feed prior briefs.
            return await _run_stage2_section(
                plan,
                section,
                [],
                signals=signals,
                form=form,
                resource_spec=resource_spec,
                emit_event=emit_event,
                generation_id=generation_id,
                trace_id=trace_id,
                persist_brief=persist_brief,
                persistence_lock=persistence_lock,
            )

        fan_out_results = await asyncio.gather(
            *(run_section(section) for section in plan.sections),
            return_exceptions=True,
        )
        completed_briefs = []
        for section, result in zip(plan.sections, fan_out_results, strict=True):
            if isinstance(result, Exception):
                errors = [f"{type(result).__name__}: {str(result)[:400]}"]
                brief = _failed_placeholder(section.id, errors)
                print(
                    f"\n[STAGE2 SECTION EXCEPTION-ISOLATED] generation_id={generation_id}"
                    f" section_id={section.id}"
                    f" type={type(result).__name__}",
                    flush=True,
                )
                if emit_event:
                    await emit_event("stage2_section_failed", {
                        "section_id": section.id,
                        "generation_id": generation_id,
                        "errors": errors,
                    })
                async with persistence_lock:
                    await persist_brief(brief)
                completed_briefs.append(brief)
            else:
                completed_briefs.append(result)

    return await _complete_stage2(
        completed_briefs,
        emit_event=emit_event,
        generation_id=generation_id,
    )


async def _run_stage2_serial(
    plan: StructuralPlan,
    sections: list[SectionPlan],
    *,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    emit_event: EmitFn | None,
    generation_id: str | None,
    trace_id: str | None,
    persist_brief: Callable[[SectionBrief], Awaitable[None]],
    initial_briefs: list[SectionBrief] | None = None,
) -> list[SectionBrief]:
    completed_briefs = list(initial_briefs or [])
    for section in sections:
        brief = await _run_stage2_section(
            plan,
            section,
            completed_briefs,
            signals=signals,
            form=form,
            resource_spec=resource_spec,
            emit_event=emit_event,
            generation_id=generation_id,
            trace_id=trace_id,
            persist_brief=persist_brief,
        )
        completed_briefs.append(brief)
    return completed_briefs


async def _run_stage2_section(
    plan: StructuralPlan,
    section: SectionPlan,
    prior_briefs: list[SectionBrief],
    *,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    emit_event: EmitFn | None,
    generation_id: str | None,
    trace_id: str | None,
    persist_brief: Callable[[SectionBrief], Awaitable[None]],
    persistence_lock: asyncio.Lock | None = None,
) -> SectionBrief:
        print(
            f"\n[STAGE2 SECTION START] generation_id={generation_id}"
            f" section_id={section.id}"
            f" role={section.role}"
            f" components={[c.slug for c in section.components]}",
            flush=True,
        )
        if emit_event:
            await emit_event("stage2_section_start", {
                "section_id": section.id,
                "generation_id": generation_id,
            })

        brief = await _run_section_with_retry(
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

        if getattr(brief, "_failed", False):
            print(
                f"\n[STAGE2 SECTION FAILED] generation_id={generation_id}"
                f" section_id={section.id}"
                f" errors={getattr(brief, '_errors', [])}",
                flush=True,
            )
            if emit_event:
                await emit_event("stage2_section_failed", {
                    "section_id": section.id,
                    "generation_id": generation_id,
                    "errors": getattr(brief, "_errors", []),
                })
        else:
            print(
                f"\n[STAGE2 SECTION DONE] generation_id={generation_id}"
                f" section_id={section.id}"
                f" components_briefed={len(brief.components)}"
                f" has_visual={'yes' if brief.visual_strategy else 'no'}",
                flush=True,
            )
            if emit_event:
                await emit_event("stage2_section_done", {
                    "section_id": section.id,
                    "generation_id": generation_id,
                    "brief": stage2_brief_preview_payload(brief),
                })

        # Persist immediately after each section. Parallel callers serialize this
        # read-modify-write operation so completed briefs cannot overwrite peers.
        if persistence_lock is None:
            await persist_brief(brief)
        else:
            async with persistence_lock:
                await persist_brief(brief)

        return brief


async def _complete_stage2(
    completed_briefs: list[SectionBrief],
    *,
    emit_event: EmitFn | None,
    generation_id: str | None,
) -> list[SectionBrief]:
    failed = [b.section_id for b in completed_briefs if getattr(b, "_failed", False)]
    print(
        f"\n[STAGE2 COMPLETE] generation_id={generation_id}"
        f" total={len(completed_briefs)}"
        f" failed={failed}",
        flush=True,
    )
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

    if skip_expander_enabled():
        brief = synthesize_section_brief(section)
        print(
            f"\n[STAGE2 SKIP EXPANDER] generation_id={generation_id}"
            f" section_id={section.id}"
            f" components={len(brief.components)}",
            flush=True,
        )
        return brief

    component_cards = _load_component_cards_for_section(section)
    errors: list[str] = []

    for attempt in range(1, 3):  # max 2 attempts
        print(
            f"\n[STAGE2 CALL] generation_id={generation_id}"
            f" section_id={section.id}"
            f" attempt={attempt}",
            flush=True,
        )
        if attempt == 2 and emit_event:
            await emit_event("stage2_section_retry", {
                "section_id": section.id,
                "attempt": 2,
                "generation_id": generation_id,
            })

        try:
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
        except UnexpectedModelBehavior as exc:
            import traceback

            print(
                f"\n[STAGE2 CALL EXCEPTION] generation_id={generation_id}"
                f" section_id={section.id}"
                f" attempt={attempt}"
                f" type={type(exc).__name__}"
                f"\nmessage={str(exc)}"
                f"\n{traceback.format_exc()}",
                flush=True,
            )
            if not _is_structured_output_validation_failure(exc):
                raise
            errors = [f"Stage 2 structured output could not be validated: {exc}"]
        except Exception as exc:
            import traceback

            print(
                f"\n[STAGE2 CALL EXCEPTION] generation_id={generation_id}"
                f" section_id={section.id}"
                f" attempt={attempt}"
                f" type={type(exc).__name__}"
                f"\nmessage={str(exc)}"
                f"\n{traceback.format_exc()}",
                flush=True,
            )
            raise
        else:
            errors = validate_section_brief(brief, section, plan.question_plan)

        if not errors:
            print(
                f"\n[STAGE2 CALL OK] generation_id={generation_id}"
                f" section_id={section.id}"
                f" attempt={attempt}",
                flush=True,
            )
            return brief

        print(
            f"\n[STAGE2 VALIDATION FAIL] generation_id={generation_id}"
            f" section_id={section.id}"
            f" attempt={attempt}"
            f" errors={errors}",
            flush=True,
        )
        if attempt == 1:
            log.warning(
                "Section '%s' attempt 1 failed: %s",
                section.id,
                errors,
            )
            continue

    # Both attempts failed — return placeholder
    print(
        f"\n[STAGE2 SECTION EXHAUSTED] generation_id={generation_id}"
        f" section_id={section.id}"
        f" final_errors={errors}",
        flush=True,
    )
    return _failed_placeholder(section.id, errors)


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
    "_failed_placeholder",
    "_run_section_with_retry",
    "retry_failed_section",
    "run_stage1_with_retry",
    "run_stage2",
]
