"""Durable document QA execution for SharedLessonDocument runs.

Deterministic QA is performed before admission.  The admitted item freezes the
approved Teaching Plan identity and the exact assembled document identity;
execution then makes the existing single FAST semantic review call through the
generic lease/fence/checkpoint runtime.  The loader is deliberately read-only
and verifies the active leaf again before a finalizer may consume its PASS.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.document_semantic import (
    DocumentSemanticInputError,
    DocumentSemanticOutputError,
    DocumentSemanticQAResult,
    DocumentSemanticValidator,
    qa_shared_lesson_document_semantics,
)
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import SharedLessonDocument
from document.shared_lesson.qa import DocumentQAResult
from document.shared_lesson.quality_flags import QualityFlag, quality_flags_from_issues
from document.shared_lesson.repository import save_shared_lesson_document
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source
from infra.config import settings
from infra.database.models import GenerationBuildModel, GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.execution.leases import LeaseLostError
from infra.generation_runtime import (
    AdmissionResult,
    CheckpointCompatibilityError,
    CheckpointIntegrityError,
    ErrorClass,
    RecoveryAction,
    RuntimeCheckpointCompatibility,
    SourceIdentity,
    WorkItemAdmission,
    WorkItemFailure,
    WorkItemReplacement,
    active_work_items,
    add_work_item,
    append_event,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
    replace_work_item,
)
DOCUMENT_QA_STAGE = "document_qa"
DOCUMENT_QA_ITEM_KEY = "document-qa"
DOCUMENT_QA_DEFINITION = "shared-document-qa:v1"

# Semantic reviewers may report these presentation-target findings directly.
# They are retained as teacher-visible flags and never gate READY, even when
# the configured semantic gate is blocking. Identity, schema, leakage, and
# task-correctness findings remain actionable QA issues.
SEMANTIC_ADVISORY_SHAPE_ISSUE_CODES = frozenset(
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


class DocumentQARuntimeError(ValueError):
    """The durable document QA boundary received an unsafe request."""


class DocumentQASourceConflict(DocumentQARuntimeError):
    """The document or approved source differs from the admitted Run."""


class DocumentQACheckpointError(DocumentQARuntimeError):
    """A checkpoint does not describe the exact frozen QA input."""


class DocumentQAOutputError(DocumentQARuntimeError):
    """A durable QA output is malformed or not bound to its source."""


class DocumentQAProvider(Protocol):
    async def __call__(self, request: Any) -> Any:
        """Review one exact assembled document."""


class DocumentQAWorkItemOutput(BaseModel):
    """Closed durable output persisted on the generic WorkItem row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    stage: Literal["document_qa"] = DOCUMENT_QA_STAGE
    source_plan_id: str = Field(min_length=1)
    source_plan_revision: int = Field(ge=1)
    source_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: str = Field(min_length=1)
    document_revision: int = Field(ge=1)
    document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_qa: DocumentSemanticQAResult
    #: Non-blocking findings from deterministic, semantic-shape, composer, and
    #: writer advisory checks. When present, ``semantic_qa`` is the issue-free
    #: PASS the run proceeds on and these flags carry what the reviewer reported.
    quality_flags: tuple[QualityFlag, ...] = ()

    @model_validator(mode="after")
    def _bind_result(self) -> DocumentQAWorkItemOutput:
        result = self.semantic_qa
        if (
            result.document_id != self.document_id
            or result.document_revision != self.document_revision
            or result.document_hash != self.document_hash
        ):
            raise ValueError("document QA result identity differs from its output binding")
        if result.semantic_calls > 1 or result.deterministic_skipped_semantic:
            raise ValueError("durable document QA output has invalid call accounting")
        return self


