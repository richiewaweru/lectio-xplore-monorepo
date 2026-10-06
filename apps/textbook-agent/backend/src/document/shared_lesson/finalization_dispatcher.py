"""Owner-scoped adapter for the atomic SharedLessonDocument finalizer.

This module only gathers and verifies durable inputs for an existing Run.  It
does not author content or accept caller-supplied task, source, media, or
required-media maps.  The atomic finalizer remains the only code that writes a
draft, promotes READY, and finalizes the generic Run.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from document.shared_lesson.approved_source import (
    ApprovedSourceVerificationError,
    load_current_approved_teaching_plan_source,
    make_approved_source_verifier,
)
from document.shared_lesson.finalizer import (
    SharedLessonFinalizationError,
    SharedLessonFinalizationRequest,
    SharedLessonFinalizationResult,
    _verify_boundary_coverage,
    _verify_document_qa_matches_handoff,
    _verify_durable_inputs_match_handoff,
    finalize_shared_lesson_document,
    resolve_review_structural_document,
)
from document.shared_lesson.handoff import SharedLessonHandoffEvidence
from document.shared_lesson.media import (
    BoundFigureMediaOutcome,
    SharedFigureMediaError,
    bind_durable_media_outcome,
)
from document.shared_lesson.media_runtime import MEDIA_STAGE
from document.shared_lesson.models import FigureNode
from document.shared_lesson.qa_runtime import (
    DOCUMENT_QA_STAGE,
    DocumentQARuntimeError,
    load_verified_document_qa,
)
from document.shared_lesson.section_sources import SectionSourceError, build_section_sources
from document.shared_lesson.semantic_inputs import (
    SemanticInputError,
    load_verified_semantic_inputs,
)
from document.shared_lesson.work_item_inputs import (
    SharedLessonInputError,
    load_verified_shared_lesson_inputs,
)
from infra.database.models import GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import active_work_items
from infra.generation_runtime.repository import ArtifactLoader


class SharedLessonFinalizationDispatchError(ValueError):
    """Durable finalization inputs cannot be assembled for this Run."""


@dataclass(frozen=True)
class SharedLessonFinalizationDispatchOutcome:
    """Explicit projection of a finalization attempt."""

    status: Literal["ready", "blocked"]
    result: SharedLessonFinalizationResult | None = None
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"


async def _active_run_items(
    session: AsyncSession, *, run_id: str
) -> tuple[tuple[GenerationWorkItemModel, ...], tuple[GenerationWorkItemModel, ...]]:
    rows = tuple(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    return rows, active_work_items(rows)


def _all_section_sources(semantic: Any, source: Any) -> tuple[Any, ...]:
    projected: list[Any] = []
    by_id: dict[str, Any] = {}
    for plan_section in source.plan.sections:
        section_sources = build_section_sources(semantic, plan_section)
        for section_source in section_sources:
            previous = by_id.get(section_source.id)
            if previous is None:
                by_id[section_source.id] = section_source
                projected.append(section_source)
            elif previous != section_source:
                raise SectionSourceError(
                    f"durable sourcebook entry {section_source.id!r} has conflicting projections"
                )
    return tuple(projected)


def _required_media_map(
    results: Sequence[BoundFigureMediaOutcome],
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for result in results:
        grouped.setdefault(result.section_id, []).append(result.figure_node_id)
    return {section_id: tuple(figure_ids) for section_id, figure_ids in grouped.items()}


def _durable_media_results(
    *,
    document: Any,
    active_items: Sequence[GenerationWorkItemModel],
) -> tuple[tuple[BoundFigureMediaOutcome, ...], dict[str, tuple[str, ...]]]:
    expected = tuple(
        (section.id, node.id)
        for section in document.sections
        for node in section.nodes
        if isinstance(node, FigureNode)
    )
    media_items = tuple(
        item
        for item in active_items
        if item.stage == MEDIA_STAGE or item.item_key.startswith("media:")
    )
    if len(media_items) != len(expected):
        raise SharedLessonFinalizationDispatchError(
            "durable media leaves do not cover exactly the document figures"
        )

    results: list[BoundFigureMediaOutcome] = []
    seen: set[tuple[str, str]] = set()
    for item in media_items:
        if item.status != "ready" or item.output_json is None or not item.output_hash:
            raise SharedLessonFinalizationDispatchError(f"media WorkItem {item.id!r} is not ready")
        if content_hash(item.output_json) != item.output_hash:
            raise SharedLessonFinalizationDispatchError(
                f"media WorkItem {item.id!r} output hash is stale"
            )
        try:
            bound = bind_durable_media_outcome(item.output_json, document)
            if item.item_key != f"media:{bound.work_order_id}":
                raise SharedLessonFinalizationDispatchError(
                    f"media WorkItem {item.id!r} has a stale work-order identity"
                )
        except (TypeError, ValueError, SharedFigureMediaError) as exc:
            if isinstance(exc, SharedLessonFinalizationDispatchError):
                raise
            raise SharedLessonFinalizationDispatchError(
                f"media WorkItem {item.id!r} output is stale or forged"
            ) from exc
        identity = (bound.section_id, bound.figure_node_id)
        if identity in seen:
            raise SharedLessonFinalizationDispatchError(
                f"duplicate durable media identity {identity!r}"
            )
        seen.add(identity)
        results.append(bound)

    observed = {(result.section_id, result.figure_node_id) for result in results}
    if observed != set(expected):
        raise SharedLessonFinalizationDispatchError(
            "durable media outputs do not match the document figure identities"
        )
    results.sort(key=lambda result: expected.index((result.section_id, result.figure_node_id)))
    return tuple(results), _required_media_map(results)


async def finalize_shared_lesson_document_for_run(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    path_lesson_id: str,
    preparation_generation_id: str,
    handoff: SharedLessonHandoffEvidence,
    artifact_loader: ArtifactLoader | None = None,
    now: datetime | None = None,
) -> SharedLessonFinalizationDispatchOutcome:
    """Finalize one existing owner-scoped Run from durable accepted outputs."""

    try:
        source = await load_current_approved_teaching_plan_source(
            session=session,
            owner_user_id=owner_user_id,
            path_lesson_id=path_lesson_id,
            preparation_generation_id=preparation_generation_id,
        )
        if (
            handoff.teaching_plan_id,
            handoff.teaching_plan_revision,
            handoff.teaching_plan_hash,
        ) != (source.id, source.revision, source.content_hash):
            raise SharedLessonFinalizationDispatchError(
                "handoff evidence is stale for the current approved Teaching Plan"
            )

        semantic = await load_verified_semantic_inputs(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
        )
        sources = _all_section_sources(semantic, source)
        accepted = await load_verified_shared_lesson_inputs(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            tasks=semantic.tasks,
            sources=sources,
        )
        all_items, active_items = await _active_run_items(session, run_id=run_id)
        media_results, required_media = _durable_media_results(
            document=handoff.document,
            active_items=active_items,
        )
        structural_document = await resolve_review_structural_document(
            session,
            path_lesson_id=path_lesson_id,
            document=handoff.document,
            media_results=media_results,
        )
        _verify_durable_inputs_match_handoff(
            document=structural_document,
            tasks=semantic.tasks,
            verified_inputs=accepted,
            handoff_expected_shapes=handoff.expected_shapes,
        )

        _verify_boundary_coverage(
            source=source,
            document=structural_document,
            verified_inputs=accepted,
            active_items=active_items,
            all_items=all_items,
        )

        qa_items = tuple(item for item in active_items if item.stage == DOCUMENT_QA_STAGE)
        if len(qa_items) != 1 or qa_items[0].status != "ready":
            raise SharedLessonFinalizationDispatchError("document QA WorkItem is not ready")
        verified_qa = await load_verified_document_qa(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            document=handoff.document,
        )
        _verify_document_qa_matches_handoff(
            document=handoff.document,
            semantic_qa=handoff.semantic_qa,
            verified_qa=verified_qa,
            active_items=active_items,
        )

        request = SharedLessonFinalizationRequest(
            run_id=run_id,
            owner_user_id=owner_user_id,
            path_lesson_id=path_lesson_id,
            source=source,
            handoff=handoff,
            tasks=tuple(semantic.tasks),
            sources=tuple(sources),
            approved_source_ids=tuple(item.id for item in sources),
            source_facts_by_section=None,
            required_media_by_section=required_media,
            media_results=media_results,
        )
        result = await finalize_shared_lesson_document(
            session,
            request=request,
            source_verifier=make_approved_source_verifier(
                owner_user_id=owner_user_id,
                path_lesson_id=path_lesson_id,
                preparation_generation_id=preparation_generation_id,
            ),
            artifact_loader=artifact_loader,
            now=now,
        )
        return SharedLessonFinalizationDispatchOutcome(status="ready", result=result)
    except (
        ApprovedSourceVerificationError,
        DocumentQARuntimeError,
        SemanticInputError,
        SectionSourceError,
        SharedLessonFinalizationDispatchError,
        SharedLessonFinalizationError,
        SharedLessonInputError,
        SharedFigureMediaError,
        ValidationError,
    ) as exc:
        return SharedLessonFinalizationDispatchOutcome(status="blocked", error=str(exc))


__all__ = [
    "SharedLessonFinalizationDispatchError",
    "SharedLessonFinalizationDispatchOutcome",
    "finalize_shared_lesson_document_for_run",
]
