"""Same-Run deterministic assembly and semantic QA dispatch for shared lessons."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.assembly import (
    SharedLessonAssemblyError,
    assemble_shared_lesson_document,
)
from document.shared_lesson.composer import (
    CompositionValidationError,
    SectionCompositionPlan,
    validate_composition_plan,
)
from document.shared_lesson.continuity import ContinuityIssue, ExpectedNodeShape
from document.shared_lesson.quality_flags import QualityFlag
from document.shared_lesson.document_semantic import DocumentSemanticValidator
from document.shared_lesson.media import (
    BoundFigureMediaOutcome,
    BoundUnavailableFigureMedia,
    FigureMediaResult,
    SharedFigureMediaError,
    SharedFigureWorkOrder,
    bind_durable_media_outcome,
    verify_bound_media_outcome,
)
from document.shared_lesson.media_runtime import (
    MAX_CONCURRENT_MEDIA,
    MEDIA_STAGE,
    MediaReadiness,
    MediaRuntimeError,
    MediaWorkItemJob,
    execute_figure_media_work_items,
    project_media_readiness,
    work_order_from_composition_identity,
)
from document.shared_lesson.models import FigureNode, SharedLessonDocument, SharedSection
from document.shared_lesson.qa import (
    DocumentQAResult,
    qa_shared_lesson_document,
    split_media_outcomes,
)
from document.shared_lesson.qa_runtime import (
    DOCUMENT_QA_STAGE,
    DocumentQAOutcome,
    DocumentQAWorkItemJob,
    VerifiedDocumentQA,
    admit_document_qa_work_item,
    execute_document_qa_work_item,
    load_verified_document_qa,
)
from document.shared_lesson.repository import (
    SharedLessonDocumentRepositoryError,
    load_shared_lesson_document,
)
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source
from infra.database.models import GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import active_work_items


class SharedDocumentQADispatchError(ValueError):
    """Verified inputs cannot produce one durable same-Run QA result."""


class SharedDocumentQADispatchResult(BaseModel):
    """Closed result containing the immutable document and durable QA PASS."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    work_item_id: str
    document: SharedLessonDocument
    deterministic_qa: DocumentQAResult
    verified_qa: VerifiedDocumentQA


def _by_section(
    values: Mapping[str, Any] | Sequence[Any],
    *,
    identity: str,
    expected: tuple[str, ...],
    label: str,
) -> dict[str, Any]:
    if isinstance(values, Mapping):
        result = dict(values)
    else:
        result = {}
        for value in values:
            key = getattr(value, identity, None)
            if not isinstance(key, str) or not key:
                raise SharedDocumentQADispatchError(f"{label} has an invalid section identity")
            if key in result:
                raise SharedDocumentQADispatchError(f"{label} contains duplicate section {key!r}")
            result[key] = value
    if tuple(result) != expected:
        raise SharedDocumentQADispatchError(
            f"{label} must cover approved sections in order; expected {expected!r}"
        )
    return result


def _expected_shapes(
    compositions: Mapping[str, SectionCompositionPlan],
) -> dict[str, tuple[ExpectedNodeShape, ...]]:
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


#: Maps a writer SOFT issue code (see writer.SOFT_SECTION_WRITE_ISSUE_CODES)
#: to the typed continuity issue code a reviewer sees for it.
_WRITER_WARNING_ISSUE_CODES = {
    "task_answer_leaked": "answer_leakage",
    "unsupported_number": "unsupported_claim",
}
_WRITER_ADVISORY_CODES = frozenset(
    {
        "length_over_target",
        "shape_missing",
        "list_item_not_parallel",
        "paragraph_run_exceeded",
        "block_exceeds_node_limit",
        "section_exceeds_node_limit",
        "section_exceeds_callout_limit",
        "heading_missing_subsection_cue",
        "kind_missing_semantic_cue",
        "callout_missing_cautionary_cue",
    }
)
_WRITER_WARNING_NODE_PATH = re.compile(r"^nodes\[(\d+)\]")


