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
from contracts.lectio import get_component_registry_entry
from core.database.models import EditableLessonModel, GenerationModel


class ComponentLectioBuilderError(ValueError):
    """Base error for opening a Component Lectio generation in Builder."""


class ComponentLectioBuilderNotReadyError(ComponentLectioBuilderError):
    """The generation has not reached a completed Component Lectio state."""


class ComponentLectioBuilderDocumentError(ComponentLectioBuilderError):
    """The persisted generation document is not a canonical LessonDocument."""


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
        raise ComponentLectioBuilderDocumentError("LessonDocument must be valid JSON") from exc


def _builder_document(document: dict[str, Any], *, lesson_id: str) -> dict[str, Any]:
    normalized = _copy_document(document)
    now = datetime.now(timezone.utc).isoformat()
    normalized["id"] = lesson_id
    normalized["title"] = str(normalized["title"]).strip()
    normalized["created_at"] = now
    normalized["updated_at"] = now
    return normalized


async def _find_component_lesson(
    session: AsyncSession,
    *,
    generation_id: str,
    user_id: str,
) -> EditableLessonModel | None:
    result = await session.execute(
        select(EditableLessonModel).where(
            EditableLessonModel.user_id == user_id,
            EditableLessonModel.source_generation_id == generation_id,
            EditableLessonModel.source_type == "component_lectio",
        )
    )
    return result.scalar_one_or_none()


def _validate_component_generation(generation: GenerationModel, *, user_id: str) -> dict[str, Any]:
    if generation.user_id != user_id:
        raise ComponentLectioBuilderNotReadyError("Generation is not owned by the current user")
    if str(generation.status or "").casefold() != "completed":
        raise ComponentLectioBuilderNotReadyError(
            "Component Lectio generation must be completed before opening Builder"
        )
    if _pipeline_marker(generation) != "component_lectio":
        raise ComponentLectioBuilderNotReadyError(
            "Generation is not marked as a Component Lectio generation"
        )
    if not isinstance(generation.document_json, dict):
        raise ComponentLectioBuilderDocumentError(
            "Completed Component Lectio generation has no LessonDocument"
        )
    document = _copy_document(generation.document_json)
    try:
        assert_valid_lesson_document(document)
    except LessonDocumentValidationError as exc:
        raise ComponentLectioBuilderDocumentError(str(exc)) from exc
    if document.get("source") != "generated":
        raise ComponentLectioBuilderDocumentError(
            "Component Lectio LessonDocument must have source='generated'"
        )
    if document.get("source_generation_id") != generation.id:
        raise ComponentLectioBuilderDocumentError(
            "LessonDocument source_generation_id does not match the generation"
        )
    if document.get("id") != generation.id:
        raise ComponentLectioBuilderDocumentError("LessonDocument id does not match the generation")
    for block_id, block in document["blocks"].items():
        component_id = block.get("component_id")
        if not isinstance(component_id, str) or not component_id.strip():
            raise ComponentLectioBuilderDocumentError(
                f"Missing valid component_id in block '{block_id}'"
            )
        if get_component_registry_entry(component_id) is None:
            raise ComponentLectioBuilderDocumentError(
                f"Unknown component_id in block '{block_id}': {component_id}"
            )
    return document


async def get_or_create_component_lectio_builder_lesson(
    session: AsyncSession,
    *,
    generation: GenerationModel,
    user_id: str,
) -> EditableLessonModel:
    """Open a completed Component Lectio generation in Builder exactly once.

    The operation flushes but does not commit, leaving transaction ownership to
    the caller. A partial unique index plus a savepoint makes concurrent opens
    converge on the same Builder lesson without affecting legacy source types.
    """
    document = _validate_component_generation(generation, user_id=user_id)
    existing = await _find_component_lesson(
        session,
        generation_id=generation.id,
        user_id=user_id,
    )
    if existing is not None:
        return existing

    lesson_id = str(uuid.uuid4())
    lesson = EditableLessonModel(
        id=lesson_id,
        user_id=user_id,
        source_generation_id=generation.id,
        source_type="component_lectio",
        title=str(document["title"]).strip() or "Untitled lesson",
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
        existing = await _find_component_lesson(
            session,
            generation_id=generation.id,
            user_id=user_id,
        )
        if existing is None:
            raise
        return existing
    return lesson


__all__ = [
    "ComponentLectioBuilderDocumentError",
    "ComponentLectioBuilderError",
    "ComponentLectioBuilderNotReadyError",
    "get_or_create_component_lectio_builder_lesson",
]
