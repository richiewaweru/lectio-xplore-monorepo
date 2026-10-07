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

import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.assembly import SharedLessonAssemblyResult
from document.shared_lesson.boundary import BoundaryValidationResult
from document.shared_lesson.boundary_runtime import (
    BOUNDARY_DEFINITION,
    BOUNDARY_STAGE,
    BoundaryWorkOrder,
    accepted_section_output_hash,
    boundary_advisory_input_hash,
    is_boundary_advisory_item,
)
from document.shared_lesson.continuity import ContinuityIssue, ExpectedNodeShape
from document.shared_lesson.handoff import SharedLessonHandoffEvidence
from document.shared_lesson.media import (
    BoundFigureMediaOutcome,
    SectionFigureMediaOutcome,
    SharedFigureMediaError,
    UnavailableFigureMediaResult,
    parse_media_outcome,
    verify_bound_media_outcome,
)
from document.shared_lesson.models import FigureNode, SharedLessonDocument
from document.shared_lesson.qa_runtime import (
    DocumentQARuntimeError,
    VerifiedDocumentQA,
    load_verified_document_qa,
)
from document.shared_lesson.repository import (
    SharedLessonDocumentRepositoryError,
    StoredSharedLessonDocument,
    load_shared_lesson_document,
    promote_shared_lesson_document,
    save_shared_lesson_document,
)
from document.shared_lesson.review_revision import (
    ReviewRevisionValidationError,
    prove_review_draft_chain,
)
from document.shared_lesson.runtime import (
    TeachingPlanSource,
    _stable_hash,
    verify_teaching_plan_source,
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
from document.shared_lesson.writer import SectionSource, SectionWriteResult
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    RunFinalization,
    SourceIdentity,
    active_work_items,
    append_event,
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
    media_results: tuple[BoundFigureMediaOutcome, ...]

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


async def resolve_review_structural_document(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    document: SharedLessonDocument,
    media_results: Sequence[BoundFigureMediaOutcome] = (),
) -> SharedLessonDocument:
    """Return the writer-composed structural document backing ``document``.

    For the unedited revision-1 path this is ``document`` itself.  For a
    reviewer-edited revision this walks and revalidates the immutable
    save-time proof chain back to revision 1 -- reproving every adjacent pair
    exactly as ``review-draft/revisions`` did when it was saved.  Only a
    proven pure-text correction may reach READY; the returned revision-1
    document is the one durable writer/boundary evidence must still match.

    A figure-containing section may be touched, but only when every figure in
    that section has an active READY media result
    in ``media_results`` bound to ``document`` -- the edited revision -- at
    its exact section output hash and figure semantic hash.  Editing a
    figure-containing section without a matching regenerated media result
    fails closed exactly like any other invalid media evidence; stale media
    frozen against a prior revision is never accepted here.
    """
    if document.revision == 1:
        return document
    chain: list[SharedLessonDocument] = []
    for revision in range(1, document.revision + 1):
        try:
            stored = await load_shared_lesson_document(
                session,
                document_id=document.id,
                revision=revision,
                path_lesson_id=path_lesson_id,
            )
        except SharedLessonDocumentRepositoryError as exc:
            raise SharedLessonFinalizationError(
                f"review revision chain is missing revision {revision}"
            ) from exc
        chain.append(stored.document)
    if chain[-1].content_hash != document.content_hash:
        raise SharedLessonFinalizationError(
            "requested review revision differs from its stored draft"
        )
    try:
        proof = prove_review_draft_chain(chain)
    except ReviewRevisionValidationError as exc:
        raise SharedLessonFinalizationError(
            f"review revision chain failed proof: {exc}"
        ) from exc
    if proof.figure_section_ids:
        touched_figures = {
            (section.id, node.id)
            for section in document.sections
            if section.id in proof.figure_section_ids
            for node in section.nodes
            if isinstance(node, FigureNode)
        }
        media_by_identity = {
            (result.section_id, result.figure_node_id): result for result in media_results
        }
        missing = sorted(
            f"{section_id}:{figure_node_id}"
            for section_id, figure_node_id in touched_figures
            if (section_id, figure_node_id) not in media_by_identity
        )
        if missing:
            raise SharedLessonFinalizationError(
                "review revision edited a figure-containing section without regenerated "
                f"media for: {missing!r}"
            )
        for identity in touched_figures:
            result = media_by_identity[identity]
            try:
                verify_bound_media_outcome(result, document)
            except SharedFigureMediaError as exc:
                raise SharedLessonFinalizationError(
                    f"review revision figure media for {identity[1]!r} failed verification: {exc}"
                ) from exc
    return chain[0]


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


def _verify_semantic_inputs_match_request(
    *,
    request: SharedLessonFinalizationRequest,
    verified_inputs: Any,
) -> None:
    """Bind caller evidence to the durable sourcebook and shared-task leaves."""
    if not _json_equal(verified_inputs.source, request.source):
        raise SharedLessonFinalizationError(
            "durable semantic inputs differ from the approved Teaching Plan source"
        )

    verified_tasks = tuple(verified_inputs.tasks)
    if len(verified_tasks) != len(request.tasks) or any(
        not _json_equal(left, right)
        for left, right in zip(verified_tasks, request.tasks, strict=False)
    ):
        raise SharedLessonFinalizationError(
            "caller task snapshots differ from the verified durable semantic task inputs"
        )

    try:
        derived_sources: list[SectionSource] = []
        source_by_id: dict[str, SectionSource] = {}
        for section in verified_inputs.source.plan.sections:
            for source in build_section_sources(verified_inputs, section):
                previous = source_by_id.get(source.id)
                if previous is None:
                    source_by_id[source.id] = source
                    derived_sources.append(source)
                elif not _json_equal(previous, source):
                    raise SectionSourceError(
                        f"verified sourcebook entry {source.id!r} has conflicting projections"
                    )
    except SectionSourceError as exc:
        raise SharedLessonFinalizationError(
            "verified sourcebook could not be projected into section sources"
        ) from exc

    supplied_sources = tuple(request.sources)
    if len(supplied_sources) != len(derived_sources) or any(
        not _json_equal(left, right)
        for left, right in zip(supplied_sources, derived_sources, strict=False)
    ):
        raise SharedLessonFinalizationError(
            "caller sources differ from the verified durable sourcebook projection"
        )

    expected_source_ids = tuple(source.id for source in derived_sources)
    if tuple(request.approved_source_ids) != expected_source_ids:
        raise SharedLessonFinalizationError(
            "approved source IDs differ from the verified sourcebook projection"
        )

    if request.source_facts_by_section and any(request.source_facts_by_section.values()):
        raise SharedLessonFinalizationError(
            "caller supplied source facts are not backed by a durable approved projection"
        )


def _verify_document_qa_matches_handoff(
    *,
    document: SharedLessonDocument,
    semantic_qa: Any,
    verified_qa: Any,
    active_items: Sequence[GenerationWorkItemModel],
) -> None:
    """Bind the finalizer handoff to the one active durable QA leaf."""
    if not isinstance(verified_qa, VerifiedDocumentQA):
        raise SharedLessonFinalizationError("durable document QA loader returned invalid evidence")
    active_ids = {item.id for item in active_items}
    if verified_qa.work_item_id not in active_ids:
        raise SharedLessonFinalizationError(
            "durable document QA WorkItem is not among the locked active work items"
        )
    observed = verified_qa.semantic_qa
    if (
        not observed.passed
        or observed.status != "pass"
        or observed.issues
        or observed.semantic_calls != 1
        or observed.deterministic_skipped_semantic
    ):
        raise SharedLessonFinalizationError(
            "durable document QA WorkItem does not contain a PASS verdict"
        )
    if (
        observed.document_id != document.id
        or observed.document_revision != document.revision
        or observed.document_hash != document.content_hash
    ):
        raise SharedLessonFinalizationError(
            "durable document QA result is stale for the finalization document"
        )
    if not _json_equal(observed, semantic_qa):
        raise SharedLessonFinalizationError(
            "durable document QA result differs from the handoff semantic QA"
        )


def _logical_boundary_item_key(
    item: GenerationWorkItemModel,
    by_id: Mapping[str, GenerationWorkItemModel],
) -> str:
    current = item
    seen: set[str] = set()
    while current.replaces_work_item_id is not None:
        if current.id in seen:
            raise SharedLessonFinalizationError("boundary replacement chain contains a cycle")
        seen.add(current.id)
        predecessor = by_id.get(current.replaces_work_item_id)
        if predecessor is None:
            raise SharedLessonFinalizationError(
                "boundary replacement chain has a missing predecessor"
            )
        current = predecessor
    return current.item_key


def _boundary_item_composition_identity(previous: str, next_: str) -> str:
    return json.dumps(
        {"previous": previous, "next": next_},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _verify_boundary_coverage(
    *,
    source: TeachingPlanSource,
    document: SharedLessonDocument,
    verified_inputs: Any,
    active_items: Sequence[GenerationWorkItemModel],
    all_items: Sequence[GenerationWorkItemModel] | None = None,
) -> None:
    """Verify every adjacent approved section has one current passing boundary."""
    plan_sections = tuple(source.plan.sections)
    accepted_sections = tuple(verified_inputs.sections)
    compositions = tuple(verified_inputs.compositions)
    if len(accepted_sections) != len(plan_sections) or len(compositions) != len(plan_sections):
        raise SharedLessonFinalizationError(
            "durable section inputs do not cover the approved section sequence"
        )
    if tuple(document.sections) != accepted_sections:
        raise SharedLessonFinalizationError(
            "boundary sections differ from the final handoff sections"
        )

    expected_pairs = tuple(pairwise(plan_sections))
    expected_keys = {
        f"boundary:{previous.slot_id}->{next_.slot_id}" for previous, next_ in expected_pairs
    }
    by_id = {item.id: item for item in (all_items if all_items is not None else active_items)}
    boundary_items: list[tuple[str, GenerationWorkItemModel]] = []
    for item in active_items:
        if item.stage != BOUNDARY_STAGE and not item.item_key.startswith("boundary:"):
            continue
        if item.stage != BOUNDARY_STAGE:
            raise SharedLessonFinalizationError("active boundary work item has an invalid stage")
        boundary_items.append((_logical_boundary_item_key(item, by_id), item))
    active_keys = [key for key, _item in boundary_items]
    if len(active_keys) != len(set(active_keys)):
        raise SharedLessonFinalizationError("duplicate active boundary work-item identity")
    if set(active_keys) != expected_keys:
        missing = sorted(expected_keys - set(active_keys))
        extra = sorted(set(active_keys) - expected_keys)
        raise SharedLessonFinalizationError(
            f"active boundary work-item set mismatch; missing={missing!r}, extra={extra!r}"
        )

    item_by_key = dict(boundary_items)
    definition_hash = hashlib.sha256(BOUNDARY_DEFINITION.encode("utf-8")).hexdigest()
    section_by_id = {section.id: section for section in accepted_sections}
    composition_by_id = {composition.section_slot_id: composition for composition in compositions}
    for previous_plan, next_plan in expected_pairs:
        previous = section_by_id.get(previous_plan.slot_id)
        next_ = section_by_id.get(next_plan.slot_id)
        previous_composition = composition_by_id.get(previous_plan.slot_id)
        next_composition = composition_by_id.get(next_plan.slot_id)
        if (
            previous is None
            or next_ is None
            or previous_composition is None
            or next_composition is None
        ):
            raise SharedLessonFinalizationError(
                "durable boundary inputs are missing an approved section pair"
            )
        expected_composition_output_hash = content_hash(
            previous_composition.model_dump(mode="json")
        )
        expected_section_output_hash = content_hash(
            SectionWriteResult(
                section_slot_id=previous_plan.slot_id,
                title=previous.title,
                nodes=previous.nodes,
                # The durable writer output carries its accepted SOFT-issue
                # warnings; omitting them here makes the hashes diverge.
                warnings=verified_inputs.section_warnings.get(previous_plan.slot_id, ()),
            ).model_dump(mode="json")
        )
        if (
            verified_inputs.composition_hashes.get(previous_plan.slot_id)
            != expected_composition_output_hash
            or verified_inputs.section_hashes.get(previous_plan.slot_id)
            != expected_section_output_hash
        ):
            raise SharedLessonFinalizationError(
                f"current accepted section inputs for {previous.id!r} have stale hashes"
            )
        expected_composition_output_hash = content_hash(next_composition.model_dump(mode="json"))
        expected_section_output_hash = content_hash(
            SectionWriteResult(
                section_slot_id=next_plan.slot_id,
                title=next_.title,
                nodes=next_.nodes,
                # The durable writer output carries its accepted SOFT-issue
                # warnings; omitting them here makes the hashes diverge.
                warnings=verified_inputs.section_warnings.get(next_plan.slot_id, ()),
            ).model_dump(mode="json")
        )
        if (
            verified_inputs.composition_hashes.get(next_plan.slot_id)
            != expected_composition_output_hash
            or verified_inputs.section_hashes.get(next_plan.slot_id) != expected_section_output_hash
        ):
            raise SharedLessonFinalizationError(
                f"current accepted section inputs for {next_.id!r} have stale hashes"
            )
        previous_identity = _stable_hash(previous_composition.model_dump(mode="json"))
        next_identity = _stable_hash(next_composition.model_dump(mode="json"))
        expected_work = BoundaryWorkOrder(
            source_plan_id=source.id,
            source_plan_revision=source.revision,
            source_plan_hash=source.content_hash,
            previous_section_id=previous.id,
            previous_section_output_hash=accepted_section_output_hash(previous),
            previous_composition_identity=previous_identity,
            next_section_id=next_.id,
            next_section_output_hash=accepted_section_output_hash(next_),
            next_composition_identity=next_identity,
        )
        item = item_by_key[f"boundary:{previous_plan.slot_id}->{next_plan.slot_id}"]
        if item.status != "ready" or item.output_json is None or not item.output_hash:
            raise SharedLessonFinalizationError(
                f"boundary work item for {previous.id!r}->{next_.id!r} is not ready"
            )
        if content_hash(item.output_json) != item.output_hash:
            raise SharedLessonFinalizationError(
                f"boundary work item for {previous.id!r}->{next_.id!r} has an invalid output hash"
            )
        expected_composition_identity = _boundary_item_composition_identity(
            previous_identity, next_identity
        )
        expected_input_hashes = {content_hash(expected_work.model_dump(mode="json"))}
        if is_boundary_advisory_item(item):
            # An advisory successor is bound to the ORIGINAL (still current)
            # work order through a distinct input identity.
            expected_input_hashes = {boundary_advisory_input_hash(expected_work)}
        if (
            item.input_hash not in expected_input_hashes
            or item.definition_hash != definition_hash
            or item.composition_identity != expected_composition_identity
        ):
            raise SharedLessonFinalizationError(
                f"boundary work item for {previous.id!r}->{next_.id!r} has stale input binding"
            )
        raw = item.output_json
        if not isinstance(raw, Mapping):
            raise SharedLessonFinalizationError("boundary output violates its closed schema")
        expected_output_keys = {
            "kind",
            "status",
            "work",
            "previous_section",
            "next_section",
            "semantic_calls",
        }
        if (
            set(raw) - {"advisories"} != expected_output_keys
            or raw.get("kind") != "shared_lesson_boundary_result"
        ):
            raise SharedLessonFinalizationError("boundary output violates its closed schema")
        try:
            if "advisories" in raw:
                if not isinstance(raw["advisories"], list):
                    raise TypeError("boundary advisories must be a list")
                for advisory in raw["advisories"]:
                    ContinuityIssue.model_validate(advisory)
            observed_work = BoundaryWorkOrder.model_validate(raw["work"])
            result = BoundaryValidationResult.model_validate(
                {key: raw[key] for key in expected_output_keys if key not in {"kind", "work"}}
            )
        except (TypeError, ValueError) as exc:
            raise SharedLessonFinalizationError(
                "boundary output violates its closed schema"
            ) from exc
        if observed_work != expected_work:
            raise SharedLessonFinalizationError(
                f"boundary output for {previous.id!r}->{next_.id!r} has stale work identity"
            )
        if not result.passed:
            raise SharedLessonFinalizationError(
                f"boundary output for {previous.id!r}->{next_.id!r} is not PASS"
            )
        if result.previous_section != previous or result.next_section != next_:
            raise SharedLessonFinalizationError(
                f"boundary output for {previous.id!r}->{next_.id!r} has stale sections"
            )


_UNAVAILABLE_MEDIA_COMPARISON_FIELDS = (
    "source_plan_id",
    "source_plan_revision",
    "source_plan_hash",
    "section_id",
    "section_output_hash",
    "figure_node_id",
    "figure_semantic_hash",
    "work_order_id",
    "visual_id",
    "alt_text",
    "mode",
    "required",
    "source_facts",
    "status",
    "error_code",
    "reason",
    "attempts",
)

_READY_MEDIA_COMPARISON_FIELDS = (
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
    "alt_text",
    "mode",
    "required",
    "source_facts",
    "status",
)

def _parse_media_work_item_output(payload: Any, *, item_id: str) -> SectionFigureMediaOutcome:
    """Parse one durable media output (ready or unavailable)."""
    try:
        return parse_media_outcome(payload)
    except (TypeError, ValueError) as exc:
        raise SharedLessonFinalizationError(
            f"durable media output for work item {item_id!r} is invalid"
        ) from exc


def _verify_media_matches_work_items(
    *,
    document: SharedLessonDocument,
    media_results: Sequence[BoundFigureMediaOutcome],
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
    outputs_by_figure: dict[tuple[str, str], SectionFigureMediaOutcome] = {}
    for item in media_items:
        output = output_by_id.get(item.id)
        if output is None:
            raise SharedLessonFinalizationError(
                f"durable media output is missing for work item {item.id!r}"
            )
        parsed = _parse_media_work_item_output(output.output_json, item_id=item.id)
        if item.item_key != f"media:{parsed.work_order_id}":
            raise SharedLessonFinalizationError(
                f"durable media work item {item.id!r} has a mismatched work order"
            )
        identity = (parsed.section_id, parsed.figure_node_id)
        if identity in outputs_by_figure:
            raise SharedLessonFinalizationError(
                f"durable media outputs duplicate figure identity {identity!r}"
            )
        outputs_by_figure[identity] = parsed
    for result in media_results:
        parsed = outputs_by_figure.get((result.section_id, result.figure_node_id))
        if parsed is None:
            raise SharedLessonFinalizationError(
                f"bound media has no matching durable output for {result.figure_node_id!r}"
            )
        parsed_payload = parsed.model_dump(mode="json")
        result_payload = result.model_dump(mode="json")
        if result_payload.get("status") != parsed_payload.get("status"):
            raise SharedLessonFinalizationError(
                "bound media field 'status' differs from its durable work-item output"
            )
        fields = (
            _UNAVAILABLE_MEDIA_COMPARISON_FIELDS
            if isinstance(parsed, UnavailableFigureMediaResult)
            else _READY_MEDIA_COMPARISON_FIELDS
        )
        for field in fields:
            if result_payload[field] != parsed_payload[field]:
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
            verified_semantic_inputs = await load_verified_semantic_inputs(
                session,
                run_id=request.run_id,
                owner_user_id=request.owner_user_id,
                source=request.source,
            )
            _verify_semantic_inputs_match_request(
                request=request,
                verified_inputs=verified_semantic_inputs,
            )
        except SemanticInputError as exc:
            raise SharedLessonFinalizationError(
                "durable semantic task/source inputs failed shared lesson input verification"
            ) from exc

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
        structural_document = await resolve_review_structural_document(
            session,
            path_lesson_id=request.path_lesson_id,
            document=request.handoff.document,
            media_results=request.media_results,
        )
        _verify_durable_inputs_match_handoff(
            document=structural_document,
            tasks=request.tasks,
            verified_inputs=verified_inputs,
            handoff_expected_shapes=request.handoff.expected_shapes,
        )
        _verify_boundary_coverage(
            source=request.source,
            document=structural_document,
            verified_inputs=verified_inputs,
            active_items=active_items,
            all_items=locked_items,
        )
        try:
            verified_qa = await load_verified_document_qa(
                session,
                run_id=request.run_id,
                owner_user_id=request.owner_user_id,
                source=request.source,
                document=request.handoff.document,
            )
            _verify_document_qa_matches_handoff(
                document=request.handoff.document,
                semantic_qa=request.handoff.semantic_qa,
                verified_qa=verified_qa,
                active_items=active_items,
            )
        except DocumentQARuntimeError as exc:
            raise SharedLessonFinalizationError(
                "durable document QA failed finalization verification"
            ) from exc
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
        if document.revision != 1:
            await append_event(
                session,
                run_id=request.run_id,
                event_type="review_revision_promoted",
                safe_payload={
                    "document_revision": document.revision,
                    "content_hash": document.content_hash,
                },
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
