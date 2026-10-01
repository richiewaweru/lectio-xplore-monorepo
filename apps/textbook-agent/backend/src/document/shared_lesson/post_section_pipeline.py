"""Run the post-section SharedDocument stages on one existing Run."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from document.shared_lesson.approved_source import (
    ApprovedSourceVerificationError,
    load_current_approved_teaching_plan_source,
    make_approved_source_verifier,
)
from document.shared_lesson.assembly import (
    SharedLessonAssemblyError,
    assemble_shared_lesson_document,
)
from document.shared_lesson.boundary import BoundaryRepairEngine, BoundarySemanticValidator
from document.shared_lesson.boundary_dispatcher import (
    BoundaryDispatchError,
    BoundaryDispatchResult,
    dispatch_shared_document_boundaries,
)
from document.shared_lesson.composer import SectionCompositionPlan
from document.shared_lesson.document_qa_dispatcher import (
    SharedDocumentQADispatchError,
    SharedDocumentQADispatchResult,
    dispatch_reviewed_document_qa,
    dispatch_reviewed_figure_media,
    dispatch_shared_document_qa,
)
from document.shared_lesson.figure_executor_adapter import SharedFigureExecutorAdapter
from document.shared_lesson.finalization_dispatcher import (
    SharedLessonFinalizationDispatchError,
    SharedLessonFinalizationDispatchOutcome,
    _active_run_items,
    _durable_media_results,
    finalize_shared_lesson_document_for_run,
)
from document.shared_lesson.handoff import SharedLessonHandoffError, SharedLessonHandoffEvidence
from document.shared_lesson.handoff_dispatcher import (
    SharedDocumentHandoffDispatchError,
    handoff_qa_dispatch_result,
)
from document.shared_lesson.qa_runtime import DOCUMENT_QA_STAGE
from document.shared_lesson.media import SharedFigureMediaError
from document.shared_lesson.media_dispatcher import (
    SharedMediaDispatcher,
    SharedMediaDispatcherError,
)
from document.shared_lesson.media_runtime import MEDIA_STAGE, MediaReadiness, MediaRuntimeError
from document.shared_lesson.runtime import TeachingPlanSource
from document.shared_lesson.semantic_inputs import SemanticInputError, load_verified_semantic_inputs
from document.shared_lesson.work_item_inputs import (
    SharedLessonInputError,
    load_verified_shared_lesson_inputs,
)
from infra.database.models import GenerationRunModel
from infra.generation_runtime import get_run_status

FINALIZATION_STAGE = "document_finalization"


class PostSectionPipelineError(ValueError):
    """The post-section stages cannot safely advance this Run."""


class PostSectionPipelineOutcome(BaseModel):
    """Closed status projection for the post-section pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    state: Literal["ready", "pending", "blocked"]
    stage: str
    document_id: str | None = None
    error: str | None = None


def _source_ids(source: TeachingPlanSource) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for section in source.plan.sections:
        for block in section.blocks:
            for source_id in block.sourcebook_refs:
                if source_id not in seen:
                    seen.add(source_id)
                    ordered.append(source_id)
    return tuple(ordered)


def _expected_shapes(
    compositions: Mapping[str, SectionCompositionPlan],
) -> dict[str, tuple[Any, ...]]:
    from document.shared_lesson.continuity import ExpectedNodeShape

    return {
        section_id: tuple(
            ExpectedNodeShape(
                id=item.id,
                kind=item.kind,
                teaching_block_id=item.teaching_block_id,
                semantic_role=item.semantic_role,
                task_spec_id=item.task_spec_id,
            )
            for item in composition.items
        )
        for section_id, composition in compositions.items()
    }


def _find_review_leaf(active_items: Any) -> Any:
    """Return the active document QA review replacement leaf, if any.

    A reviewer-submitted correction is admitted as a linked replacement of the
    document QA leaf that originally failed with a semantic issue; both the
    media stage and the document QA stage must agree on the same leaf.
    """
    return next(
        (
            item
            for item in active_items
            if item.stage == DOCUMENT_QA_STAGE and item.replaces_work_item_id is not None
        ),
        None,
    )


