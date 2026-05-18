from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import async_session_factory
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning.models import SectionBrief, StructuralPlan

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


@asynccontextmanager
async def _session_scope(session: AsyncSession | None):
    if session is not None:
        yield session, False
        return
    async with async_session_factory() as managed:
        yield managed, True


async def _read_chunked_state(
    generation_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    result = await session.execute(
        text("SELECT chunked_state_json FROM generations WHERE id = :generation_id"),
        {"generation_id": generation_id},
    )
    row = result.first()
    if row is None:
        raise ValueError(f"Generation '{generation_id}' not found")
    raw = row[0]
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


async def _write_chunked_state(
    generation_id: str,
    state: dict[str, Any],
    session: AsyncSession,
) -> None:
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "postgresql":
        await session.execute(
            text(
                "UPDATE generations "
                "SET chunked_state_json = CAST(:state AS JSONB) "
                "WHERE id = :generation_id"
            ),
            {"generation_id": generation_id, "state": json.dumps(state)},
        )
    else:
        await session.execute(
            text(
                "UPDATE generations "
                "SET chunked_state_json = :state "
                "WHERE id = :generation_id"
            ),
            {"generation_id": generation_id, "state": json.dumps(state)},
        )


async def persist_chunked_state(
    generation_id: str,
    update: dict,
    session: AsyncSession | None = None,
) -> None:
    async with _session_scope(session) as (db, should_commit):
        current = await _read_chunked_state(generation_id, db)
        current.update(update)
        await _write_chunked_state(generation_id, current, db)
        if should_commit:
            await db.commit()


async def persist_structural_plan(
    generation_id: str,
    plan: StructuralPlan,
    session: AsyncSession | None = None,
    *,
    signals: V3SignalSummary | None = None,
    form: V3InputForm | None = None,
    resource_spec: dict | None = None,
) -> None:
    await persist_chunked_state(generation_id, {
        "stage": "plan_ready",
        "structural_plan": plan.model_dump(mode="json"),
        "section_briefs": {s.id: None for s in plan.sections},
        "failed_sections": [],
        "context": {
            "signals": signals.model_dump(mode="json") if signals is not None else None,
            "form": form.model_dump(mode="json") if form is not None else None,
            "resource_spec": resource_spec,
        },
    }, session=session)


async def persist_section_brief(
    generation_id: str,
    brief: SectionBrief,
    session: AsyncSession | None = None,
) -> None:
    async with _session_scope(session) as (db, should_commit):
        current = await _read_chunked_state(generation_id, db)

        section_briefs = current.get("section_briefs", {})
        if getattr(brief, "_failed", False):
            section_briefs[brief.section_id] = None
            failed = current.get("failed_sections", [])
            if brief.section_id not in failed:
                failed.append(brief.section_id)
            current["failed_sections"] = failed
            current["stage"] = f"section_{brief.section_id}_failed"
        else:
            section_briefs[brief.section_id] = brief.model_dump(mode="json")
            failed = [
                section
                for section in current.get("failed_sections", [])
                if section != brief.section_id
            ]
            current["failed_sections"] = failed
            current["stage"] = f"section_{brief.section_id}_complete"

        current["section_briefs"] = section_briefs
        await _write_chunked_state(generation_id, current, db)
        if should_commit:
            await db.commit()


async def load_chunked_state(
    generation_id: str,
    session: AsyncSession | None = None,
) -> dict:
    async with _session_scope(session) as (db, _):
        state = await _read_chunked_state(generation_id, db)
        if not state:
            raise ValueError(
                f"No chunked state found for generation {generation_id}"
            )
        return state


async def resume_stage2(
    generation_id: str,
    session: AsyncSession | None = None,
    emit_event: EmitFn | None = None,
) -> list[SectionBrief]:
    from v3_blueprint.planning.retry import _run_section_with_retry

    async with _session_scope(session) as (db, _):
        state = await load_chunked_state(generation_id, db)
        plan = StructuralPlan(**state["structural_plan"])

        # Rebuild completed briefs from persisted state
        completed_briefs: list[SectionBrief] = []
        for section in plan.sections:
            persisted = state["section_briefs"].get(section.id)
            if persisted is not None:
                completed_briefs.append(SectionBrief(**persisted))

        # Find remaining sections
        completed_ids = {b.section_id for b in completed_briefs}
        remaining = [s for s in plan.sections if s.id not in completed_ids]

        context = state.get("context") or {}
        signals_raw = context.get("signals")
        form_raw = context.get("form")
        resource_spec = context.get("resource_spec")
        if not isinstance(signals_raw, dict) or not isinstance(form_raw, dict):
            raise ValueError(
                "Cannot resume Stage 2: missing persisted signals/form context."
            )
        signals = V3SignalSummary(**signals_raw)
        form = V3InputForm(**form_raw)
        if not isinstance(resource_spec, dict):
            raise ValueError(
                "Cannot resume Stage 2: missing persisted resource_spec context."
            )

        print(
            f"\n[STAGE2 START] generation_id={generation_id}"
            f" sections={[s.id for s in plan.sections]}",
            flush=True,
        )

        # Continue loop from next incomplete section
        for section in remaining:
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
                prior_briefs=completed_briefs,
                signals=signals,
                form=form,
                resource_spec=resource_spec,
                emit_event=emit_event,
                generation_id=generation_id,
            )
            completed_briefs.append(brief)
            await persist_section_brief(generation_id, brief, db)
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
                    f" questions_briefed={len(brief.question_briefs)}"
                    f" has_visual={'yes' if brief.visual_strategy else 'no'}",
                    flush=True,
                )
                if emit_event:
                    await emit_event("stage2_section_done", {
                        "section_id": section.id,
                        "generation_id": generation_id,
                    })

        failed_sections = [
            brief.section_id
            for brief in completed_briefs
            if getattr(brief, "_failed", False)
        ]
        print(
            f"\n[STAGE2 COMPLETE] generation_id={generation_id}"
            f" total={len(completed_briefs)}"
            f" failed={failed_sections}",
            flush=True,
        )
        if emit_event:
            await emit_event("stage2_complete", {
                "generation_id": generation_id,
                "failed_sections": failed_sections,
            })

        return completed_briefs


__all__ = [
    "load_chunked_state",
    "persist_chunked_state",
    "persist_section_brief",
    "persist_structural_plan",
    "resume_stage2",
]