def _writer_warning_node_id(
    path: str, composition: SectionCompositionPlan | None
) -> str | None:
    """Resolve a writer warning's sanitized structural path to a real node ID.

    The writer records only a structural path (e.g. ``nodes[2].text``),
    indexing the section's ordinary (non-task-anchor) composition items in
    order -- never learner text. This recovers the actual document node ID
    from that index and the section's own accepted composition, so a
    synthetic review issue can target the exact node.
    """
    if composition is None:
        return None
    match = _WRITER_WARNING_NODE_PATH.match(path)
    if not match:
        return None
    index = int(match.group(1))
    ordinary_ids = [item.id for item in composition.items if item.kind != "task_anchor"]
    if 0 <= index < len(ordinary_ids):
        return ordinary_ids[index]
    return None


def _synthetic_writer_issues(
    writer_warnings: Mapping[str, Sequence[tuple[str, str]]],
    compositions: Mapping[str, SectionCompositionPlan],
) -> tuple[ContinuityIssue, ...]:
    """Build typed, reviewable issues from writer warnings accepted at write time.

    An accepted SOFT writer issue (see ``writer.SOFT_SECTION_WRITE_ISSUE_CODES``)
    must not let the document reach READY unreviewed; this turns each
    (code, path) warning into the same typed ``ContinuityIssue`` shape a real
    semantic QA issue uses, so it can be merged into the existing review path.
    """
    issues: list[ContinuityIssue] = []
    for section_id, warnings in writer_warnings.items():
        if not warnings:
            continue
        composition = compositions.get(section_id)
        for code, path in warnings:
            if code in _WRITER_ADVISORY_CODES:
                continue
            issue_code = _WRITER_WARNING_ISSUE_CODES.get(code)
            if issue_code is None:
                raise SharedDocumentQADispatchError(
                    f"unknown writer warning code {code!r} for section {section_id!r}"
                )
            node_id = _writer_warning_node_id(path, composition)
            issues.append(
                ContinuityIssue(
                    issue_code=issue_code,
                    affected_section_id=section_id,
                    affected_node_ids=(node_id,) if node_id else (),
                    explanation=(
                        "The section writer accepted this content on a bounded final "
                        "repair attempt; a reviewer must confirm or correct it."
                    ),
                    required_correction="Review and correct the affected section content.",
                )
            )
    return tuple(issues)


def _advisory_writer_issues(
    writer_warnings: Mapping[str, Sequence[tuple[str, str]]],
    compositions: Mapping[str, SectionCompositionPlan],
) -> tuple[ContinuityIssue, ...]:
    """Project shape warnings into quality flags without gating READY."""
    issues: list[ContinuityIssue] = []
    for section_id, warnings in writer_warnings.items():
        composition = compositions.get(section_id)
        for code, path in warnings:
            if code not in _WRITER_ADVISORY_CODES:
                continue
            node_id = _writer_warning_node_id(path, composition)
            issues.append(
                ContinuityIssue(
                    issue_code=code,
                    affected_section_id=section_id,
                    affected_node_ids=(node_id,) if node_id else (),
                    explanation=(
                        f"Advisory shape check {code} at {path}; all written content was preserved."
                    ),
                    required_correction=(
                        f"Review advisory shape check {code} at {path} if a future revision is needed."
                    ),
                )
            )
    return tuple(issues)


def _required_media(document: SharedLessonDocument) -> dict[str, tuple[str, ...]]:
    return {
        section.id: tuple(node.id for node in section.nodes if isinstance(node, FigureNode))
        for section in document.sections
        if any(isinstance(node, FigureNode) for node in section.nodes)
    }