class VerifiedDocumentQA(BaseModel):
    """Read-only evidence returned after revalidating a ready QA leaf."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: str = Field(min_length=1)
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_qa: DocumentSemanticQAResult
    quality_flags: tuple[QualityFlag, ...] = ()

    @property
    def result(self) -> DocumentSemanticQAResult:
        return self.semantic_qa


@dataclass(frozen=True)
class DocumentQAWorkItemJob:
    """Inputs for one already-admitted document QA worker."""

    session: AsyncSession
    work_item_id: str
    worker_id: str
    owner_user_id: str
    source: TeachingPlanSource
    document: SharedLessonDocument
    deterministic_qa: DocumentQAResult
    semantic_validator: DocumentSemanticValidator | None = None
    lease_seconds: int = 300
    #: ``None`` resolves ``settings.document_quality_gate`` at execution time.
    quality_gate: Literal["advisory", "blocking"] | None = None
    #: Typed issues synthesized from accepted writer warnings (never provider
    #: output or learner text), merged with the semantic verdict so a document
    #: with an accepted SOFT writer issue routes to review instead of READY.
    #: Callers building a fresh revision-1 dispatch supply these; a reviewer
    #: replacement dispatch never does, since the reviewer's edit -- not the
    #: original writer warning -- is what semantic QA must judge next.
    synthetic_issues: tuple[ContinuityIssue, ...] = ()
    #: Shape findings from composer/writer are recorded as teacher-visible
    #: quality flags only. They never enter semantic review or block READY.
    advisory_issues: tuple[ContinuityIssue, ...] = ()


class DocumentQAOutcome(BaseModel):
    """Independent execution result for one QA work item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: str
    qa: DocumentQAWorkItemOutput | None = None
    error_code: str | None = None
    error_summary: str | None = None
    preserved_ready: bool = False


def _identity(source: TeachingPlanSource | SourceIdentity) -> SourceIdentity:
    if isinstance(source, TeachingPlanSource):
        return verify_teaching_plan_source(source)
    if isinstance(source, SourceIdentity):
        return source
    raise DocumentQASourceConflict(
        "document QA source must be an approved TeachingPlanSource or SourceIdentity"
    )


def _document_identity(document: SharedLessonDocument) -> tuple[str, int, str]:
    recomputed = shared_lesson_content_hash(document)
    if recomputed != document.content_hash:
        raise DocumentQASourceConflict("SharedLessonDocument content hash is stale")
    return document.id, document.revision, recomputed


def _verify_document_source(document: SharedLessonDocument, source: SourceIdentity) -> None:
    if source.source_artifact_type != "teaching_plan":
        raise DocumentQASourceConflict("document QA requires a Teaching Plan source")
    if (
        document.teaching_plan_id,
        document.teaching_plan_revision,
        document.teaching_plan_hash,
    ) != (source.source_artifact_id, source.source_revision, source.source_hash):
        raise DocumentQASourceConflict(
            "SharedLessonDocument lineage differs from the approved Teaching Plan"
        )
    _document_identity(document)


def _teaching_plan_sections(
    source: TeachingPlanSource,
) -> tuple[Any, ...]:
    return tuple(source.plan.sections)


async def _verify_run_source(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: SourceIdentity,
    lock: bool = False,
) -> GenerationRunModel:
    statement = select(GenerationRunModel).where(
        GenerationRunModel.id == run_id,
        GenerationRunModel.owner_user_id == owner_user_id,
    )
    if lock:
        statement = statement.with_for_update()
    run = await session.scalar(statement)
    if run is None:
        raise DocumentQASourceConflict("SharedDocument Run is unavailable to this owner")
    if run.run_type != "shared_document":
        raise DocumentQASourceConflict("document QA requires a SharedDocument Run")
    if (
        run.source_artifact_type,
        run.source_artifact_id,
        run.source_revision,
        run.source_hash,
    ) != (
        source.source_artifact_type,
        source.source_artifact_id,
        source.source_revision,
        source.source_hash,
    ):
        raise DocumentQASourceConflict("document QA source differs from the admitted Run")
    return run


