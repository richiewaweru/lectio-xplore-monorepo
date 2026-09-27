"""Owner-scoped reviewer submit: revalidate an edited draft for requalification.

This is the trust boundary between a reviewer's saved text-only draft
revisions (``review-draft/revisions``) and durable re-admission of a document
semantic QA replacement work item.  It never runs the semantic provider
itself; it only proves the saved edits are allowlisted text corrections,
recomputes deterministic QA, and admits the linked replacement so the
existing generic runtime and the post-section pipeline can execute it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from document.shared_lesson.approved_source import (
    ApprovedSourceVerificationError,
    load_current_approved_teaching_plan_source,
)
from document.shared_lesson.composer import SectionCompositionPlan
from document.shared_lesson.continuity import ContinuityIssue, ExpectedNodeShape
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import FigureNode, SharedLessonDocument
from document.shared_lesson.qa import qa_shared_lesson_document
from document.shared_lesson.qa_runtime import (
    DOCUMENT_QA_STAGE,
    DocumentQARuntimeError,
    admit_repaired_document_qa_work_item,
)
from document.shared_lesson.repository import (
    SharedLessonDocumentRepositoryError,
    load_shared_lesson_document,
)
from document.shared_lesson.review_revision import (
    ReviewRevisionValidationError,
    prove_review_draft_chain,
)
from document.shared_lesson.section_sources import build_section_sources
from document.shared_lesson.semantic_inputs import SemanticInputError, load_verified_semantic_inputs
from document.shared_lesson.work_item_inputs import (
    SharedLessonInputError,
    load_verified_shared_lesson_inputs,
)
from infra.database.models import (
    GenerationBuildModel,
    GenerationEventModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    SharedLessonDocumentModel,
)
from infra.generation_runtime import active_work_items


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


def _required_media(document: SharedLessonDocument) -> dict[str, tuple[str, ...]]:
    return {
        section.id: tuple(node.id for node in section.nodes if isinstance(node, FigureNode))
        for section in document.sections
        if any(isinstance(node, FigureNode) for node in section.nodes)
    }


class ReviewSubmitError(ValueError):
    """Base error for the review-draft submit boundary."""


class ReviewSubmitNotFound(ReviewSubmitError):
    """The run, draft, or QA leaf is unavailable to this owner."""


class ReviewSubmitConflict(ReviewSubmitError):
    """Run/draft state, staleness, or a figure edit blocks submission."""


class ReviewSubmitInvalid(ReviewSubmitError):
    """The saved edit chain does not prove a valid review revision."""


@dataclass(frozen=True)
class ReviewDraftContext:
    """Resolved owner-scoped review state for one failed_recoverable Run."""

    run: GenerationRunModel
    path_lesson_id: str
    preparation_generation_id: str
    leaf: GenerationWorkItemModel
    origin: SharedLessonDocument
    latest: SharedLessonDocument
    issues: tuple[ContinuityIssue, ...]


@dataclass(frozen=True)
class ReviewSubmitOutcome:
    """Closed projection of one successful review-submit admission."""

    run_id: str
    work_item_id: str
    document_id: str
    document_revision: int
    content_hash: str


async def _load_document(
    session: AsyncSession,
    *,
    document_id: str,
    revision: int,
    path_lesson_id: str,
    expected_hash: str | None = None,
) -> SharedLessonDocument:
    try:
        stored = await load_shared_lesson_document(
            session,
            document_id=document_id,
            revision=revision,
            path_lesson_id=path_lesson_id,
        )
    except SharedLessonDocumentRepositoryError:
        raise ReviewSubmitNotFound("shared document revision is unavailable") from None
    document = stored.document
    if stored.status != "draft" or shared_lesson_content_hash(document) != document.content_hash:
        raise ReviewSubmitNotFound("shared document revision is not an editable draft")
    if expected_hash is not None and document.content_hash != expected_hash:
        raise ReviewSubmitNotFound("shared document revision hash does not match its evidence")
    return document


async def load_review_draft_context(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
) -> ReviewDraftContext:
    """Resolve the immutable semantic-issue origin and the latest saved draft."""
    row = await session.execute(
        select(GenerationRunModel, GenerationBuildModel.path_lesson_id)
        .join(GenerationBuildModel, GenerationBuildModel.id == GenerationRunModel.build_id)
        .where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
            GenerationBuildModel.owner_user_id == owner_user_id,
            GenerationRunModel.run_type == "shared_document",
            GenerationRunModel.status != "ready",
        )
    )
    candidate = row.one_or_none()
    if candidate is None:
        raise ReviewSubmitNotFound("SharedDocument Run is not available for review")
    run, path_lesson_id = candidate

    items = tuple(
        (
            await session.scalars(
                select(GenerationWorkItemModel)
                .where(
                    GenerationWorkItemModel.run_id == run.id,
                    GenerationWorkItemModel.stage == DOCUMENT_QA_STAGE,
                )
                .order_by(GenerationWorkItemModel.id)
            )
        ).all()
    )
    leaves = active_work_items(items)
    if len(leaves) != 1:
        raise ReviewSubmitNotFound(
            "SharedDocument Run does not have exactly one active document QA leaf"
        )
    leaf = leaves[0]
    if leaf.status != "failed_recoverable" or leaf.recovery_action != "review":
        raise ReviewSubmitNotFound("document QA leaf is not awaiting reviewer submission")

    event = await session.scalar(
        select(GenerationEventModel)
        .where(
            GenerationEventModel.run_id == run.id,
            GenerationEventModel.work_item_id == leaf.id,
            GenerationEventModel.event_type == "document_qa_semantic_issues",
            GenerationEventModel.error_code == "document_qa_semantic_issue",
        )
        .order_by(GenerationEventModel.seq.desc())
    )
    if event is None or not isinstance(event.safe_payload_json, dict):
        raise ReviewSubmitNotFound("document QA issue evidence is unavailable")
    payload = event.safe_payload_json
    try:
        document_id = payload["document_id"]
        origin_revision = payload["document_revision"]
        digest = payload["document_hash"]
        if not isinstance(document_id, str) or not isinstance(origin_revision, int):
            raise ValueError("document identity is malformed")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("document hash is malformed")
        issues = tuple(ContinuityIssue.model_validate(issue) for issue in payload["issues"])
        if not issues:
            raise ValueError("semantic issue list is empty")
    except (KeyError, TypeError, ValueError) as exc:
        raise ReviewSubmitNotFound("document QA issue evidence is malformed") from exc

    origin = await _load_document(
        session,
        document_id=document_id,
        revision=origin_revision,
        path_lesson_id=path_lesson_id,
        expected_hash=digest,
    )
    if (
        origin.teaching_plan_id != run.source_artifact_id
        or origin.teaching_plan_revision != run.source_revision
        or origin.teaching_plan_hash != run.source_hash
    ):
        raise ReviewSubmitNotFound("document QA issue evidence is stale for this Run")

    latest_revision = await session.scalar(
        select(SharedLessonDocumentModel.revision)
        .where(
            SharedLessonDocumentModel.id == document_id,
            SharedLessonDocumentModel.path_lesson_id == path_lesson_id,
            SharedLessonDocumentModel.status == "draft",
        )
        .order_by(SharedLessonDocumentModel.revision.desc())
        .limit(1)
    )
    if latest_revision is None:
        raise ReviewSubmitNotFound("no editable draft is available for this Run")
    latest = await _load_document(
        session,
        document_id=document_id,
        revision=latest_revision,
        path_lesson_id=path_lesson_id,
    )
    if (
        latest.teaching_plan_id != run.source_artifact_id
        or latest.teaching_plan_revision != run.source_revision
        or latest.teaching_plan_hash != run.source_hash
    ):
        raise ReviewSubmitNotFound("latest draft is stale for this Run")

    lesson = await session.get(PathLessonModel, path_lesson_id)
    preparation_generation_id = lesson.pack_id if lesson is not None and lesson.pack_id else ""

    return ReviewDraftContext(
        run=run,
        path_lesson_id=path_lesson_id,
        preparation_generation_id=preparation_generation_id,
        leaf=leaf,
        origin=origin,
        latest=latest,
        issues=issues,
    )


async def submit_review_draft_for_requalification(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    expected_revision: int,
    expected_hash: str,
) -> ReviewSubmitOutcome:
    """Revalidate the saved edit chain and admit one document QA replacement.

    Deterministic and lineage checks fail closed with a typed error the HTTP
    boundary maps onto 404/409/422.  This never calls the semantic provider;
    it only re-qualifies the edited draft for the existing document QA
    execution and finalization paths to consume.
    """
    context = await load_review_draft_context(session, run_id=run_id, owner_user_id=owner_user_id)
    latest = context.latest
    if latest.revision != expected_revision or latest.content_hash != expected_hash:
        raise ReviewSubmitConflict("review draft changed; reload before submitting")
    if latest.revision == context.origin.revision:
        raise ReviewSubmitConflict("review draft has no saved correction to submit")
    if not context.preparation_generation_id:
        raise ReviewSubmitNotFound("path lesson has no active preparation generation")

    chain: list[SharedLessonDocument] = [context.origin]
    for revision in range(context.origin.revision + 1, latest.revision + 1):
        chain.append(
            await _load_document(
                session,
                document_id=context.origin.id,
                revision=revision,
                path_lesson_id=context.path_lesson_id,
            )
        )
    try:
        proof = prove_review_draft_chain(chain)
    except ReviewRevisionValidationError as exc:
        raise ReviewSubmitInvalid(f"review draft revision is invalid: {exc}") from exc
    if proof.figure_section_ids:
        raise ReviewSubmitConflict("review_edit_invalidates_media")

    try:
        source = await load_current_approved_teaching_plan_source(
            session=session,
            owner_user_id=owner_user_id,
            path_lesson_id=context.path_lesson_id,
            preparation_generation_id=context.preparation_generation_id,
        )
        if (
            latest.teaching_plan_id != source.id
            or latest.teaching_plan_revision != source.revision
            or latest.teaching_plan_hash != source.content_hash
        ):
            raise ReviewSubmitConflict("approved Teaching Plan changed since the original document")
        semantic = await load_verified_semantic_inputs(
            session,
            run_id=context.run.id,
            owner_user_id=owner_user_id,
            source=source,
        )
        sources = []
        seen_sources: set[str] = set()
        for section in source.plan.sections:
            for projected in build_section_sources(semantic, section):
                if projected.id not in seen_sources:
                    seen_sources.add(projected.id)
                    sources.append(projected)
        accepted = await load_verified_shared_lesson_inputs(
            session,
            run_id=context.run.id,
            owner_user_id=owner_user_id,
            source=source,
            tasks=semantic.tasks,
            sources=tuple(sources),
        )
    except ApprovedSourceVerificationError as exc:
        raise ReviewSubmitConflict(f"approved Teaching Plan source is unavailable: {exc}") from exc
    except (SemanticInputError, SharedLessonInputError) as exc:
        raise ReviewSubmitConflict(f"durable writer inputs are unavailable: {exc}") from exc

    expected_shapes = _expected_shapes({item.section_slot_id: item for item in accepted.compositions})
    required_media = {
        section_id: figure_ids
        for section_id, figure_ids in _required_media(context.origin).items()
    }
    figure_ids = tuple(
        node.id
        for section in context.origin.sections
        for node in section.nodes
        if isinstance(node, FigureNode)
    )
    deterministic_qa = qa_shared_lesson_document(
        document=latest,
        teaching_plan_sections=tuple(source.plan.sections),
        expected_shapes=expected_shapes,
        expected_title=source.plan.learner_title,
        approved_source_ids=tuple(item.id for item in sources),
        required_media_by_section=required_media,
        available_media_ids=figure_ids,
    )
    if not deterministic_qa.ready:
        raise ReviewSubmitInvalid(
            "deterministic document QA failed for the reviewed revision: "
            + ", ".join(issue.issue_code for issue in deterministic_qa.issues)
        )

    try:
        replacement = await admit_repaired_document_qa_work_item(
            session,
            predecessor_work_item_id=context.leaf.id,
            owner_user_id=owner_user_id,
            source=source,
            document=latest,
            deterministic_qa=deterministic_qa,
        )
    except DocumentQARuntimeError as exc:
        raise ReviewSubmitConflict(f"document QA replacement could not be admitted: {exc}") from exc

    return ReviewSubmitOutcome(
        run_id=context.run.id,
        work_item_id=replacement.id,
        document_id=latest.id,
        document_revision=latest.revision,
        content_hash=latest.content_hash,
    )


__all__ = [
    "ReviewDraftContext",
    "ReviewSubmitConflict",
    "ReviewSubmitError",
    "ReviewSubmitInvalid",
    "ReviewSubmitNotFound",
    "ReviewSubmitOutcome",
    "load_review_draft_context",
    "submit_review_draft_for_requalification",
]