def _created_at(run: GenerationRunModel):
    value = run.created_at
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _set_run_stage(
    session_factory: Callable[[], Any],
    *,
    run_id: str,
    owner_user_id: str,
    stage: str,
) -> None:
    """Persist the authoritative stage before an external stage begins."""
    async with session_factory() as session:
        run = await get_run_status(session, run_id=run_id, owner_user_id=owner_user_id)
        if run is None or run.run_type != "shared_document":
            raise PostSectionPipelineError("SharedDocument Run is unavailable to this owner")
        if run.status not in {"queued", "running", "awaiting_review"}:
            raise PostSectionPipelineError("SharedDocument Run is not active")
        run.stage = stage
        await session.commit()


async def _load_post_section_inputs(
    session_factory: Callable[[], Any],
    *,
    run_id: str,
    owner_user_id: str,
    path_lesson_id: str,
    preparation_generation_id: str,
):
    async with session_factory() as session:
        run = await get_run_status(session, run_id=run_id, owner_user_id=owner_user_id)
        if run is None or run.run_type != "shared_document":
            raise PostSectionPipelineError("SharedDocument Run is unavailable to this owner")
        source = await load_current_approved_teaching_plan_source(
            session=session,
            owner_user_id=owner_user_id,
            path_lesson_id=path_lesson_id,
            preparation_generation_id=preparation_generation_id,
        )
        semantic = await load_verified_semantic_inputs(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
        )
        sources = []
        seen_sources: set[str] = set()
        from document.shared_lesson.section_sources import build_section_sources

        for section in source.plan.sections:
            for projected in build_section_sources(semantic, section):
                if projected.id not in seen_sources:
                    seen_sources.add(projected.id)
                    sources.append(projected)
        accepted = await load_verified_shared_lesson_inputs(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            tasks=semantic.tasks,
            sources=tuple(sources),
        )
        return (
            run,
            source,
            semantic.tasks,
            accepted.compositions,
            accepted.sections,
            accepted.section_warnings,
        )


