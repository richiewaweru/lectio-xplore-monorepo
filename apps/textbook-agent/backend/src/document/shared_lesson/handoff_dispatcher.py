"""Bridge a durable QA dispatch result into the pure handoff contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.composer import SectionCompositionPlan
from document.shared_lesson.document_qa_dispatcher import SharedDocumentQADispatchResult
from document.shared_lesson.handoff import (
    SharedLessonHandoffError,
    SharedLessonHandoffEvidence,
    handoff_accepted_sections_to_document,
)
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.media import (
    FigureMediaResult,
    SharedFigureMediaError,
    verify_bound_figure_media,
)
from document.shared_lesson.models import FigureNode, SharedLessonDocument, SharedSection
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source


class SharedDocumentHandoffDispatchError(ValueError):
    """The durable QA artifact cannot be handed off without identity drift."""


def _approved_source_ids(source: TeachingPlanSource) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for section in source.plan.sections:
        for block in section.blocks:
            for source_id in block.sourcebook_refs:
                if source_id not in seen:
                    seen.add(source_id)
                    ordered.append(source_id)
    return tuple(ordered)


def _required_media(document: SharedLessonDocument) -> dict[str, tuple[str, ...]]:
    return {
        section.id: tuple(node.id for node in section.nodes if isinstance(node, FigureNode))
        for section in document.sections
        if any(isinstance(node, FigureNode) for node in section.nodes)
    }


def _verify_media(
    document: SharedLessonDocument,
    required_media_by_section: Mapping[str, Sequence[str]] | None,
    media_results: Sequence[FigureMediaResult],
) -> tuple[str, ...]:
    expected = _required_media(document)
    declared = {
        section_id: tuple(figure_ids)
        for section_id, figure_ids in (required_media_by_section or {}).items()
        if figure_ids
    }
    if {key: set(value) for key, value in declared.items()} != {
        key: set(value) for key, value in expected.items()
    }:
        raise SharedDocumentHandoffDispatchError(
            "required media declaration does not match the QA dispatch document"
        )
    expected_ids = {
        (section_id, figure_id) for section_id, values in expected.items() for figure_id in values
    }
    supplied: dict[tuple[str, str], FigureMediaResult] = {}
    for result in media_results:
        identity = (result.section_id, result.figure_node_id)
        if identity in supplied:
            raise SharedDocumentHandoffDispatchError(
                f"duplicate durable media evidence for {identity!r}"
            )
        try:
            verify_bound_figure_media(result, document)
        except SharedFigureMediaError as exc:
            raise SharedDocumentHandoffDispatchError(
                f"durable media evidence is stale for {identity!r}"
            ) from exc
        if not result.required:
            raise SharedDocumentHandoffDispatchError(
                f"durable media evidence is not required for {identity!r}"
            )
        supplied[identity] = result
    if set(supplied) != expected_ids:
        raise SharedDocumentHandoffDispatchError(
            "durable media evidence does not cover the QA dispatch document"
        )
    return tuple(sorted(result.figure_node_id for result in supplied.values()))


def _verify_dispatch_identity(result: SharedDocumentQADispatchResult) -> None:
    document = result.document
    if shared_lesson_content_hash(document) != document.content_hash:
        raise SharedDocumentHandoffDispatchError("QA dispatch document content hash is stale")
    deterministic = result.deterministic_qa
    semantic = result.verified_qa.semantic_qa
    if (
        deterministic.document_id,
        deterministic.document_revision,
    ) != (document.id, document.revision):
        raise SharedDocumentHandoffDispatchError(
            "QA dispatch deterministic QA identity differs from its document"
        )
    if (
        semantic.document_id,
        semantic.document_revision,
        semantic.document_hash,
    ) != (document.id, document.revision, document.content_hash):
        raise SharedDocumentHandoffDispatchError(
            "QA dispatch semantic QA identity differs from its document"
        )
    if (
        not semantic.passed
        or semantic.semantic_calls != 1
        or semantic.deterministic_skipped_semantic
    ):
        raise SharedDocumentHandoffDispatchError(
            "QA dispatch must contain one durable semantic PASS"
        )


async def handoff_qa_dispatch_result(
    result: SharedDocumentQADispatchResult,
    *,
    source: TeachingPlanSource,
    compositions: Mapping[str, SectionCompositionPlan] | Sequence[SectionCompositionPlan],
    sections: Mapping[str, SharedSection] | Sequence[SharedSection],
    tasks: Sequence[SharedTaskSpec] = (),
    required_media_by_section: Mapping[str, Sequence[str]] | None = None,
    media_results: Sequence[FigureMediaResult] = (),
) -> SharedLessonHandoffEvidence:
    """Handoff one already-QA'd document without making another provider call."""
    if not isinstance(result, SharedDocumentQADispatchResult):
        raise SharedDocumentHandoffDispatchError("QA dispatch result is not closed")
    try:
        identity = verify_teaching_plan_source(source)
    except ValueError as exc:
        raise SharedDocumentHandoffDispatchError(
            "approved Teaching Plan source is invalid"
        ) from exc
    _verify_dispatch_identity(result)
    document = result.document
    if (
        document.teaching_plan_id,
        document.teaching_plan_revision,
        document.teaching_plan_hash,
    ) != (identity.source_artifact_id, identity.source_revision, identity.source_hash):
        raise SharedDocumentHandoffDispatchError(
            "QA dispatch document source differs from the approved Teaching Plan"
        )
    available_media_ids = _verify_media(
        document,
        required_media_by_section,
        media_results,
    )
    try:
        handoff = await handoff_accepted_sections_to_document(
            source=source,
            compositions=compositions,
            sections=sections,
            tasks=tasks,
            document_id=document.id,
            document_revision=document.revision,
            created_at=document.created_at,
            provenance=document.provenance,
            approved_source_ids=_approved_source_ids(source),
            source_facts_by_section=None,
            required_media_by_section=required_media_by_section,
            available_media_ids=available_media_ids,
            expected_content_hash=document.content_hash,
            verified_semantic_qa=result.verified_qa.semantic_qa,
        )
    except (SharedLessonHandoffError, ValueError) as exc:
        raise SharedDocumentHandoffDispatchError(str(exc)) from exc
    if handoff.document != document or handoff.document.content_hash != document.content_hash:
        raise SharedDocumentHandoffDispatchError(
            "handoff document differs from the QA dispatch document"
        )
    if handoff.semantic_qa != result.verified_qa.semantic_qa:
        raise SharedDocumentHandoffDispatchError(
            "handoff semantic QA differs from the durable QA dispatch result"
        )
    return handoff


__all__ = [
    "SharedDocumentHandoffDispatchError",
    "handoff_qa_dispatch_result",
]
