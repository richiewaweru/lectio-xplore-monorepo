"""Atomic READY finalization for a SharedLessonDocument generation run.

Section workers and semantic QA may finish before this boundary.  The
finalizer is the last durable gate: it rechecks the approved Teaching Plan,
locks the run and its active work items, persists the immutable draft,
promotes it after the repository QA/media checks, and then finalizes the
generic run in the same transaction.

Teaching Plan persistence and the section-output loader are deliberately
injected.  The current preparation store and the section loader are separate
bounded packages, so this module does not invent a second persistence path for
either one.  A caller must provide a verifier that reads the current approved
source and a loader that reads the active durable work-item outputs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.assembly import SharedLessonAssemblyResult
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.handoff import SharedLessonHandoffEvidence
from document.shared_lesson.media import FigureMediaResult, ReadyFigureMediaResult
from document.shared_lesson.models import FigureNode, SharedLessonDocument
from document.shared_lesson.repository import (
    StoredSharedLessonDocument,
    promote_shared_lesson_document,
    save_shared_lesson_document,
)
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source
from document.shared_lesson.work_item_inputs import (
    SharedLessonInputError,
    load_verified_shared_lesson_inputs,
)
from document.shared_lesson.writer import SectionSource
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    RunFinalization,
    SourceIdentity,
    active_work_items,
    finalize_run,
)
from infra.generation_runtime.repository import ArtifactLoader, SourceVerifier


class SharedLessonFinalizationError(ValueError):
    """A finalization input or durable identity failed the READY gate."""


class VerifiedWorkItemOutput(BaseModel):
    """Closed output identity returned by the durable section/media loader."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: str = Field(min_length=1)
    output_json: JsonValue
    output_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def output_hash_matches_payload(self) -> VerifiedWorkItemOutput:
        if self.output_json is None:
            raise ValueError("verified work-item output must be present")
        if content_hash(self.output_json) != self.output_hash:
            raise ValueError("verified work-item output hash does not match its payload")
        return self


