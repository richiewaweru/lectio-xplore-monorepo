"""Restart-safe required-figure media orchestration for SharedDocument Runs."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.media import SharedFigureWorkOrder, build_figure_work_order
from document.shared_lesson.media_runtime import (
    MAX_CONCURRENT_MEDIA,
    MEDIA_STAGE,
    MediaReadiness,
    MediaRuntimeOutcome,
    MediaWorkItemJob,
    admit_figure_media_work_item,
    execute_figure_media_work_items,
    project_media_readiness,
)
from document.shared_lesson.models import FigureNode
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source
from document.shared_lesson.section_sources import build_section_sources
from document.shared_lesson.semantic_inputs import load_verified_semantic_inputs
from document.shared_lesson.work_item_inputs import load_verified_shared_lesson_inputs
from infra.database.models import GenerationWorkItemModel
from infra.generation_runtime import SourceIdentity, append_event


class SharedMediaDispatcherError(ValueError):
    """Durable accepted section inputs cannot safely produce media work."""


@dataclass(frozen=True)
class MediaDispatchOutcome:
    run_id: str
    readiness: MediaReadiness
    results: tuple[MediaRuntimeOutcome, ...] = ()


def _expired(item: Any, now: datetime) -> bool:
    expiry = item.lease_expires_at
    if expiry is None:
        return False
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)
    return expiry <= now


def _eligible(item: Any, now: datetime) -> bool:
    return item.status == "queued" or (item.status == "running" and _expired(item, now))


def _expected_shape(composition: Any) -> tuple[ExpectedNodeShape, ...]:
    return tuple(
        ExpectedNodeShape(
            id=item.id,
            kind=item.kind,
            teaching_block_id=item.teaching_block_id,
            semantic_role=item.semantic_role,
            task_spec_id=item.task_spec_id,
        )
        for item in composition.items
    )


def _source_facts(
    sourcebook: Any,
    plan_section: Any,
) -> tuple[Mapping[str, str], tuple[str, ...]]:
    entry_by_id = {entry.id: entry for entry in sourcebook.entries}
    refs: list[str] = []
    for block in plan_section.blocks:
        for ref in block.sourcebook_refs:
            if ref not in refs:
                refs.append(ref)
    if any(ref not in entry_by_id for ref in refs):
        missing = sorted(ref for ref in refs if ref not in entry_by_id)
        raise SharedMediaDispatcherError(
            f"accepted section references missing sourcebook facts: {missing!r}"
        )
    facts = {
        ref: json.dumps(
            entry_by_id[ref].content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for ref in refs
    }
    return facts, tuple(refs)


class SharedMediaDispatcher:
    """Admit and execute figure media on one existing owner-scoped Run."""

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        worker_id: str,
        executor: Any,
        concurrency: int = MAX_CONCURRENT_MEDIA,
        lease_seconds: int = 300,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must be non-empty")
        if concurrency < 1 or concurrency > MAX_CONCURRENT_MEDIA:
            raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENT_MEDIA}")
        self.session_factory = session_factory
        self.worker_id = worker_id
        self.executor = executor
        self.concurrency = concurrency
        self.lease_seconds = lease_seconds

    async def run_one(
        self,
        *,
        session: Any,
        run_id: str,
        owner_user_id: str,
        source: TeachingPlanSource,
        source_verifier: Callable[..., Any],
        now: datetime | None = None,
    ) -> MediaDispatchOutcome:
        identity = verify_teaching_plan_source(source)
        observed = source_verifier(session, identity)
        if hasattr(observed, "__await__"):
            observed = await observed
        if not isinstance(observed, SourceIdentity) or observed != identity:
            raise SharedMediaDispatcherError(
                "persisted source differs from the approved Teaching Plan"
            )

        semantic = await load_verified_semantic_inputs(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
        )
        sources_by_section = {
            section.slot_id: tuple(build_section_sources(semantic, section))
            for section in source.plan.sections
        }
        all_sources: list[Any] = []
        seen_source_ids: set[str] = set()
        for values in sources_by_section.values():
            for projected in values:
                if projected.id not in seen_source_ids:
                    seen_source_ids.add(projected.id)
                    all_sources.append(projected)
        accepted = await load_verified_shared_lesson_inputs(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            tasks=semantic.tasks,
            sources=tuple(all_sources),
        )

        expected_figures: list[tuple[str, str]] = []
        frozen_works: list[tuple[SharedFigureWorkOrder, Any]] = []
        compositions = {
            composition.section_slot_id: composition for composition in accepted.compositions
        }
        for section in accepted.sections:
            expected_shape = _expected_shape(compositions[section.id])
            plan_section = next(
                planned for planned in source.plan.sections if planned.slot_id == section.id
            )
            facts, approved_ids = _source_facts(semantic.sourcebook, plan_section)
            for node in section.nodes:
                if not isinstance(node, FigureNode):
                    continue
                expected_figures.append((section.id, node.id))
                work = build_figure_work_order(
                    source,
                    section,
                    figure_node_id=node.id,
                    expected_shape=expected_shape,
                    approved_source_facts=facts,
                    approved_source_ids=approved_ids,
                )
                frozen_works.append((work, section))

        admissions: list[tuple[SharedFigureWorkOrder, Any, Any]] = []
        for work, section in frozen_works:
            admitted = await admit_figure_media_work_item(
                session,
                run_id=run_id,
                owner_user_id=owner_user_id,
                source=source,
                work=work,
                accepted_section=section,
            )
            admissions.append((work, section, admitted.record))
            if admitted.created and work.warnings:
                # Non-blocking: surface label drift for Phase 2, never gate media.
                await append_event(
                    session,
                    run_id=run_id,
                    work_item_id=admitted.record.id,
                    event_type="figure_label_missing",
                    safe_payload={
                        "figure_node_id": work.figure_node_id,
                        "warnings": list(work.warnings),
                    },
                )
        await session.commit()
        # Stage sessions update these rows independently. Refresh the
        # admission-session view before deciding which queued/expired leaves
        # to dispatch; expire_on_commit=False must not hide a prior READY
        # result or resurrect an already-fenced lease.
        if admissions:
            await session.rollback()
            item_ids = tuple(item.id for _work, _section, item in admissions)
            fresh_items = list(
                (
                    await session.scalars(
                        select(GenerationWorkItemModel)
                        .where(GenerationWorkItemModel.id.in_(item_ids))
                        .execution_options(populate_existing=True)
                    )
                ).all()
            )
            fresh_by_id = {item.id: item for item in fresh_items}
            admissions = [
                (work, section, fresh_by_id.get(item.id, item))
                for work, section, item in admissions
            ]

        current = now or datetime.now(UTC).replace(tzinfo=None)
        if current.tzinfo is not None:
            current = current.astimezone(UTC).replace(tzinfo=None)
        results: tuple[MediaRuntimeOutcome, ...] = ()
        works_by_id = {item.id: work for work, _section, item in admissions}
        if admissions:
            async with AsyncExitStack() as stack:
                jobs: list[MediaWorkItemJob] = []
                for work, section, item in admissions:
                    if not _eligible(item, current):
                        continue
                    stage_session = await stack.enter_async_context(self.session_factory())
                    jobs.append(
                        MediaWorkItemJob(
                            session=stage_session,
                            work_item_id=item.id,
                            worker_id=self.worker_id,
                            source=source,
                            work=work,
                            accepted_section=section,
                            executor=self.executor,
                            status="queued",
                            lease_seconds=self.lease_seconds,
                        )
                    )
                if jobs:
                    results = await execute_figure_media_work_items(
                        jobs,
                        concurrency=self.concurrency,
                    )

        media_items = list(
            (
                await session.scalars(
                    select(GenerationWorkItemModel)
                    .where(
                        GenerationWorkItemModel.run_id == run_id,
                        GenerationWorkItemModel.stage == MEDIA_STAGE,
                    )
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        readiness = project_media_readiness(
            media_items,
            works_by_id,
            expected_required_work_item_ids=tuple(item.id for _w, _s, item in admissions),
            expected_figure_identities=tuple(expected_figures),
        )
        return MediaDispatchOutcome(run_id=run_id, readiness=readiness, results=results)


__all__ = ["MediaDispatchOutcome", "SharedMediaDispatcher", "SharedMediaDispatcherError"]