def _input_hash(
    *,
    source: SourceIdentity,
    document: SharedLessonDocument,
    deterministic_qa: DocumentQAResult,
) -> str:
    payload = {
        "source": source.model_dump(mode="json"),
        "document": document.model_dump(mode="json"),
        "deterministic_qa": deterministic_qa.model_dump(mode="json"),
    }
    return content_hash(payload)


def _definition_hash() -> str:
    return hashlib.sha256(DOCUMENT_QA_DEFINITION.encode("utf-8")).hexdigest()


def _composition_identity(source: SourceIdentity, document: SharedLessonDocument) -> str:
    return json.dumps(
        {
            "source_plan_id": source.source_artifact_id,
            "source_plan_revision": source.source_revision,
            "source_plan_hash": source.source_hash,
            "document_id": document.id,
            "document_revision": document.revision,
            "document_hash": document.content_hash,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _item_request(
    *,
    run_id: str,
    source: SourceIdentity,
    document: SharedLessonDocument,
    deterministic_qa: DocumentQAResult,
    max_attempts: int,
    item_key: str = DOCUMENT_QA_ITEM_KEY,
) -> WorkItemAdmission:
    return WorkItemAdmission(
        run_id=run_id,
        item_key=item_key,
        stage=DOCUMENT_QA_STAGE,
        input_hash=_input_hash(source=source, document=document, deterministic_qa=deterministic_qa),
        definition_hash=_definition_hash(),
        composition_identity=_composition_identity(source, document),
        max_attempts=max_attempts,
    )


async def admit_document_qa_work_item(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    document: SharedLessonDocument,
    deterministic_qa: DocumentQAResult,
    max_attempts: int = 3,
) -> AdmissionResult:
    """Admit one QA item only after deterministic QA and lineage pass."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    identity = _identity(source)
    _teaching_plan_sections(source)
    _verify_document_source(document, identity)
    if (
        deterministic_qa.document_id != document.id
        or deterministic_qa.document_revision != document.revision
    ):
        raise DocumentQASourceConflict("deterministic QA identity differs from the document")
    if not deterministic_qa.ready:
        raise DocumentQARuntimeError(
            "document semantic QA cannot be admitted before deterministic QA passes"
        )
    run = await _verify_run_source(
        session,
        run_id=run_id,
        owner_user_id=owner_user_id,
        source=identity,
        lock=True,
    )
    return await add_work_item(
        session,
        _item_request(
            run_id=run.id,
            source=identity,
            document=document,
            deterministic_qa=deterministic_qa,
            max_attempts=max_attempts,
        ),
    )


async def admit_repaired_document_qa_work_item(
    session: AsyncSession,
    *,
    predecessor_work_item_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    document: SharedLessonDocument,
    deterministic_qa: DocumentQAResult,
    max_attempts: int = 3,
) -> GenerationWorkItemModel:
    """Admit a changed assembled document as a linked QA replacement."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    identity = _identity(source)
    _teaching_plan_sections(source)
    _verify_document_source(document, identity)
    if (
        deterministic_qa.document_id != document.id
        or deterministic_qa.document_revision != document.revision
    ):
        raise DocumentQASourceConflict("deterministic QA identity differs from the document")
    if not deterministic_qa.ready:
        raise DocumentQARuntimeError(
            "repaired document QA cannot be admitted before deterministic QA passes"
        )
    predecessor = await session.get(GenerationWorkItemModel, predecessor_work_item_id)
    if predecessor is None:
        raise DocumentQASourceConflict("document QA replacement predecessor does not exist")
    if predecessor.stage != DOCUMENT_QA_STAGE:
        raise DocumentQASourceConflict("document QA replacement predecessor has the wrong stage")
    run = await _verify_run_source(
        session,
        run_id=predecessor.run_id,
        owner_user_id=owner_user_id,
        source=identity,
    )
    replacement_key = (
        f"{DOCUMENT_QA_ITEM_KEY}:{document.id}:{document.revision}:{document.content_hash[:16]}"
    )
    return await replace_work_item(
        session,
        WorkItemReplacement(
            predecessor_work_item_id=predecessor_work_item_id,
            owner_user_id=owner_user_id,
            source=identity,
            replacement=_item_request(
                run_id=run.id,
                source=identity,
                document=document,
                deterministic_qa=deterministic_qa,
                max_attempts=max_attempts,
                item_key=replacement_key,
            ),
        ),
    )


def _checkpoint_compatibility(
    *, source: SourceIdentity, item: GenerationWorkItemModel
) -> RuntimeCheckpointCompatibility:
    return RuntimeCheckpointCompatibility(
        schema_version=1,
        source_revision=source.source_revision,
        source_hash=source.source_hash,
        input_hash=item.input_hash,
        definition_hash=item.definition_hash,
        composition_identity=item.composition_identity,
    )


def _checkpoint_payload(
    *, source: SourceIdentity, document: SharedLessonDocument, deterministic_qa: DocumentQAResult
) -> dict[str, Any]:
    return {
        "kind": DOCUMENT_QA_ITEM_KEY,
        "source": source.model_dump(mode="json"),
        "document_id": document.id,
        "document_revision": document.revision,
        "document_hash": document.content_hash,
        "deterministic_qa": deterministic_qa.model_dump(mode="json"),
    }


def _validate_item_binding(
    item: GenerationWorkItemModel,
    *,
    source: SourceIdentity,
    document: SharedLessonDocument,
    deterministic_qa: DocumentQAResult,
) -> None:
    if item.stage != DOCUMENT_QA_STAGE or not item.item_key.startswith(DOCUMENT_QA_ITEM_KEY):
        raise DocumentQACheckpointError("document QA work item has an unexpected identity")
    expected = _item_request(
        run_id=item.run_id,
        source=source,
        document=document,
        deterministic_qa=deterministic_qa,
        max_attempts=item.max_attempts,
    )
    if item.input_hash != expected.input_hash or item.definition_hash != expected.definition_hash:
        raise DocumentQACheckpointError("document QA work item input identity is stale")
    if item.composition_identity != expected.composition_identity:
        raise DocumentQACheckpointError("document QA work item composition identity is stale")


def _validate_checkpoint_payload(
    payload: Any,
    *,
    source: SourceIdentity,
    document: SharedLessonDocument,
    deterministic_qa: DocumentQAResult,
) -> None:
    expected = _checkpoint_payload(
        source=source, document=document, deterministic_qa=deterministic_qa
    )
    if payload != expected:
        raise DocumentQACheckpointError("document QA checkpoint is stale or conflicting")


def _failure_for_exception(exc: Exception) -> WorkItemFailure:
    """Classify operational failures without semantic fallback."""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return WorkItemFailure(
            error_code="document_qa_provider_transport",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="Document semantic QA provider transport failed.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, DocumentSemanticOutputError):
        return WorkItemFailure(
            error_code="document_qa_provider_output",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary="Document semantic QA provider output was malformed.",
            recovery_action=RecoveryAction.RETRY,
        )
    name = type(exc).__name__.casefold()
    if any(token in name for token in ("auth", "permission", "config", "program")):
        return WorkItemFailure(
            error_code="document_qa_configuration",
            error_class=ErrorClass.INTERNAL_PROGRAMMING,
            safe_summary="Document semantic QA provider configuration or authorization failed.",
            recovery_action=RecoveryAction.NONE,
        )
    if isinstance(exc, (DocumentSemanticInputError, DocumentQARuntimeError, ValidationError)):
        return WorkItemFailure(
            error_code="document_qa_validation",
            error_class=ErrorClass.VALIDATION,
            safe_summary="Document semantic QA input or output failed validation.",
            recovery_action=RecoveryAction.RETRY,
        )
    return WorkItemFailure(
        error_code="document_qa_failure",
        error_class=ErrorClass.INTERNAL_PROGRAMMING,
        safe_summary="Document semantic QA failed unexpectedly.",
        recovery_action=RecoveryAction.NONE,
    )


def _semantic_issue_payload(semantic: DocumentSemanticQAResult) -> dict[str, Any]:
    """Keep typed issue targets durable for a targeted correction worker."""
    return {
        "document_id": semantic.document_id,
        "document_revision": semantic.document_revision,
        "document_hash": semantic.document_hash,
        "issues": [issue.model_dump(mode="json") for issue in semantic.issues],
    }


async def execute_document_qa_work_item(
    job: DocumentQAWorkItemJob,
    *,
    now: datetime | None = None,
) -> DocumentQAOutcome:
    """Claim, review once, and fenced-commit one document QA item."""
    identity = _identity(job.source)
    _verify_document_source(job.document, identity)
    if (
        job.deterministic_qa.document_id != job.document.id
        or job.deterministic_qa.document_revision != job.document.revision
        or not job.deterministic_qa.ready
    ):
        raise DocumentQARuntimeError("document QA execution requires passing deterministic QA")
    work_item = await job.session.get(GenerationWorkItemModel, job.work_item_id)
    if work_item is None:
        raise DocumentQASourceConflict("document QA WorkItem does not exist")
    run = await _verify_run_source(
        job.session,
        run_id=work_item.run_id,
        owner_user_id=job.owner_user_id,
        source=identity,
    )
    item = await claim_work_item(
        job.session,
        work_item_id=job.work_item_id,
        worker_id=job.worker_id,
        source=identity,
        lease_seconds=job.lease_seconds,
        now=now,
    )
    compatibility = _checkpoint_compatibility(source=identity, item=item)
    try:
        _validate_item_binding(
            item,
            source=identity,
            document=job.document,
            deterministic_qa=job.deterministic_qa,
        )
        checkpoint = await load_compatible_checkpoint(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            compatibility=compatibility,
            now=now,
        )
        if checkpoint is None:
            await persist_checkpoint(
                job.session,
                work_item_id=item.id,
                worker_id=job.worker_id,
                lease_token=item.lease_token or 0,
                compatibility=compatibility,
                payload=_checkpoint_payload(
                    source=identity,
                    document=job.document,
                    deterministic_qa=job.deterministic_qa,
                ),
                now=now,
            )
        else:
            _validate_checkpoint_payload(
                checkpoint.payload,
                source=identity,
                document=job.document,
                deterministic_qa=job.deterministic_qa,
            )

        # The provider call is deliberately outside the database transaction.
        # Persist the lease claim and its compatible checkpoint first so a
        # separate worker can observe the durable fence, and so cancellation
        # or lease expiry can prevent a late provider result from becoming
        # ready output.
        await job.session.commit()

        semantic = await qa_shared_lesson_document_semantics(
            document=job.document,
            teaching_plan_sections=tuple(_teaching_plan_sections(job.source)),
            deterministic=job.deterministic_qa,
            semantic_validator=job.semantic_validator,
        )
        verdict_issues = tuple(semantic.issues)
        semantic_shape_issues = tuple(
            issue
            for issue in verdict_issues
            if issue.issue_code in SEMANTIC_ADVISORY_SHAPE_ISSUE_CODES
        )
        if job.synthetic_issues:
            # An accepted writer SOFT issue (task_answer_leaked or
            # unsupported_number) must still block automatic READY promotion
            # even when the semantic reviewer itself passed the text. Fold the
            # synthetic issues into the same typed-issue/review path a real
            # semantic ISSUE already uses below.
            semantic = DocumentSemanticQAResult(
                document_id=semantic.document_id,
                document_revision=semantic.document_revision,
                document_hash=semantic.document_hash,
                status="issue",
                issues=tuple(semantic.issues) + job.synthetic_issues,
                semantic_calls=semantic.semantic_calls,
                deterministic_skipped_semantic=semantic.deterministic_skipped_semantic,
            )
        combined_issues = tuple(semantic.issues)
        combined_actionable_issues = tuple(
            issue
            for issue in combined_issues
            if issue.issue_code not in SEMANTIC_ADVISORY_SHAPE_ISSUE_CODES
        )
        quality_flags: tuple[QualityFlag, ...] = ()
        gate = job.quality_gate or settings.document_quality_gate
        advisory_writer_flags = quality_flags_from_issues(
            job.advisory_issues, source="writer_warning"
        )
        quality_flags = advisory_writer_flags + quality_flags_from_issues(
            semantic_shape_issues, source="semantic_qa"
        )
        if gate == "advisory":
            quality_flags = (
                quality_flags_from_issues(
                    job.deterministic_qa.advisory_issues, source="deterministic_qa"
                )
                + quality_flags_from_issues(verdict_issues, source="semantic_qa")
                + quality_flags_from_issues(job.synthetic_issues, source="writer_warning")
                + advisory_writer_flags
            )
        else:
            # An exhausted figure ships as unavailable under both gate modes; the
            # teacher must still see the flag even when the gate is blocking.
            quality_flags += quality_flags_from_issues(
                tuple(
                    issue
                    for issue in job.deterministic_qa.advisory_issues
                    if issue.issue_code == "figure_media_unavailable"
                ),
                source="deterministic_qa",
            )
        if semantic_shape_issues and not combined_actionable_issues:
            # Presentation-target findings from a semantic reviewer are
            # advisory under both gate modes; preserve them in flags above.
            semantic = DocumentSemanticQAResult(
                document_id=semantic.document_id,
                document_revision=semantic.document_revision,
                document_hash=semantic.document_hash,
                status="pass",
                issues=(),
                semantic_calls=semantic.semantic_calls,
                deterministic_skipped_semantic=semantic.deterministic_skipped_semantic,
            )
        elif semantic_shape_issues and combined_actionable_issues:
            semantic = DocumentSemanticQAResult(
                document_id=semantic.document_id,
                document_revision=semantic.document_revision,
                document_hash=semantic.document_hash,
                status="issue",
                issues=combined_actionable_issues,
                semantic_calls=semantic.semantic_calls,
                deterministic_skipped_semantic=semantic.deterministic_skipped_semantic,
            )
        if not semantic.passed:
            # Only a well-formed semantic ISSUE after the deterministic gate is
            # reviewable. Persist that exact immutable candidate in this same
            # transaction as its issue event and failed WorkItem state.
            if (
                semantic.status != "issue"
                or not semantic.issues
                or semantic.semantic_calls != 1
                or semantic.deterministic_skipped_semantic
                or semantic.document_id != job.document.id
                or semantic.document_revision != job.document.revision
                or semantic.document_hash != shared_lesson_content_hash(job.document)
            ):
                raise DocumentQAOutputError("semantic QA issue is not bound to the candidate")
            if gate == "advisory":
                # Advisory gate: a well-formed semantic finding is a flag, not a
                # failure. The run proceeds on an issue-free PASS bound to the
                # exact document; the findings live in ``quality_flags``.
                semantic = DocumentSemanticQAResult(
                    document_id=semantic.document_id,
                    document_revision=semantic.document_revision,
                    document_hash=semantic.document_hash,
                    status="pass",
                    issues=(),
                    semantic_calls=semantic.semantic_calls,
                    deterministic_skipped_semantic=semantic.deterministic_skipped_semantic,
                )
        if not semantic.passed:
            path_lesson_id = await job.session.scalar(
                select(GenerationBuildModel.path_lesson_id).where(
                    GenerationBuildModel.id == run.build_id,
                    GenerationBuildModel.owner_user_id == job.owner_user_id,
                )
            )
            if path_lesson_id is None:
                raise DocumentQASourceConflict("document QA Run build is unavailable")
            await save_shared_lesson_document(
                job.session,
                path_lesson_id=path_lesson_id,
                document=job.document,
            )
            failure = WorkItemFailure(
                error_code="document_qa_semantic_issue",
                error_class=ErrorClass.VALIDATION,
                safe_summary="Document semantic QA reported an actionable learner-content issue.",
                recovery_action=RecoveryAction.REVIEW,
            )
            await fail_work_item(
                job.session,
                work_item_id=item.id,
                worker_id=job.worker_id,
                lease_token=item.lease_token or 0,
                failure=failure,
                now=now,
            )
            await append_event(
                job.session,
                run_id=item.run_id,
                work_item_id=item.id,
                event_type="document_qa_semantic_issues",
                error_code=failure.error_code,
                safe_payload=_semantic_issue_payload(semantic),
            )
            return DocumentQAOutcome(
                work_item_id=item.id,
                error_code=failure.error_code,
                error_summary=failure.safe_summary,
            )
        output = DocumentQAWorkItemOutput(
            source_plan_id=identity.source_artifact_id,
            source_plan_revision=identity.source_revision,
            source_plan_hash=identity.source_hash,
            document_id=job.document.id,
            document_revision=job.document.revision,
            document_hash=job.document.content_hash,
            semantic_qa=semantic,
            quality_flags=quality_flags,
        )
        await complete_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            output_json=output.model_dump(mode="json"),
            output_hash=content_hash(output.model_dump(mode="json")),
            now=now,
        )
        if quality_flags:
            await append_event(
                job.session,
                run_id=item.run_id,
                work_item_id=item.id,
                event_type="document_qa_advisory_flags",
                safe_payload={
                    "document_id": job.document.id,
                    "document_revision": job.document.revision,
                    "flag_count": len(quality_flags),
                    "codes": sorted({flag.code for flag in quality_flags}),
                },
            )
        return DocumentQAOutcome(work_item_id=item.id, qa=output)
    except LeaseLostError:
        raise
    except (CheckpointCompatibilityError, CheckpointIntegrityError, DocumentQACheckpointError):
        await fail_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            failure=WorkItemFailure(
                error_code="document_qa_checkpoint_conflict",
                error_class=ErrorClass.SOURCE_CONFLICT,
                safe_summary="Document QA checkpoint no longer matches its approved input.",
                recovery_action=RecoveryAction.NONE,
            ),
            now=now,
        )
        return DocumentQAOutcome(
            work_item_id=item.id,
            error_code="document_qa_checkpoint_conflict",
            error_summary="Document QA checkpoint no longer matches its approved input.",
        )
    except Exception as exc:  # noqa: BLE001 - classify and persist every provider failure.
        failure = _failure_for_exception(exc)
        await fail_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            failure=failure,
            now=now,
        )
        return DocumentQAOutcome(
            work_item_id=item.id,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
        )