def _verify_media_inputs(
    *,
    document: SharedLessonDocument,
    required_media_by_section: Mapping[str, Sequence[str]] | None,
    media_results: Sequence[BoundFigureMediaOutcome],
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
        raise SharedDocumentQADispatchError(
            "required media declaration must match the assembled document figures"
        )
    expected_ids = {
        (section_id, figure_id) for section_id, values in expected.items() for figure_id in values
    }
    supplied: dict[tuple[str, str], BoundFigureMediaOutcome] = {}
    for result in media_results:
        if not isinstance(result, (FigureMediaResult, BoundUnavailableFigureMedia)):
            raise SharedDocumentQADispatchError(
                "required media must use verified document-bound media outcomes"
            )
        identity = (result.section_id, result.figure_node_id)
        if identity in supplied:
            raise SharedDocumentQADispatchError(f"required media figure {identity!r} is duplicated")
        try:
            verify_bound_media_outcome(result, document)
        except SharedFigureMediaError as exc:
            raise SharedDocumentQADispatchError(
                f"required media figure {result.figure_node_id!r} is not verified"
            ) from exc
        if not result.required:
            raise SharedDocumentQADispatchError(
                f"required media figure {result.figure_node_id!r} is not marked required"
            )
        supplied[identity] = result
    supplied_ids = set(supplied)
    missing = sorted(expected_ids - supplied_ids)
    unexpected = sorted(supplied_ids - expected_ids)
    if missing:
        raise SharedDocumentQADispatchError(f"required media is not ready for figures: {missing!r}")
    if unexpected:
        raise SharedDocumentQADispatchError(
            f"media supplied for undeclared document figures: {unexpected!r}"
        )
    return tuple(sorted(result.figure_node_id for result in supplied.values()))



def _dispatchable(record: Any) -> bool:
    """Queued, or running under an expired lease (worker died mid-QA).

    ``claim_work_item`` already fences an expired lease takeover, so a
    restart during semantic QA must not strand the leaf in ``running``.
    """
    status = getattr(record, "status", None)
    if status == "queued":
        return True
    if status != "running":
        return False
    expires = getattr(record, "lease_expires_at", None)
    if expires is None:
        return False
    now = datetime.now(UTC).replace(tzinfo=None)
    if getattr(expires, "tzinfo", None) is not None:
        expires = expires.astimezone(UTC).replace(tzinfo=None)
    return expires <= now

async def _load_durable_media_results(
    session_factory: Callable[[], Any],
    *,
    run_id: str,
    document: SharedLessonDocument,
    supplied: Sequence[BoundFigureMediaOutcome],
) -> tuple[BoundFigureMediaOutcome, ...]:
    """Rebuild caller media evidence from active READY media WorkItems."""
    async with session_factory() as session:
        rows = tuple(
            (
                await session.scalars(
                    select(GenerationWorkItemModel)
                    .where(
                        GenerationWorkItemModel.run_id == run_id,
                        GenerationWorkItemModel.stage == "media_generation",
                    )
                    .order_by(GenerationWorkItemModel.id)
                )
            ).all()
        )
    leaves = active_work_items(rows)
    durable: dict[tuple[str, str], BoundFigureMediaOutcome] = {}
    for item in leaves:
        if item.status != "ready" or item.output_json is None or not item.output_hash:
            raise SharedDocumentQADispatchError(
                "required media outputs must be active READY WorkItems"
            )
        if content_hash(item.output_json) != item.output_hash:
            raise SharedDocumentQADispatchError("durable media output hash is invalid")
        try:
            bound = bind_durable_media_outcome(item.output_json, document)
            if item.item_key != f"media:{bound.work_order_id}":
                raise ValueError("media WorkItem identity differs from its output")
        except (TypeError, ValueError, SharedFigureMediaError) as exc:
            raise SharedDocumentQADispatchError(
                f"durable media output for WorkItem {item.id!r} is invalid"
            ) from exc
        identity = (bound.section_id, bound.figure_node_id)
        if identity in durable:
            raise SharedDocumentQADispatchError(
                f"durable media outputs duplicate figure identity {identity!r}"
            )
        durable[identity] = bound

    caller: dict[tuple[str, str], BoundFigureMediaOutcome] = {}
    for result in supplied:
        identity = (result.section_id, result.figure_node_id)
        if identity in caller:
            raise SharedDocumentQADispatchError(
                f"caller media evidence duplicates figure identity {identity!r}"
            )
        caller[identity] = result
    if set(caller) != set(durable):
        raise SharedDocumentQADispatchError(
            "caller media evidence does not match durable READY media outputs"
        )
    for identity, result in caller.items():
        if result != durable[identity]:
            raise SharedDocumentQADispatchError(
                f"caller media evidence differs from durable output for {identity!r}"
            )
    return tuple(durable.values())


async def dispatch_shared_document_qa(
    session_factory: Callable[[], Any],
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    compositions: Mapping[str, SectionCompositionPlan] | Sequence[SectionCompositionPlan],
    sections: Mapping[str, SharedSection] | Sequence[SharedSection],
    tasks: Sequence[SharedTaskSpec] = (),
    document_id: str,
    document_revision: int,
    created_at: datetime | str,
    provenance: Mapping[str, Any] | None = None,
    source_facts_by_section: Mapping[str, Sequence[str]] | None = None,
    required_media_by_section: Mapping[str, Sequence[str]] | None = None,
    media_results: Sequence[BoundFigureMediaOutcome] = (),
    writer_warnings: Mapping[str, Sequence[tuple[str, str]]] | None = None,
    boundary_quality_flags: Sequence[QualityFlag] = (),
    semantic_validator: DocumentSemanticValidator | None = None,
    worker_id: str = "shared-document-qa-dispatcher",
    max_attempts: int = 3,
) -> SharedDocumentQADispatchResult:
    """Assemble and execute exactly one semantic QA WorkItem on an existing Run.

    ``writer_warnings`` (section slot ID -> accepted SOFT writer issue
    (code, path) pairs) is only ever supplied for a fresh revision-1
    dispatch; it becomes synthetic typed issues merged into the semantic
    verdict so the document routes to review instead of READY when the
    writer accepted a bounded content issue. It must never be supplied for a
    reviewer-edited replacement dispatch (see ``dispatch_reviewed_document_qa``),
    since the reviewer's edit -- not the original writer warning -- is what
    semantic QA judges for that revision.
    """
    if not run_id.strip() or not owner_user_id.strip():
        raise ValueError("run_id and owner_user_id must be non-empty")
    if not worker_id.strip():
        raise ValueError("worker_id must be non-empty")
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if source_facts_by_section and any(source_facts_by_section.values()):
        raise SharedDocumentQADispatchError(
            "source facts require a verified durable source projection"
        )
    try:
        verify_teaching_plan_source(source)
    except ValueError as exc:
        raise SharedDocumentQADispatchError("approved Teaching Plan source is invalid") from exc

    section_ids = tuple(section.slot_id for section in source.plan.sections)
    if not section_ids:
        raise SharedDocumentQADispatchError("approved Teaching Plan has no sections")
    composition_by_section = _by_section(
        compositions,
        identity="section_slot_id",
        expected=section_ids,
        label="compositions",
    )
    section_by_id = _by_section(
        sections,
        identity="id",
        expected=section_ids,
        label="sections",
    )
    try:
        for plan_section in source.plan.sections:
            validate_composition_plan(
                plan=composition_by_section[plan_section.slot_id],
                section=plan_section,
                tasks=tuple(
                    task
                    for task in tasks
                    if task.teaching_block_id in {block.id for block in plan_section.blocks}
                ),
            )
    except (CompositionValidationError, TypeError, ValueError) as exc:
        raise SharedDocumentQADispatchError("accepted composition is invalid") from exc

    try:
        assembly = assemble_shared_lesson_document(
            document_id=document_id,
            revision=document_revision,
            source=source,
            accepted_sections=section_by_id,
            tasks=tasks,
            provenance=provenance,
            created_at=created_at,
            expected_shapes=_expected_shapes(composition_by_section),
            approved_source_ids=_approved_source_ids(source),
            source_facts_by_section=None,
            required_media_by_section={},
            available_media_ids=(),
        )
    except SharedLessonAssemblyError as exc:
        raise SharedDocumentQADispatchError(str(exc)) from exc
    if not assembly.ready:
        raise SharedDocumentQADispatchError(
            "deterministic document QA failed: "
            + ", ".join(issue.issue_code for issue in assembly.qa.issues)
        )
    durable_media = await _load_durable_media_results(
        session_factory,
        run_id=run_id,
        document=assembly.document,
        supplied=media_results,
    )
    _verify_media_inputs(
        document=assembly.document,
        required_media_by_section=required_media_by_section,
        media_results=durable_media,
    )
    try:
        assembly = assemble_shared_lesson_document(
            document_id=document_id,
            revision=document_revision,
            source=source,
            accepted_sections=section_by_id,
            tasks=tasks,
            provenance=provenance,
            created_at=created_at,
            expected_shapes=_expected_shapes(composition_by_section),
            approved_source_ids=_approved_source_ids(source),
            source_facts_by_section=None,
            required_media_by_section=required_media_by_section,
            available_media_ids=split_media_outcomes(durable_media)[0],
            unavailable_media=split_media_outcomes(durable_media)[1],
        )
    except SharedLessonAssemblyError as exc:
        raise SharedDocumentQADispatchError(str(exc)) from exc
    if not assembly.ready:
        raise SharedDocumentQADispatchError(
            "deterministic document QA failed: "
            + ", ".join(issue.issue_code for issue in assembly.qa.issues)
        )

    async with session_factory() as admission_session:
        admitted = await admit_document_qa_work_item(
            admission_session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            document=assembly.document,
            deterministic_qa=assembly.qa,
            max_attempts=max_attempts,
        )
        await admission_session.commit()

    synthetic_issues = _synthetic_writer_issues(writer_warnings or {}, composition_by_section)
    advisory_issues = _advisory_writer_issues(writer_warnings or {}, composition_by_section)
    if _dispatchable(admitted.record):
        async with session_factory() as execution_session:
            outcome: DocumentQAOutcome = await execute_document_qa_work_item(
                DocumentQAWorkItemJob(
                    session=execution_session,
                    work_item_id=admitted.record.id,
                    worker_id=worker_id,
                    owner_user_id=owner_user_id,
                    source=source,
                    document=assembly.document,
                    deterministic_qa=assembly.qa,
                    semantic_validator=semantic_validator,
                    synthetic_issues=synthetic_issues,
                    advisory_issues=advisory_issues,
                    boundary_quality_flags=tuple(boundary_quality_flags),
                )
            )
            await execution_session.commit()
        if outcome.qa is None:
            raise SharedDocumentQADispatchError(
                outcome.error_summary or "document semantic QA did not produce a PASS"
            )
    elif admitted.record.status != "ready":
        raise SharedDocumentQADispatchError(
            f"document QA WorkItem is not dispatchable from {admitted.record.status!r}"
        )

    async with session_factory() as load_session:
        verified = await load_verified_document_qa(
            load_session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            document=assembly.document,
        )
    return SharedDocumentQADispatchResult(
        run_id=run_id,
        work_item_id=verified.work_item_id,
        document=assembly.document,
        deterministic_qa=assembly.qa,
        verified_qa=verified,
    )


async def load_review_replacement_document(
    session_factory: Callable[[], Any],
    *,
    path_lesson_id: str,
    source: TeachingPlanSource,
    leaf: GenerationWorkItemModel,
) -> SharedLessonDocument:
    """Load and revalidate the exact reviewer-edited draft revision bound to ``leaf``.

    ``leaf`` must be the active document QA WorkItem admitted by
    ``admit_repaired_document_qa_work_item`` for one reviewer-edited draft
    revision. This is the single durable source both the review QA dispatch
    and the review media dispatch use to resolve that exact revision, so
    neither ever trusts an in-memory or caller-supplied document.
    """
    try:
        identity = verify_teaching_plan_source(source)
    except ValueError as exc:
        raise SharedDocumentQADispatchError("approved Teaching Plan source is invalid") from exc
    if leaf.stage != DOCUMENT_QA_STAGE or leaf.replaces_work_item_id is None:
        raise SharedDocumentQADispatchError(
            "leaf is not an admitted document QA review replacement"
        )

    try:
        bound = json.loads(leaf.composition_identity)
        document_id = bound["document_id"]
        document_revision = bound["document_revision"]
        document_hash = bound["document_hash"]
        if not isinstance(document_id, str) or not isinstance(document_revision, int):
            raise ValueError("bound document identity is malformed")
        if not isinstance(document_hash, str) or len(document_hash) != 64:
            raise ValueError("bound document hash is malformed")
    except (TypeError, ValueError, KeyError) as exc:
        raise SharedDocumentQADispatchError(
            "review replacement composition identity is invalid"
        ) from exc

    async with session_factory() as load_session:
        try:
            stored = await load_shared_lesson_document(
                load_session,
                document_id=document_id,
                revision=document_revision,
                path_lesson_id=path_lesson_id,
            )
        except SharedLessonDocumentRepositoryError as exc:
            raise SharedDocumentQADispatchError(
                "review replacement draft revision is unavailable"
            ) from exc
    document = stored.document
    if document.content_hash != document_hash:
        raise SharedDocumentQADispatchError("review replacement draft revision is stale")
    if (
        document.teaching_plan_id,
        document.teaching_plan_revision,
        document.teaching_plan_hash,
    ) != (identity.source_artifact_id, identity.source_revision, identity.source_hash):
        raise SharedDocumentQADispatchError(
            "review replacement draft lineage differs from the approved Teaching Plan"
        )
    return document


def _media_lease_eligible(item: GenerationWorkItemModel, now: datetime) -> bool:
    if item.status == "queued":
        return True
    if item.status != "running":
        return False
    expiry = item.lease_expires_at
    if expiry is None:
        return False
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)
    return expiry <= now


