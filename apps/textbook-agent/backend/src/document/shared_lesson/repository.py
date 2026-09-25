"""Durable storage and trusted loading for SharedLessonDocument artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import SharedLessonDocument
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
        raise SharedLessonDocumentIntegrityError("stored document JSON failed contract validation") from exc

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
    "SharedLessonDocumentRepositoryError",
    "StoredSharedLessonDocument",
    "load_shared_lesson_document",
    "load_verified_shared_lesson_artifact",
    "save_shared_lesson_document",
    "verify_shared_lesson_source",
]
