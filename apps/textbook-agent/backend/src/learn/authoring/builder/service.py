"""Reusable persistence operations for Builder-owned generated lessons."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from contracts.lesson_document import LessonDocumentValidationError, assert_valid_lesson_document
from core.database.models import EditableLessonModel, GenerationModel
from learn.contracts.lesson_document import (
    LearnDocumentValidationError,
    assert_valid_learn_document,
    validate_learn_document,
    validate_lesson_document,
)
from learn.generation.pipeline_dispatch import COMPONENT_LECTIO_RETIRED

# Source types for new LearnDocument v2 saves.
DOCUMENT_SOURCE_TYPES = frozenset({"document", "learn_document"})
ACTIVE_BUILDER_SOURCE_TYPES = frozenset(
    {"manual", "template", "document", "learn_document", "native_learn"}
)
_RETIRED_COMPONENT_SOURCE = "component_lectio"


class ComponentLectioBuilderError(ValueError):
    """Retired: Component Lectio Builder open path."""


class ComponentLectioBuilderNotReadyError(ComponentLectioBuilderError):
    """Retired: generation was never a completed Component Lectio state."""


class ComponentLectioBuilderDocumentError(ComponentLectioBuilderError):
    """Retired: Component Lectio LessonDocument open is no longer supported."""


class BuilderDocumentValidationError(ValueError):
    """Builder save rejected an invalid LessonDocument / LearnDocument payload."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        ValueError.__init__(
            self, "; ".join(self.errors) if self.errors else "invalid builder document"
        )


def validate_builder_document(document: Any) -> list[str]:
    """Validate a Builder document payload by version.

    version==2 → LearnDocument (node-centric).
    version==1 → legacy LessonDocument (read/edit until fully migrated).
    """
    if not isinstance(document, dict):
        return ["Document must be an object"]
    version = document.get("version")
    if version == 2:
        return validate_learn_document(document)
    if version == 1:
        return validate_lesson_document(document)
    return [f"Unsupported document version: {version!r}. Expected 1 or 2."]


def assert_valid_builder_document(document: Any) -> dict[str, Any]:
    """Raise BuilderDocumentValidationError when validation fails."""
    if not isinstance(document, dict):
        raise BuilderDocumentValidationError(["Document must be an object"])
    version = document.get("version")
    if version == 2:
        try:
            assert_valid_learn_document(document)
        except LearnDocumentValidationError as exc:
            raise BuilderDocumentValidationError(list(exc.errors)) from exc
        return document
    if version == 1:
        try:
            assert_valid_lesson_document(document)
        except LessonDocumentValidationError as exc:
            raise BuilderDocumentValidationError(list(exc.errors)) from exc
        return document
    raise BuilderDocumentValidationError(
        [f"Unsupported document version: {version!r}. Expected 1 or 2."]
    )


def _pipeline_marker(generation: GenerationModel) -> str | None:
    state = generation.chunked_state_json
    if not isinstance(state, dict):
        return None
    for container_name in ("control", "control_meta"):
        container = state.get(container_name)
        if isinstance(container, dict) and container.get("pipeline"):
            return str(container["pipeline"])
    return None


def _copy_document(document: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(document))
    except (TypeError, ValueError) as exc:
        raise ValueError("Document must be valid JSON") from exc


def _builder_document(document: dict[str, Any], *, lesson_id: str) -> dict[str, Any]:
    normalized = _copy_document(document)
    now = datetime.now(timezone.utc).isoformat()
    normalized["id"] = lesson_id
    if "title" in normalized:
        normalized["title"] = str(normalized["title"]).strip()
    normalized["created_at"] = now
    normalized["updated_at"] = now
    return normalized


async def _find_document_lesson(
    session: AsyncSession,
    *,
    generation_id: str,
    user_id: str,
    source_types: frozenset[str],
) -> EditableLessonModel | None:
    result = await session.execute(
        select(EditableLessonModel).where(
            EditableLessonModel.user_id == user_id,
            EditableLessonModel.source_generation_id == generation_id,
            EditableLessonModel.source_type.in_(source_types),
        )
    )
    return result.scalar_one_or_none()


def _validate_document_generation(generation: GenerationModel, *, user_id: str) -> dict[str, Any]:
    if generation.user_id != user_id:
        raise ValueError("Generation is not owned by the current user")
    if str(generation.status or "").casefold() != "completed":
        raise ValueError("Generation must be completed before opening Builder")
    marker = _pipeline_marker(generation)
    if marker == _RETIRED_COMPONENT_SOURCE:
        raise ComponentLectioBuilderError(COMPONENT_LECTIO_RETIRED)
    if marker not in {"native_learn", "learn_document"} and not (
        isinstance(generation.chunked_state_json, dict)
        and generation.chunked_state_json.get("native_learn")
    ):
        raise ValueError("Generation is not marked as a native Learn document generation")
    if not isinstance(generation.document_json, dict):
        raise ValueError("Completed generation has no document")
    document = _copy_document(generation.document_json)
    version = document.get("version")
    if version == 2:
        try:
            assert_valid_learn_document(document)
        except LearnDocumentValidationError as exc:
            raise ValueError(str(exc)) from exc
    else:
        try:
            assert_valid_lesson_document(document)
        except LessonDocumentValidationError as exc:
            raise ValueError(str(exc)) from exc
    if document.get("source_generation_id") not in {generation.id, None}:
        if document.get("source_generation_id") != generation.id:
            raise ValueError("Document source_generation_id does not match the generation")
    return document


async def get_or_create_native_learn_builder_lesson(
    session: AsyncSession,
    *,
    generation: GenerationModel,
    user_id: str,
) -> EditableLessonModel:
    """Open a completed native Learn / LearnDocument generation in Builder."""
    document = _validate_document_generation(generation, user_id=user_id)
    source_type = "learn_document" if document.get("version") == 2 else "native_learn"
    existing = await _find_document_lesson(
        session,
        generation_id=generation.id,
        user_id=user_id,
        source_types=frozenset({"learn_document", "native_learn", "document"}),
    )
    if existing is not None:
        return existing

    lesson_id = str(uuid.uuid4())
    lesson = EditableLessonModel(
        id=lesson_id,
        user_id=user_id,
        source_generation_id=generation.id,
        source_type=source_type,
        title=str(document.get("title") or "Untitled lesson").strip() or "Untitled lesson",
        class_label=None,
        document_json=_builder_document(document, lesson_id=lesson_id),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    try:
        async with session.begin_nested():
            session.add(lesson)
            await session.flush()
    except IntegrityError:
        existing = await _find_document_lesson(
            session,
            generation_id=generation.id,
            user_id=user_id,
            source_types=frozenset({"learn_document", "native_learn", "document"}),
        )
        if existing is None:
            raise
        return existing
    return lesson


async def get_or_create_component_lectio_builder_lesson(
    session: AsyncSession,
    *,
    generation: GenerationModel,
    user_id: str,
) -> EditableLessonModel:
    """Retired: Component Lectio Builder open always fails."""
    _ = (session, generation, user_id)
    raise ComponentLectioBuilderError(COMPONENT_LECTIO_RETIRED)


__all__ = [
    "ACTIVE_BUILDER_SOURCE_TYPES",
    "BuilderDocumentValidationError",
    "ComponentLectioBuilderDocumentError",
    "ComponentLectioBuilderError",
    "ComponentLectioBuilderNotReadyError",
    "DOCUMENT_SOURCE_TYPES",
    "assert_valid_builder_document",
    "get_or_create_component_lectio_builder_lesson",
    "get_or_create_native_learn_builder_lesson",
    "validate_builder_document",
]