async def dispatch_reviewed_figure_media(
    session_factory: Callable[[], Any],
    *,
    run_id: str,
    owner_user_id: str,
    path_lesson_id: str,
    source: TeachingPlanSource,
    leaf: GenerationWorkItemModel,
    media_executor: Any,
    worker_id: str = "shared-document-review-media",
    lease_seconds: int = 300,
    concurrency: int = MAX_CONCURRENT_MEDIA,
) -> tuple[SharedLessonDocument, MediaReadiness]:
    """Execute (or reload) durable figure media replacements for a reviewed draft.

    Unlike the ordinary media dispatcher, this never re-derives figure work
    orders from the durable writer/composer outputs at revision 1 -- a
    reviewer edit may have changed a figure-containing section's exact text,
    and ``review-draft/submit`` already regenerated that section's figures as
    linked replacement media WorkItems bound to the edited revision. This
    loads the exact edited revision bound to ``leaf``, reconstructs every
    active media WorkItem's frozen work order from its own durable
    composition identity (never from a caller-supplied section), executes
    any that are still queued or hold an expired lease against that
    revision's sections, and projects readiness exactly like the ordinary
    dispatcher.
    """
    if not run_id.strip() or not owner_user_id.strip() or not path_lesson_id.strip():
        raise ValueError("run_id, owner_user_id, and path_lesson_id must be non-empty")
    document = await load_review_replacement_document(
        session_factory, path_lesson_id=path_lesson_id, source=source, leaf=leaf
    )

    async with session_factory() as probe_session:
        rows = tuple(
            (
                await probe_session.scalars(
                    select(GenerationWorkItemModel).where(
                        GenerationWorkItemModel.run_id == run_id,
                        GenerationWorkItemModel.stage == MEDIA_STAGE,
                    )
                )
            ).all()
        )
    leaves = active_work_items(rows)
    works: dict[str, SharedFigureWorkOrder] = {}
    for item in leaves:
        try:
            works[item.id] = work_order_from_composition_identity(item.composition_identity)
        except MediaRuntimeError as exc:
            raise SharedDocumentQADispatchError(
                f"media WorkItem {item.id!r} has an invalid frozen work order"
            ) from exc

    section_by_id = {section.id: section for section in document.sections}
    current = datetime.now(UTC).replace(tzinfo=None)
    async with AsyncExitStack() as stack:
        jobs: list[MediaWorkItemJob] = []
        for item in leaves:
            if not _media_lease_eligible(item, current):
                continue
            work = works[item.id]
            section = section_by_id.get(work.section_id)
            if section is None:
                raise SharedDocumentQADispatchError(
                    f"media WorkItem {item.id!r} references a section absent from the "
                    "reviewed document"
                )
            stage_session = await stack.enter_async_context(session_factory())
            jobs.append(
                MediaWorkItemJob(
                    session=stage_session,
                    work_item_id=item.id,
                    worker_id=worker_id,
                    source=source,
                    work=work,
                    accepted_section=section,
                    executor=media_executor,
                    status="queued",
                    lease_seconds=lease_seconds,
                )
            )
        if jobs:
            await execute_figure_media_work_items(jobs, concurrency=concurrency)

    async with session_factory() as reload_session:
        fresh_rows = tuple(
            (
                await reload_session.scalars(
                    select(GenerationWorkItemModel).where(
                        GenerationWorkItemModel.run_id == run_id,
                        GenerationWorkItemModel.stage == MEDIA_STAGE,
                    )
                )
            ).all()
        )
    fresh_leaves = active_work_items(fresh_rows)
    expected_figures = tuple(
        (section.id, node.id)
        for section in document.sections
        for node in section.nodes
        if isinstance(node, FigureNode)
    )
    readiness = project_media_readiness(
        fresh_rows,
        works,
        expected_required_work_item_ids=tuple(item.id for item in fresh_leaves),
        expected_figure_identities=expected_figures,
    )
    return document, readiness