def _coerce_output(value: Any) -> DocumentQAWorkItemOutput:
    try:
        return (
            value
            if isinstance(value, DocumentQAWorkItemOutput)
            else DocumentQAWorkItemOutput.model_validate(value)
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise DocumentQAOutputError(
            "durable document QA output violates its closed contract"
        ) from exc


async def load_verified_document_qa(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource | SourceIdentity,
    document: SharedLessonDocument,
) -> VerifiedDocumentQA:
    """Reload and verify the active QA leaf without mutating durable state."""
    identity = _identity(source)
    _verify_document_source(document, identity)
    run = await _verify_run_source(
        session,
        run_id=run_id,
        owner_user_id=owner_user_id,
        source=identity,
    )
    rows = list(
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
    leaves = active_work_items(rows)
    if len(leaves) != 1:
        raise DocumentQAOutputError("SharedDocument Run must have exactly one active QA leaf")
    item = leaves[0]
    if item.status != "ready":
        raise DocumentQAOutputError("active document QA WorkItem is not ready")
    if item.output_json is None or not item.output_hash:
        raise DocumentQAOutputError("active document QA WorkItem has no durable output")
    if content_hash(item.output_json) != item.output_hash:
        raise DocumentQAOutputError("active document QA WorkItem output hash changed")
    output = _coerce_output(item.output_json)
    if (
        output.source_plan_id,
        output.source_plan_revision,
        output.source_plan_hash,
    ) != (identity.source_artifact_id, identity.source_revision, identity.source_hash):
        raise DocumentQASourceConflict("durable document QA output source identity is stale")
    if (
        output.document_id,
        output.document_revision,
        output.document_hash,
    ) != (document.id, document.revision, document.content_hash):
        raise DocumentQASourceConflict("durable document QA output document identity is stale")
    result = output.semantic_qa
    if (
        not result.passed
        or result.status != "pass"
        or result.issues
        or result.semantic_calls != 1
        or result.deterministic_skipped_semantic
    ):
        raise DocumentQAOutputError("durable document QA WorkItem does not contain a PASS verdict")
    return VerifiedDocumentQA(
        work_item_id=item.id,
        output_hash=item.output_hash,
        semantic_qa=result,
        quality_flags=output.quality_flags,
    )


def quality_flags_from_work_items(
    items: Any,
) -> tuple[QualityFlag, ...]:
    """Flags on the active READY document-QA leaf of already-loaded work items.

    Pure and tolerant: anything that is not a hash-consistent, well-formed READY
    QA output yields no flags (flags are advisory; they never gate anything).
    """
    leaves = [
        item
        for item in active_work_items(tuple(items))
        if item.stage == DOCUMENT_QA_STAGE and item.status == "ready"
    ]
    if len(leaves) != 1:
        return ()
    item = leaves[0]
    if item.output_json is None or not item.output_hash:
        return ()
    if content_hash(item.output_json) != item.output_hash:
        return ()
    try:
        return _coerce_output(item.output_json).quality_flags
    except DocumentQAOutputError:
        return ()


async def load_run_quality_flags(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
) -> tuple[QualityFlag, ...]:
    """Owner-scoped, read-only flags for one SharedDocument Run."""
    run = await session.scalar(
        select(GenerationRunModel).where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
            GenerationRunModel.run_type == "shared_document",
        )
    )
    if run is None:
        return ()
    rows = (
        await session.scalars(
            select(GenerationWorkItemModel)
            .where(
                GenerationWorkItemModel.run_id == run.id,
                GenerationWorkItemModel.stage == DOCUMENT_QA_STAGE,
            )
            .order_by(GenerationWorkItemModel.id)
        )
    ).all()
    return quality_flags_from_work_items(rows)


async def load_verified_document_qa_result(
    session: AsyncSession,
    **kwargs: Any,
) -> DocumentSemanticQAResult:
    """Convenience loader for finalizers that consume the closed semantic result."""
    return (await load_verified_document_qa(session, **kwargs)).semantic_qa


__all__ = [
    "DOCUMENT_QA_DEFINITION",
    "DOCUMENT_QA_ITEM_KEY",
    "DOCUMENT_QA_STAGE",
    "DocumentQACheckpointError",
    "DocumentQAOutcome",
    "DocumentQAOutputError",
    "DocumentQAProvider",
    "DocumentQARuntimeError",
    "DocumentQASourceConflict",
    "DocumentQAWorkItemJob",
    "DocumentQAWorkItemOutput",
    "VerifiedDocumentQA",
    "admit_document_qa_work_item",
    "admit_repaired_document_qa_work_item",
    "execute_document_qa_work_item",
    "load_run_quality_flags",
    "load_verified_document_qa",
    "load_verified_document_qa_result",
    "quality_flags_from_work_items",
]