async def run_post_section_pipeline(
    session_factory: Callable[[], Any],
    *,
    run_id: str,
    owner_user_id: str,
    path_lesson_id: str,
    preparation_generation_id: str,
    media_executor: Any = None,
    boundary_semantic_validator: BoundarySemanticValidator | None = None,
    boundary_repair_engine: BoundaryRepairEngine | None = None,
    qa_semantic_validator: Any = None,
    artifact_loader: Any = None,
    worker_id: str = "shared-document-post-section",
) -> PostSectionPipelineOutcome:
    """Advance one existing Run through boundaries, media, QA, handoff, and READY."""
    try:
        await _set_run_stage(
            session_factory,
            run_id=run_id,
            owner_user_id=owner_user_id,
            stage="continuity_validation",
        )
    except PostSectionPipelineError as exc:
        return PostSectionPipelineOutcome(
            run_id=run_id, state="blocked", stage="boundaries", error=str(exc)
        )
    try:
        boundaries: BoundaryDispatchResult = await dispatch_shared_document_boundaries(
            session_factory,
            run_id=run_id,
            owner_user_id=owner_user_id,
            semantic_validator=boundary_semantic_validator,
            repair_engine=boundary_repair_engine,
            worker_id=f"{worker_id}:boundary",
        )
    except BoundaryDispatchError as exc:
        return PostSectionPipelineOutcome(
            run_id=run_id, state="blocked", stage="boundaries", error=str(exc)
        )
    if boundaries.state in {"pending", "pending_repair"}:
        return PostSectionPipelineOutcome(
            run_id=run_id, state="pending", stage="boundaries", error=boundaries.blocked_reason
        )
    if boundaries.state == "blocked":
        return PostSectionPipelineOutcome(
            run_id=run_id, state="blocked", stage="boundaries", error=boundaries.blocked_reason
        )

    review_document: Any = None
    readiness: MediaReadiness
    try:
        await _set_run_stage(
            session_factory,
            run_id=run_id,
            owner_user_id=owner_user_id,
            stage=MEDIA_STAGE,
        )
        async with session_factory() as probe_session:
            _all_items0, active_items0 = await _active_run_items(probe_session, run_id=run_id)
        review_leaf0 = _find_review_leaf(active_items0)
        async with session_factory() as session:
            source = await load_current_approved_teaching_plan_source(
                session=session,
                owner_user_id=owner_user_id,
                path_lesson_id=path_lesson_id,
                preparation_generation_id=preparation_generation_id,
            )
            selected_media_executor = (
                media_executor
                if media_executor is not None
                else SharedFigureExecutorAdapter(run_id=run_id)
            )
            if review_leaf0 is not None:
                # A reviewer already saved and submitted a text-only correction
                # that touched at least one figure-containing section.
                # ``review-draft/submit`` already regenerated that section's
                # figures as linked replacement media WorkItems bound to the
                # edited revision; never re-derive figure work orders from the
                # durable writer/composer outputs at revision 1 here, which
                # would try to re-admit against the now-stale original section.
                review_document, readiness = await dispatch_reviewed_figure_media(
                    session_factory,
                    run_id=run_id,
                    owner_user_id=owner_user_id,
                    path_lesson_id=path_lesson_id,
                    source=source,
                    leaf=review_leaf0,
                    media_executor=selected_media_executor,
                    worker_id=f"{worker_id}:media",
                )
            else:
                verifier = make_approved_source_verifier(
                    owner_user_id=owner_user_id,
                    path_lesson_id=path_lesson_id,
                    preparation_generation_id=preparation_generation_id,
                )
                media = SharedMediaDispatcher(
                    session_factory,
                    worker_id=f"{worker_id}:media",
                    executor=selected_media_executor,
                )
                media_outcome = await media.run_one(
                    session=session,
                    run_id=run_id,
                    owner_user_id=owner_user_id,
                    source=source,
                    source_verifier=verifier,
                )
                readiness = media_outcome.readiness
            await session.commit()
    except (
        ApprovedSourceVerificationError,
        SemanticInputError,
        SharedLessonInputError,
        SharedMediaDispatcherError,
        SharedFigureMediaError,
        SharedDocumentQADispatchError,
        MediaRuntimeError,
        PostSectionPipelineError,
    ) as exc:
        return PostSectionPipelineOutcome(
            run_id=run_id, state="blocked", stage="media", error=str(exc)
        )
    if not readiness.ready:
        state = "blocked" if readiness.failed_required_work_item_ids else "pending"
        return PostSectionPipelineOutcome(
            run_id=run_id, state=state, stage="media", error="required media is not ready"
        )

    try:
        await _set_run_stage(
            session_factory,
            run_id=run_id,
            owner_user_id=owner_user_id,
            stage="document_qa",
        )
        (
            run,
            source,
            tasks,
            compositions_raw,
            sections_raw,
            section_warnings,
        ) = await _load_post_section_inputs(
            session_factory,
            run_id=run_id,
            owner_user_id=owner_user_id,
            path_lesson_id=path_lesson_id,
            preparation_generation_id=preparation_generation_id,
        )
        compositions = {item.section_slot_id: item for item in compositions_raw}
        sections = {item.id: item for item in sections_raw}
        document_id = f"shared-document:{run.id}:revision:1"
        created_at = _created_at(run)
        draft = assemble_shared_lesson_document(
            document_id=document_id,
            revision=1,
            source=source,
            accepted_sections=sections,
            tasks=tasks,
            created_at=created_at,
            expected_shapes=_expected_shapes(compositions),
            approved_source_ids=_source_ids(source),
            required_media_by_section={},
            available_media_ids=(),
        )
        if not draft.ready:
            return PostSectionPipelineOutcome(
                run_id=run_id,
                state="blocked",
                stage="deterministic_qa",
                document_id=document_id,
                error="deterministic document QA failed",
            )

        async with session_factory() as session:
            _all_items, active_items = await _active_run_items(session, run_id=run_id)
        review_leaf = _find_review_leaf(active_items)
        media_results, required_media = _durable_media_results(
            document=review_document if review_leaf is not None else draft.document,
            active_items=active_items,
        )
        if review_leaf is not None:
            # A reviewer already saved and submitted a text-only correction for
            # a prior semantic ISSUE. Execute (or reload) that exact admitted
            # replacement bound to the edited draft revision; never re-assemble
            # a fresh revision-1 document over the reviewer's edits.
            qa_result = await dispatch_reviewed_document_qa(
                session_factory,
                run_id=run_id,
                owner_user_id=owner_user_id,
                path_lesson_id=path_lesson_id,
                source=source,
                leaf=review_leaf,
                compositions=compositions,
                required_media_by_section=required_media,
                media_results=media_results,
                semantic_validator=qa_semantic_validator,
                worker_id=f"{worker_id}:qa",
            )
            handoff = SharedLessonHandoffEvidence(
                status="ready",
                document=qa_result.document,
                deterministic_qa=qa_result.deterministic_qa,
                semantic_qa=qa_result.verified_qa.semantic_qa,
                expected_shapes=_expected_shapes(compositions),
                teaching_plan_id=source.id,
                teaching_plan_revision=source.revision,
                teaching_plan_hash=source.content_hash,
            )
        else:
            qa_result: SharedDocumentQADispatchResult = await dispatch_shared_document_qa(
                session_factory,
                run_id=run_id,
                owner_user_id=owner_user_id,
                source=source,
                compositions=compositions,
                sections=sections,
                tasks=tasks,
                document_id=document_id,
                document_revision=1,
                created_at=created_at,
                provenance=draft.document.provenance,
                writer_warnings=section_warnings,
                required_media_by_section=required_media,
                media_results=media_results,
                semantic_validator=qa_semantic_validator,
                worker_id=f"{worker_id}:qa",
            )
            handoff = await handoff_qa_dispatch_result(
                qa_result,
                source=source,
                compositions=compositions,
                sections=sections,
                tasks=tasks,
                required_media_by_section=required_media,
                media_results=media_results,
            )
    except (
        ApprovedSourceVerificationError,
        SemanticInputError,
        SharedLessonInputError,
        SharedLessonAssemblyError,
        SharedDocumentQADispatchError,
        SharedDocumentHandoffDispatchError,
        SharedLessonHandoffError,
        PostSectionPipelineError,
    ) as exc:
        return PostSectionPipelineOutcome(
            run_id=run_id, state="blocked", stage="qa_handoff", error=str(exc)
        )

    try:
        await _set_run_stage(
            session_factory,
            run_id=run_id,
            owner_user_id=owner_user_id,
            stage=FINALIZATION_STAGE,
        )
        async with session_factory() as session:
            finalized: SharedLessonFinalizationDispatchOutcome = (
                await finalize_shared_lesson_document_for_run(
                    session,
                    run_id=run_id,
                    owner_user_id=owner_user_id,
                    path_lesson_id=path_lesson_id,
                    preparation_generation_id=preparation_generation_id,
                    handoff=handoff,
                    artifact_loader=artifact_loader,
                )
            )
            await session.commit()
    except (PostSectionPipelineError, SharedLessonFinalizationDispatchError) as exc:
        return PostSectionPipelineOutcome(
            run_id=run_id, state="blocked", stage="finalization", error=str(exc)
        )
    if not finalized.ready:
        return PostSectionPipelineOutcome(
            run_id=run_id, state="blocked", stage="finalization", error=finalized.error
        )
    return PostSectionPipelineOutcome(
        run_id=run_id,
        state="ready",
        stage="finalization",
        document_id=handoff.document.id,
    )


__all__ = ["PostSectionPipelineError", "PostSectionPipelineOutcome", "run_post_section_pipeline"]