class SharedLessonFinalizationRequest(BaseModel):
    """Immutable evidence and identities accepted by the finalizer."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    run_id: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    path_lesson_id: str = Field(min_length=1)
    source: TeachingPlanSource
    handoff: SharedLessonHandoffEvidence
    # These are required inputs even when a particular lesson has no task or
    # source rows.  The finalizer must never silently author them as empty
    # data, because that would recreate the old Print lazy-authoring path.
    tasks: tuple[SharedTaskSpec, ...]
    sources: tuple[SectionSource, ...]
    approved_source_ids: tuple[str, ...]
    source_facts_by_section: Mapping[str, tuple[str, ...]] | None
    required_media_by_section: Mapping[str, tuple[str, ...]] | None
    media_results: tuple[FigureMediaResult, ...]

    @model_validator(mode="after")
    def identities_match(self) -> SharedLessonFinalizationRequest:
        identity = verify_teaching_plan_source(self.source)
        if (
            self.handoff.teaching_plan_id != identity.source_artifact_id
            or self.handoff.teaching_plan_revision != identity.source_revision
            or self.handoff.teaching_plan_hash != identity.source_hash
        ):
            raise ValueError("handoff evidence is bound to a different approved source")
        document = self.handoff.document
        if (
            document.teaching_plan_id != identity.source_artifact_id
            or document.teaching_plan_revision != identity.source_revision
            or document.teaching_plan_hash != identity.source_hash
        ):
            raise ValueError("document is bound to a different approved source")
        for task in self.tasks:
            if (
                task.teaching_plan_id != identity.source_artifact_id
                or task.teaching_plan_revision != identity.source_revision
                or task.teaching_plan_hash != identity.source_hash
            ):
                raise ValueError(
                    f"task {task.id!r} is not bound to the approved Teaching Plan revision"
                )
        source_ids = {source.id for source in self.sources}
        required_source_ids = {
            source_id
            for section in self.source.plan.sections
            for block in section.blocks
            for source_id in block.sourcebook_refs
        }
        missing_sources = sorted(required_source_ids - source_ids)
        if missing_sources:
            raise ValueError(
                "approved Teaching Plan sourcebook references are missing from supplied sources: "
                f"{missing_sources!r}"
            )
        return self


@dataclass(frozen=True)
class SharedLessonFinalizationResult:
    """The two durable results committed by one finalization transaction."""

    document: StoredSharedLessonDocument
    run: GenerationRunModel


WorkItemOutputLoader = Callable[
    [AsyncSession, str], Awaitable[Sequence[VerifiedWorkItemOutput | Mapping[str, Any]]]
]


def _coerce_verified_outputs(
    values: Sequence[VerifiedWorkItemOutput | Mapping[str, Any]],
) -> tuple[VerifiedWorkItemOutput, ...]:
    try:
        return tuple(
            value
            if isinstance(value, VerifiedWorkItemOutput)
            else VerifiedWorkItemOutput.model_validate(value)
            for value in values
        )
    except (TypeError, ValueError) as exc:
        raise SharedLessonFinalizationError(
            "durable work-item loader returned invalid output evidence"
        ) from exc


async def _load_default_work_item_outputs(
    session: AsyncSession,
    run_id: str,
) -> tuple[VerifiedWorkItemOutput, ...]:
    """Verify generic durable output hashes when no section loader is needed.

    Product integration should pass the section-output loader, which also
    validates compose/write result contracts.  This default is intentionally
    limited to the generic durable identity gate and never reconstructs lesson
    content from an untrusted work item.
    """
    rows = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
            )
        ).all()
    )
    active = active_work_items(rows)
    if not active:
        raise SharedLessonFinalizationError("shared document run has no active work items")
    if any(item.status != "ready" for item in active):
        raise SharedLessonFinalizationError(
            "all active work items must be ready before finalization"
        )
    outputs: list[VerifiedWorkItemOutput] = []
    for item in active:
        try:
            outputs.append(
                VerifiedWorkItemOutput(
                    work_item_id=item.id,
                    output_json=item.output_json,
                    output_hash=item.output_hash or "",
                )
            )
        except (TypeError, ValueError) as exc:
            raise SharedLessonFinalizationError(
                f"work item {item.id!r} has invalid durable output"
            ) from exc
    return tuple(outputs)


def _json_equal(left: Any, right: Any) -> bool:
    """Compare Pydantic values after applying their strict JSON shape."""
    if hasattr(left, "model_dump"):
        left = left.model_dump(mode="json")
    if hasattr(right, "model_dump"):
        right = right.model_dump(mode="json")
    return left == right


def _verify_durable_inputs_match_handoff(
    *,
    document: SharedLessonDocument,
    tasks: Sequence[SharedTaskSpec],
    verified_inputs: Any,
    handoff_expected_shapes: Mapping[str, Sequence[ExpectedNodeShape]],
) -> None:
    """Reject a forged handoff that differs from durable writer outputs."""
    if tuple(document.sections) != tuple(verified_inputs.sections):
        raise SharedLessonFinalizationError(
            "handoff sections differ from the verified durable writer outputs"
        )
    document_tasks = tuple(document.tasks)
    if len(document_tasks) != len(tasks) or any(
        not _json_equal(left, right) for left, right in zip(document_tasks, tasks, strict=False)
    ):
        raise SharedLessonFinalizationError(
            "handoff task snapshots differ from the approved durable task inputs"
        )
    durable_shapes = {
        composition.section_slot_id: tuple(
            ExpectedNodeShape(
                id=item.id,
                kind=item.kind,
                teaching_block_id=item.teaching_block_id,
                semantic_role=item.semantic_role,
                task_spec_id=item.task_spec_id,
            )
            for item in composition.items
        )
        for composition in verified_inputs.compositions
    }
    normalized_handoff_shapes = {
        section_id: tuple(
            shape
            if isinstance(shape, ExpectedNodeShape)
            else ExpectedNodeShape.model_validate(shape)
            for shape in shapes
        )
        for section_id, shapes in handoff_expected_shapes.items()
    }
    if durable_shapes != normalized_handoff_shapes:
        raise SharedLessonFinalizationError(
            "handoff expected node shapes differ from the verified durable compositions"
        )


def _verify_media_matches_work_items(
    *,
    document: SharedLessonDocument,
    media_results: Sequence[FigureMediaResult],
    active_items: Sequence[GenerationWorkItemModel],
    loaded_outputs: Sequence[VerifiedWorkItemOutput],
) -> None:
    """Bind each document figure to its ready media work-item output."""
    expected_figures = {
        (section.id, node.id)
        for section in document.sections
        for node in section.nodes
        if isinstance(node, FigureNode)
    }
    supplied_figures = {(result.section_id, result.figure_node_id) for result in media_results}
    if supplied_figures != expected_figures:
        raise SharedLessonFinalizationError(
            "media evidence does not cover exactly the document figure identities"
        )
    output_by_id = {output.work_item_id: output for output in loaded_outputs}
    media_items = [item for item in active_items if item.item_key.startswith("media:")]
    if len(media_items) != len(expected_figures):
        raise SharedLessonFinalizationError(
            "durable media work items do not cover exactly the document figure identities"
        )
    ready_by_figure: dict[tuple[str, str], ReadyFigureMediaResult] = {}
    for item in media_items:
        output = output_by_id.get(item.id)
        if output is None:
            raise SharedLessonFinalizationError(
                f"durable media output is missing for work item {item.id!r}"
            )
        try:
            ready = ReadyFigureMediaResult.model_validate(output.output_json)
        except (TypeError, ValueError) as exc:
            raise SharedLessonFinalizationError(
                f"durable media output for work item {item.id!r} is invalid"
            ) from exc
        if item.item_key != f"media:{ready.work_order_id}":
            raise SharedLessonFinalizationError(
                f"durable media work item {item.id!r} has a mismatched work order"
            )
        identity = (ready.section_id, ready.figure_node_id)
        if identity in ready_by_figure:
            raise SharedLessonFinalizationError(
                f"durable media outputs duplicate figure identity {identity!r}"
            )
        ready_by_figure[identity] = ready
    for result in media_results:
        ready = ready_by_figure.get((result.section_id, result.figure_node_id))
        if ready is None:
            raise SharedLessonFinalizationError(
                f"bound media has no matching durable output for {result.figure_node_id!r}"
            )
        ready_payload = ready.model_dump(mode="json")
        result_payload = result.model_dump(mode="json")
        for field in (
            "source_plan_id",
            "source_plan_revision",
            "source_plan_hash",
            "section_id",
            "section_output_hash",
            "figure_node_id",
            "figure_semantic_hash",
            "work_order_id",
            "visual_id",
            "asset_id",
            "asset_url",
            "mode",
            "required",
            "source_facts",
            "status",
        ):
            if result_payload[field] != ready_payload[field]:
                raise SharedLessonFinalizationError(
                    f"bound media field {field!r} differs from its durable work-item output"
                )


async def _load_and_lock_run(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
) -> tuple[GenerationRunModel, tuple[GenerationWorkItemModel, ...]]:
    items = tuple(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.run_id == run_id)
                .order_by(GenerationWorkItemModel.id)
                .with_for_update()
            )
        ).all()
    )
    # Match the generic runtime's worker/finalizer lock order: child leaves
    # first, then the parent Run.  This avoids a finalizer/worker deadlock.
    run = await session.scalar(
        select(GenerationRunModel)
        .where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise SharedLessonFinalizationError("shared document run is unavailable to this owner")
    return run, items


@asynccontextmanager
async def _finalization_transaction(session: AsyncSession) -> AsyncIterator[None]:
    """Own a commit when possible, or join the caller's transaction safely.

    Application callers normally invoke this with an idle session, in which
    case the finalizer owns the outer transaction and commits only after the
    document and Run are both ready.  A caller that already opened a
    transaction retains commit ownership; the savepoint still rolls every
    finalizer write back together on failure.
    """
    if session.in_transaction():
        async with session.begin_nested():
            yield
    else:
        async with session.begin():
            yield


async def finalize_shared_lesson_document(
    session: AsyncSession,
    *,
    request: SharedLessonFinalizationRequest,
    source_verifier: SourceVerifier,
    work_item_loader: WorkItemOutputLoader | None = None,
    artifact_loader: ArtifactLoader | None = None,
    now: datetime | None = None,
) -> SharedLessonFinalizationResult:
    """Atomically persist, promote, and finalize one SharedLessonDocument.

    ``source_verifier`` must load the current approved Teaching Plan snapshot
    and return its recomputed ``SourceIdentity``.  ``work_item_loader`` must
    load the active leaves for ``run_id`` and verify their stage-specific
    output contracts.  Both callbacks run while the run and active leaves are
    locked.  Any failure rolls back the draft/READY transition and the generic
    run update together.
    """
    if not isinstance(request, SharedLessonFinalizationRequest):
        request = SharedLessonFinalizationRequest.model_validate(request)
    if artifact_loader is None:
        from document.shared_lesson.repository import load_verified_shared_lesson_artifact

        artifact_loader = load_verified_shared_lesson_artifact
    if work_item_loader is None:
        work_item_loader = _load_default_work_item_outputs

    async with _finalization_transaction(session):
        run, locked_items = await _load_and_lock_run(
            session,
            run_id=request.run_id,
            owner_user_id=request.owner_user_id,
        )
        active_items = active_work_items(locked_items)
        if not active_items:
            raise SharedLessonFinalizationError("shared document run has no active work items")

        expected_source = verify_teaching_plan_source(request.source)
        try:
            persisted_source = await source_verifier(session, expected_source)
            if not isinstance(persisted_source, SourceIdentity):
                persisted_source = SourceIdentity.model_validate(persisted_source)
        except SharedLessonFinalizationError:
            raise
        except Exception as exc:
            raise SharedLessonFinalizationError(
                "persisted approved Teaching Plan could not be verified"
            ) from exc
        if persisted_source != expected_source:
            raise SharedLessonFinalizationError(
                "persisted approved Teaching Plan differs from admitted source"
            )
        if (
            run.source_artifact_type != expected_source.source_artifact_type
            or run.source_artifact_id != expected_source.source_artifact_id
            or run.source_revision != expected_source.source_revision
            or run.source_hash != expected_source.source_hash
        ):
            raise SharedLessonFinalizationError(
                "generation run source identity differs from approved Teaching Plan"
            )

        try:
            # This exact repository loader is mandatory.  A custom callback
            # may add media/continuity checks, but cannot bypass durable
            # compose/write verification.
            verified_inputs = await load_verified_shared_lesson_inputs(
                session,
                run_id=request.run_id,
                owner_user_id=request.owner_user_id,
                source=request.source,
                tasks=request.tasks,
                sources=request.sources,
            )
        except SharedLessonInputError as exc:
            raise SharedLessonFinalizationError(
                "durable composer/writer outputs failed shared lesson input verification"
            ) from exc
        _verify_durable_inputs_match_handoff(
            document=request.handoff.document,
            tasks=request.tasks,
            verified_inputs=verified_inputs,
            handoff_expected_shapes=request.handoff.expected_shapes,
        )
        if work_item_loader is _load_default_work_item_outputs:
            loaded_outputs = await _load_default_work_item_outputs(session, request.run_id)
        else:
            loaded_outputs = _coerce_verified_outputs(
                await work_item_loader(session, request.run_id)
            )
        _verify_media_matches_work_items(
            document=request.handoff.document,
            media_results=request.media_results,
            active_items=active_items,
            loaded_outputs=loaded_outputs,
        )
        expected_item_ids = tuple(item.id for item in active_items)
        supplied_item_ids = tuple(output.work_item_id for output in loaded_outputs)
        if len(supplied_item_ids) != len(set(supplied_item_ids)):
            raise SharedLessonFinalizationError(
                "durable work-item loader returned duplicate identities"
            )
        if set(supplied_item_ids) != set(expected_item_ids):
            raise SharedLessonFinalizationError(
                "durable work-item loader did not cover the active work-item set"
            )

        document = request.handoff.document
        await save_shared_lesson_document(
            session,
            path_lesson_id=request.path_lesson_id,
            document=document,
        )
        stored = await promote_shared_lesson_document(
            session,
            path_lesson_id=request.path_lesson_id,
            source=request.source,
            assembly=SharedLessonAssemblyResult(
                document=request.handoff.document,
                qa=request.handoff.deterministic_qa,
                status=request.handoff.status,
            ),
            semantic_qa=request.handoff.semantic_qa,
            expected_shapes=request.handoff.expected_shapes,
            approved_source_ids=request.approved_source_ids,
            source_facts_by_section=request.source_facts_by_section,
            required_media_by_section=request.required_media_by_section,
            media_results=request.media_results,
        )
        finalized = await finalize_run(
            session,
            run_id=request.run_id,
            owner_user_id=request.owner_user_id,
            finalization=RunFinalization(
                source=expected_source,
                output_artifact_type="shared_lesson_document",
                output_artifact_id=document.id,
                output_revision=document.revision,
            ),
            source_verifier=source_verifier,
            artifact_loader=artifact_loader,
            now=now,
        )
        return SharedLessonFinalizationResult(document=stored, run=finalized)


__all__ = [
    "SharedLessonFinalizationError",
    "SharedLessonFinalizationRequest",
    "SharedLessonFinalizationResult",
    "VerifiedWorkItemOutput",
    "WorkItemOutputLoader",
    "finalize_shared_lesson_document",
]