async def dispatch_reviewed_document_qa(
    session_factory: Callable[[], Any],
    *,
    run_id: str,
    owner_user_id: str,
    path_lesson_id: str,
    source: TeachingPlanSource,
    leaf: GenerationWorkItemModel,
    compositions: Mapping[str, SectionCompositionPlan] | Sequence[SectionCompositionPlan],
    required_media_by_section: Mapping[str, Sequence[str]] | None = None,
    media_results: Sequence[BoundFigureMediaOutcome] = (),
    boundary_quality_flags: Sequence[QualityFlag] = (),
    semantic_validator: DocumentSemanticValidator | None = None,
    worker_id: str = "shared-document-qa-dispatcher",
) -> SharedDocumentQADispatchResult:
    """Execute (or load) an already-admitted reviewer-repair QA replacement.

    Unlike :func:`dispatch_shared_document_qa`, this never re-assembles the
    document from durable writer/composer outputs.  ``leaf`` must be the
    active document QA WorkItem admitted by
    ``admit_repaired_document_qa_work_item`` for one reviewer-edited draft
    revision; this loads and revalidates that exact stored revision by the
    identity bound in the leaf's own composition identity, recomputes
    deterministic QA against it, and only then executes (or reloads) the
    already-admitted semantic QA leaf.
    """
    if not run_id.strip() or not owner_user_id.strip() or not path_lesson_id.strip():
        raise ValueError("run_id, owner_user_id, and path_lesson_id must be non-empty")
    document = await load_review_replacement_document(
        session_factory, path_lesson_id=path_lesson_id, source=source, leaf=leaf
    )

    composition_by_section = (
        dict(compositions)
        if isinstance(compositions, Mapping)
        else {item.section_slot_id: item for item in compositions}
    )
    deterministic_qa = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=tuple(source.plan.sections),
        expected_shapes=_expected_shapes(composition_by_section),
        expected_title=source.plan.learner_title,
        approved_source_ids=_approved_source_ids(source),
        required_media_by_section=required_media_by_section,
        available_media_ids=split_media_outcomes(media_results)[0],
        unavailable_media=split_media_outcomes(media_results)[1],
    )
    if not deterministic_qa.ready:
        raise SharedDocumentQADispatchError(
            "deterministic document QA failed for the review replacement: "
            + ", ".join(issue.issue_code for issue in deterministic_qa.issues)
        )

    if _dispatchable(leaf):
        async with session_factory() as execution_session:
            outcome: DocumentQAOutcome = await execute_document_qa_work_item(
                DocumentQAWorkItemJob(
                    session=execution_session,
                    work_item_id=leaf.id,
                    worker_id=worker_id,
                    owner_user_id=owner_user_id,
                    source=source,
                    document=document,
                    deterministic_qa=deterministic_qa,
                    semantic_validator=semantic_validator,
                    boundary_quality_flags=tuple(boundary_quality_flags),
                )
            )
            await execution_session.commit()
        if outcome.qa is None:
            raise SharedDocumentQADispatchError(
                outcome.error_summary or "review replacement document QA did not produce a PASS"
            )
    elif leaf.status != "ready":
        raise SharedDocumentQADispatchError(
            f"review replacement document QA is not dispatchable from {leaf.status!r}"
        )

    async with session_factory() as verify_session:
        verified = await load_verified_document_qa(
            verify_session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            document=document,
        )
    return SharedDocumentQADispatchResult(
        run_id=run_id,
        work_item_id=verified.work_item_id,
        document=document,
        deterministic_qa=deterministic_qa,
        verified_qa=verified,
    )


__all__ = [
    "SharedDocumentQADispatchError",
    "SharedDocumentQADispatchResult",
    "dispatch_reviewed_document_qa",
    "dispatch_reviewed_figure_media",
    "dispatch_shared_document_qa",
    "load_review_replacement_document",
]
