"""Durable storage and trusted loading for SharedLessonDocument artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document.shared_lesson.assembly import SharedLessonAssemblyResult
from document.shared_lesson.document_semantic import DocumentSemanticQAResult
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.hashing import verify_shared_lesson_source as verify_document_source
from document.shared_lesson.media import (
    DeferredFigureMediaBinding,
    FigureMediaResult,
    SharedFigureMediaError,
    verify_bound_deferred_figure_media,
    verify_bound_figure_media,
)
from document.shared_lesson.models import FigureNode, SharedLessonDocument
from document.shared_lesson.qa import DocumentQAError, qa_shared_lesson_document
from document.shared_lesson.runtime import (
    SectionRuntimeError,
    TeachingPlanSource,
    verify_teaching_plan_source,
)
from infra.config import settings
from infra.database.models import SharedLessonDocumentModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime.contracts import SourceIdentity, VerifiedArtifact

DocumentStatus = Literal["draft", "ready"]


class SharedLessonDocumentRepositoryError(ValueError):
    """Base class for expected shared-document persistence failures."""


class SharedLessonDocumentConflict(SharedLessonDocumentRepositoryError):
    """A document identity was already used for different immutable content."""


class SharedLessonDocumentNotFound(SharedLessonDocumentRepositoryError):
    """The requested document revision is unavailable."""


class SharedLessonDocumentIntegrityError(SharedLessonDocumentRepositoryError):
    """Stored identity, JSON, or content hashes cannot be trusted."""


class SharedLessonDocumentReadinessError(SharedLessonDocumentRepositoryError):
    """A document failed the final QA, lineage, or required-media gate."""


@dataclass(frozen=True)
class StoredSharedLessonDocument:
    """A validated durable envelope and its full JSON artifact hash."""

    document: SharedLessonDocument
    path_lesson_id: str
    status: DocumentStatus
    storage_hash: str


def _canonical_json(document: SharedLessonDocument | Mapping[str, Any]) -> dict[str, Any]:
    """Serialize one validated document using the runtime's strict JSON shape."""
    payload = (
        document.model_dump(mode="json")
        if isinstance(document, SharedLessonDocument)
        else dict(document)
    )
    if not isinstance(payload, dict):  # pragma: no cover - Pydantic guarantees this
        raise SharedLessonDocumentIntegrityError("document payload is not a JSON object")
    return payload


def _canonical_bytes(payload: Mapping[str, Any]) -> str:
    """Return the runtime hash of a canonical JSON object."""
    return content_hash(dict(payload))


def _validate_stored_row(
    row: SharedLessonDocumentModel,
    *,
    expected_path_lesson_id: str | None = None,
) -> StoredSharedLessonDocument:
    if row.status not in {"draft", "ready"}:
        raise SharedLessonDocumentIntegrityError("stored document has an invalid lifecycle status")
    if expected_path_lesson_id is not None and row.path_lesson_id != expected_path_lesson_id:
        raise SharedLessonDocumentIntegrityError("stored document belongs to a different lesson")
    if not isinstance(row.document_json, Mapping):
        raise SharedLessonDocumentIntegrityError("stored document JSON must be an object")

    try:
        document = SharedLessonDocument.model_validate(row.document_json)
    except ValidationError as exc:
        raise SharedLessonDocumentIntegrityError(
            "stored document JSON failed contract validation"
        ) from exc

    expected_columns = {
        "id": document.id,
        "revision": document.revision,
        "teaching_plan_id": document.teaching_plan_id,
        "teaching_plan_revision": document.teaching_plan_revision,
        "teaching_plan_hash": document.teaching_plan_hash,
        "content_hash": document.content_hash,
    }
    for field, expected in expected_columns.items():
        if getattr(row, field) != expected:
            raise SharedLessonDocumentIntegrityError(
                f"stored document {field} does not match canonical JSON"
            )
    if shared_lesson_content_hash(document) != row.content_hash:
        raise SharedLessonDocumentIntegrityError("stored document content hash is invalid")

    canonical_payload = _canonical_json(document)
    if _canonical_bytes(row.document_json) != _canonical_bytes(canonical_payload):
        raise SharedLessonDocumentIntegrityError("stored document JSON is not canonical")

    return StoredSharedLessonDocument(
        document=document,
        path_lesson_id=row.path_lesson_id,
        status=row.status,
        storage_hash=_canonical_bytes(canonical_payload),
    )


def _validate_input_document(document: SharedLessonDocument) -> dict[str, Any]:
    try:
        validated = SharedLessonDocument.model_validate(document.model_dump(mode="json"))
    except ValidationError as exc:
        raise SharedLessonDocumentIntegrityError("document failed contract validation") from exc
    payload = _canonical_json(validated)
    if shared_lesson_content_hash(validated) != validated.content_hash:
        raise SharedLessonDocumentIntegrityError("document content hash is invalid")
    return payload


