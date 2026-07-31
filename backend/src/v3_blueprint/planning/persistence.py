from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import ConceptCardModel, GenerationModel
from core.database.session import async_session_factory
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning.models import (
    SectionBrief,
    StructuralPlan,
    VariantSpec,
)

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
    async with _session_scope(session) as (db, should_commit):
        await persist_chunked_state(
            generation_id,
            {
                "stage": "plan_ready",
                "structural_plan": plan.model_dump(mode="json"),
                "section_briefs": {s.id: None for s in plan.sections},
                "failed_sections": [],
                "context": {
                    "signals": (
                        signals.model_dump(mode="json")
                        if signals is not None
                        else None
                    ),
                    "form": form.model_dump(mode="json") if form is not None else None,
                    "resource_spec": resource_spec,
                },
            },
            session=db,
        )

        generation = await db.get(GenerationModel, generation_id)
        if generation is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        pack_id = generation.pack_id or generation_id

        for card in plan.cards:
            existing_result = await db.execute(
                select(ConceptCardModel).where(
                    ConceptCardModel.pack_id == pack_id,
                    ConceptCardModel.slug == card.id,
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing is not None and existing.teacher_edited:
                continue

            payload = {
                "pack_id": pack_id,
                "slug": card.id,
                "title": card.title,
                "objective": card.objective,
                "prereqs": list(card.prereqs),
                "misconceptions": [
                    misconception.model_dump(mode="json")
                    for misconception in card.misconceptions
                ],
            }
            if existing is None:
                db.add(ConceptCardModel(id=f"{pack_id}:{card.id}", **payload))
            else:
                for field, value in payload.items():
                    setattr(existing, field, value)

        if should_commit:
            await db.commit()


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
    from v3_blueprint.planning.retry import (
        _complete_stage2,
        _failed_placeholder,
        _run_stage2_section,
        _run_stage2_serial,
        _stage2_parallel_enabled,
    )

    async with _session_scope(session) as (db, _):
        state = await load_chunked_state(generation_id, db)
        plan = StructuralPlan(**state["structural_plan"])
        variant_raw = state.get("variant_spec")
        if isinstance(variant_raw, dict):
            plan = plan.with_variant(VariantSpec.model_validate(variant_raw))

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

        async def persist_brief(brief: SectionBrief) -> None:
            await persist_section_brief(generation_id, brief, db)

        if not _stage2_parallel_enabled() or len(remaining) <= 1:
            completed_briefs = await _run_stage2_serial(
                plan,
                remaining,
                signals=signals,
                form=form,
                resource_spec=resource_spec,
                emit_event=emit_event,
                generation_id=generation_id,
                trace_id=None,
                persist_brief=persist_brief,
                initial_briefs=completed_briefs,
            )
        else:
            persistence_lock = asyncio.Lock()
            briefs_by_id = {brief.section_id: brief for brief in completed_briefs}
            anchor_section = plan.sections[0]
            anchor = briefs_by_id.get(anchor_section.id)

            async def run_section(section, prior_briefs):  # noqa: ANN001
                return await _run_stage2_section(
                    plan,
                    section,
                    prior_briefs,
                    signals=signals,
                    form=form,
                    resource_spec=resource_spec,
                    emit_event=emit_event,
                    generation_id=generation_id,
                    trace_id=None,
                    persist_brief=persist_brief,
                    persistence_lock=persistence_lock,
                )

            if anchor is None:
                anchor = await run_section(anchor_section, [])
                briefs_by_id[anchor.section_id] = anchor

            prior_briefs = [] if getattr(anchor, "_failed", False) else [anchor]
            fan_out_sections = [
                section
                for section in remaining
                if section.id != anchor_section.id
            ]
            fan_out_results = await asyncio.gather(
                *(run_section(section, prior_briefs) for section in fan_out_sections),
                return_exceptions=True,
            )
            fan_out_briefs: list[SectionBrief] = []
            for section, result in zip(fan_out_sections, fan_out_results, strict=True):
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
                    fan_out_briefs.append(brief)
                else:
                    fan_out_briefs.append(result)
            briefs_by_id.update({brief.section_id: brief for brief in fan_out_briefs})
            completed_briefs = [
                briefs_by_id[section.id]
                for section in plan.sections
                if section.id in briefs_by_id
            ]

        ordered_briefs = {brief.section_id: brief for brief in completed_briefs}
        completed_briefs = [
            ordered_briefs[section.id]
            for section in plan.sections
            if section.id in ordered_briefs
        ]
        return await _complete_stage2(
            completed_briefs,
            emit_event=emit_event,
            generation_id=generation_id,
        )


__all__ = [
    "load_chunked_state",
    "persist_chunked_state",
    "persist_section_brief",
    "persist_structural_plan",
    "resume_stage2",
]