def _same_immutable_identity(
    row: SharedLessonDocumentModel,
    *,
    path_lesson_id: str,
    document: SharedLessonDocument,
    payload: Mapping[str, Any],
) -> bool:
    return (
        row.path_lesson_id == path_lesson_id
        and row.id == document.id
        and row.revision == document.revision
        and row.teaching_plan_id == document.teaching_plan_id
        and row.teaching_plan_revision == document.teaching_plan_revision
        and row.teaching_plan_hash == document.teaching_plan_hash
        and row.content_hash == document.content_hash
        and _canonical_bytes(row.document_json) == _canonical_bytes(payload)
    )


async def save_shared_lesson_document(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    document: SharedLessonDocument,
) -> StoredSharedLessonDocument:
    """Persist one draft revision idempotently.

    This operation deliberately has no READY transition. Final QA and required
    media evidence must be wired by the generic runtime before a document may
    become ready.
    """
    if not path_lesson_id:
        raise ValueError("path_lesson_id must not be blank")
    payload = _validate_input_document(document)
    identity = {"id": document.id, "revision": document.revision}
    existing = await session.get(SharedLessonDocumentModel, identity)
    if existing is not None:
        stored = _validate_stored_row(existing, expected_path_lesson_id=path_lesson_id)
        if not _same_immutable_identity(
            existing,
            path_lesson_id=path_lesson_id,
            document=document,
            payload=payload,
        ):
            raise SharedLessonDocumentConflict(
                "shared document identity is already bound to different content or lineage"
            )
        return stored

    row = SharedLessonDocumentModel(
        id=document.id,
        revision=document.revision,
        path_lesson_id=path_lesson_id,
        teaching_plan_id=document.teaching_plan_id,
        teaching_plan_revision=document.teaching_plan_revision,
        teaching_plan_hash=document.teaching_plan_hash,
        content_hash=document.content_hash,
        document_json=payload,
        status="draft",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        # A concurrent writer may have won the composite-key insert. Resolve
        # it through the same integrity checks rather than returning a partial row.
        existing = await session.get(SharedLessonDocumentModel, identity)
        if existing is None:
            raise SharedLessonDocumentConflict("shared document insert conflicted") from None
        stored = _validate_stored_row(existing, expected_path_lesson_id=path_lesson_id)
        if not _same_immutable_identity(
            existing,
            path_lesson_id=path_lesson_id,
            document=document,
            payload=payload,
        ):
            raise SharedLessonDocumentConflict(
                "shared document identity is already bound to different content or lineage"
            )
        return stored

    return _validate_stored_row(row, expected_path_lesson_id=path_lesson_id)


def _validate_required_media(
    *,
    document: SharedLessonDocument,
    required_media_by_section: Mapping[str, Sequence[str]],
    media_results: Sequence[FigureMediaResult | DeferredFigureMediaBinding],
) -> None:
    """Require every declared figure to be bound to this exact document.

    ``FigureMediaResult`` is the closed, post-assembly media contract.  Calling
    the binder again here is intentional: persistence is the last boundary
    before READY and must recompute the document, section, and semantic
    identities even when an upstream worker already validated them.

    A figure may instead be a ``DeferredFigureMediaBinding`` only when the
    local-only ``shared_document_media_optional`` switch is enabled; when it
    is off, a deferred binding is rejected exactly like any other invalid
    media evidence, fail-closed, regardless of what produced it.
    """
    expected: dict[str, str] = {}
    for section_id, figure_ids in required_media_by_section.items():
        for figure_id in figure_ids:
            if figure_id in expected:
                raise SharedLessonDocumentReadinessError(
                    f"required media figure {figure_id!r} is declared more than once"
                )
            expected[figure_id] = section_id

    supplied: dict[str, FigureMediaResult | DeferredFigureMediaBinding] = {}
    for result in media_results:
        if result.figure_node_id in supplied:
            raise SharedLessonDocumentReadinessError(
                f"required media figure {result.figure_node_id!r} is supplied more than once"
            )
        supplied[result.figure_node_id] = result
        try:
            if isinstance(result, DeferredFigureMediaBinding):
                if not settings.shared_document_media_optional:
                    raise SharedLessonDocumentReadinessError(
                        f"required media figure {result.figure_node_id!r} is deferred, but "
                        "SHARED_DOCUMENT_MEDIA_OPTIONAL is not enabled"
                    )
                verify_bound_deferred_figure_media(result, document)
            else:
                verify_bound_figure_media(result, document)
        except SharedFigureMediaError as exc:
            raise SharedLessonDocumentReadinessError(
                f"media binding for figure {result.figure_node_id!r} is invalid: {exc}"
            ) from exc

    missing = sorted(set(expected) - set(supplied))
    if missing:
        raise SharedLessonDocumentReadinessError(
            f"required media is not ready for figures: {missing!r}"
        )
    unexpected = sorted(set(supplied) - set(expected))
    if unexpected:
        raise SharedLessonDocumentReadinessError(
            f"media supplied for undeclared required figures: {unexpected!r}"
        )
    for figure_id, section_id in expected.items():
        result = supplied[figure_id]
        if result.section_id != section_id or not result.required:
            raise SharedLessonDocumentReadinessError(
                f"required media figure {figure_id!r} has the wrong section or required flag"
            )


def _document_required_media(document: SharedLessonDocument) -> dict[str, tuple[str, ...]]:
    """Derive the required figure identity set from the immutable document."""
    return {
        section.id: tuple(node.id for node in section.nodes if isinstance(node, FigureNode))
        for section in document.sections
        if any(isinstance(node, FigureNode) for node in section.nodes)
    }


def _same_required_media_identity(
    expected: Mapping[str, Sequence[str]], supplied: Mapping[str, Sequence[str]]
) -> bool:
    return {section_id: frozenset(figure_ids) for section_id, figure_ids in expected.items()} == {
        section_id: frozenset(figure_ids) for section_id, figure_ids in supplied.items()
    }


async def promote_shared_lesson_document(
    session: AsyncSession,
    *,
    path_lesson_id: str,
    source: TeachingPlanSource,
    assembly: SharedLessonAssemblyResult,
    semantic_qa: DocumentSemanticQAResult,
    expected_shapes: Mapping[str, Sequence[Any]],
    approved_source_ids: Sequence[str] = (),
    source_facts_by_section: Mapping[str, Sequence[str]] | None = None,
    required_media_by_section: Mapping[str, Sequence[str]] | None = None,
    media_results: Sequence[FigureMediaResult | DeferredFigureMediaBinding] = (),
) -> StoredSharedLessonDocument:
    """Atomically promote one persisted draft after the complete READY gate.

    The caller must provide the exact approved Teaching Plan snapshot and the
    immutable assembly result produced by ``assemble_shared_lesson_document``.
    The final deterministic QA is recomputed here from the approved plan and
    the exact code-owned accepted composition shapes.  The assembly's QA
    result is therefore evidence, never the authority for READY. The supplied
    semantic QA result must be a single-call PASS bound to the exact
    recomputed document. Source identity and content hashes are recomputed
    here. READY is idempotent for the same artifact, while a different artifact
    at the same identity is a hard conflict. This function only flushes;
    transaction ownership stays with the caller.
    """
    if not path_lesson_id:
        raise ValueError("path_lesson_id must not be blank")
    try:
        source_identity = verify_teaching_plan_source(source)
    except SectionRuntimeError as exc:
        raise SharedLessonDocumentReadinessError(
            f"approved Teaching Plan source is invalid: {exc}"
        ) from exc
    if not assembly.ready:
        raise SharedLessonDocumentReadinessError(
            "SharedLessonDocument cannot become ready before final deterministic QA passes"
        )
    try:
        document = assembly.require_ready()
        verify_document_source(
            document,
            teaching_plan_id=source_identity.source_artifact_id,
            teaching_plan_revision=source_identity.source_revision,
            teaching_plan_hash=source_identity.source_hash,
        )
    except (DocumentQAError, ValueError) as exc:
        raise SharedLessonDocumentReadinessError(
            f"assembled SharedLessonDocument source lineage is invalid: {exc}"
        ) from exc

    recomputed_qa = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=tuple(source.plan.sections),
        expected_shapes=expected_shapes,
        expected_title=source.plan.learner_title,
        approved_source_ids=approved_source_ids,
        source_facts_by_section=source_facts_by_section,
        # Figure media has a separate identity gate below.  The media map
        # accepted by assembly may use asset IDs, while the immutable document
        # contains figure node IDs, so feeding it back here would conflate two
        # different identities.
        required_media_by_section={},
        available_media_ids=(),
    )
    if not recomputed_qa.ready:
        raise SharedLessonDocumentReadinessError(
            "recomputed final deterministic QA failed: "
            + "; ".join(issue.issue_code for issue in recomputed_qa.issues)
        )

    if not isinstance(semantic_qa, DocumentSemanticQAResult):
        raise SharedLessonDocumentReadinessError(
            "document semantic QA result must use the closed semantic contract"
        )
    if (
        not semantic_qa.passed
        or semantic_qa.status != "pass"
        or semantic_qa.issues
        or semantic_qa.semantic_calls != 1
        or semantic_qa.deterministic_skipped_semantic
    ):
        raise SharedLessonDocumentReadinessError(
            "document semantic QA must PASS with exactly one semantic call and no issues"
        )
    if (
        semantic_qa.document_id != document.id
        or semantic_qa.document_revision != document.revision
        or semantic_qa.document_hash != shared_lesson_content_hash(document)
        or semantic_qa.document_hash != document.content_hash
    ):
        raise SharedLessonDocumentReadinessError(
            "document semantic QA identity does not match the recomputed document"
        )

    required_media = _document_required_media(document)
    if required_media_by_section is not None and not _same_required_media_identity(
        required_media, required_media_by_section
    ):
        raise SharedLessonDocumentReadinessError(
            "required media declaration does not match the assembled document figures"
        )
    _validate_required_media(
        document=document,
        required_media_by_section=required_media,
        media_results=media_results,
    )

    identity = {"id": document.id, "revision": document.revision}
    row = await session.get(SharedLessonDocumentModel, identity)
    if row is None:
        raise SharedLessonDocumentNotFound(
            "shared document draft must be persisted before READY promotion"
        )
    stored = _validate_stored_row(row, expected_path_lesson_id=path_lesson_id)
    payload = _canonical_json(document)
    if not _same_immutable_identity(
        row,
        path_lesson_id=path_lesson_id,
        document=document,
        payload=payload,
    ):
        raise SharedLessonDocumentConflict(
            "shared document identity is already bound to different content or lineage"
        )
    if stored.status == "ready":
        return stored
    if stored.status != "draft":  # pragma: no cover - closed status check above
        raise SharedLessonDocumentIntegrityError("stored document has an invalid lifecycle status")

    row.status = "ready"
    try:
        await session.flush()
    except IntegrityError as exc:
        raise SharedLessonDocumentIntegrityError(
            "database rejected the SharedLessonDocument READY transition"
        ) from exc
    return _validate_stored_row(row, expected_path_lesson_id=path_lesson_id)


async def load_shared_lesson_document(
    session: AsyncSession,
    *,
    document_id: str,
    revision: int,
    path_lesson_id: str | None = None,
) -> StoredSharedLessonDocument:
    """Load and revalidate a document by immutable identity and revision."""
    row = await session.get(
        SharedLessonDocumentModel,
        {"id": document_id, "revision": revision},
    )
    if row is None or (path_lesson_id is not None and row.path_lesson_id != path_lesson_id):
        raise SharedLessonDocumentNotFound("shared document revision is unavailable")
    return _validate_stored_row(row, expected_path_lesson_id=path_lesson_id)


async def verify_shared_lesson_source(
    session: AsyncSession,
    source: SourceIdentity,
) -> SourceIdentity:
    """Recompute source identity for the generic runtime finalization gate."""
    if source.source_artifact_type != "shared_lesson_document":
        raise SharedLessonDocumentIntegrityError("source is not a shared lesson document")
    stored = await load_shared_lesson_document(
        session,
        document_id=source.source_artifact_id,
        revision=source.source_revision,
    )
    if stored.document.content_hash != source.source_hash:
        raise SharedLessonDocumentConflict("admitted source hash differs from stored document")
    return source


async def load_verified_shared_lesson_artifact(
    session: AsyncSession,
    artifact_type: str,
    artifact_id: str,
    revision: int,
) -> VerifiedArtifact:
    """Load a strict, hash-recomputed artifact for generic run finalization."""
    if artifact_type != "shared_lesson_document":
        raise SharedLessonDocumentIntegrityError("artifact is not a shared lesson document")
    stored = await load_shared_lesson_document(
        session,
        document_id=artifact_id,
        revision=revision,
    )
    if stored.status != "ready":
        raise SharedLessonDocumentIntegrityError(
            "only ready shared lesson documents may be finalized as artifacts"
        )
    payload = _canonical_json(stored.document)
    return VerifiedArtifact(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        revision=revision,
        output_json=payload,
        output_hash=_canonical_bytes(payload),
    )


__all__ = [
    "DocumentStatus",
    "SharedLessonDocumentConflict",
    "SharedLessonDocumentIntegrityError",
    "SharedLessonDocumentNotFound",
    "SharedLessonDocumentReadinessError",
    "SharedLessonDocumentRepositoryError",
    "StoredSharedLessonDocument",
    "load_shared_lesson_document",
    "load_verified_shared_lesson_artifact",
    "promote_shared_lesson_document",
    "save_shared_lesson_document",
    "verify_shared_lesson_source",
]
