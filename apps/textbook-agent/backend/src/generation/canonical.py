"""Pipeline-neutral projections for the live Component Lectio generation path.

This module deliberately has no dependency on the retired Studio router or its
session/writer implementation.  A generation is visible through the canonical
surfaces only when its persisted pipeline identity explicitly says
``component_lectio``.  Missing markers are not inferred and therefore cannot
accidentally expose historical Studio rows after cutover.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from contracts.document import PipelineDocument, PipelineSectionManifestItem
from contracts.lesson_document import LessonDocumentValidationError, assert_valid_lesson_document
from core.database.models import EditableLessonModel, GenerationModel

CANONICAL_PIPELINE = "component_lectio"


def _state(generation: GenerationModel) -> dict[str, Any]:
    value = generation.chunked_state_json
    return value if isinstance(value, dict) else {}


def pipeline_marker(generation: GenerationModel) -> str | None:
    """Return the explicit persisted pipeline marker, without inference."""

    state = _state(generation)
    for container_name in ("control", "control_meta"):
        container = state.get(container_name)
        if isinstance(container, dict):
            value = container.get("pipeline")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def is_canonical_generation(generation: GenerationModel) -> bool:
    return pipeline_marker(generation) == CANONICAL_PIPELINE


def canonical_stage(generation: GenerationModel) -> str:
    """Project storage state into one stable status vocabulary for consumers."""

    state = _state(generation)
    stage = state.get("stage")
    if isinstance(stage, str) and stage.strip():
        return stage.strip()
    status = str(generation.status or "pending").strip().lower()
    return {
        "completed": "complete",
        "partial": "partial",
        "failed": "failed",
        "running": "component_lectio_running",
    }.get(status, status or "pending")


def canonical_document(generation: GenerationModel) -> dict[str, Any] | None:
    """Return a validated detached LessonDocument, or ``None`` while pending."""

    if not is_canonical_generation(generation) or not isinstance(generation.document_json, dict):
        return None
    document = copy.deepcopy(generation.document_json)
    try:
        assert_valid_lesson_document(document)
    except LessonDocumentValidationError:
        return None
    if document.get("id") != generation.id:
        return None
    if document.get("source_generation_id") != generation.id:
        return None
    return document


def canonical_marker_clause():
    # JSON path access is supported by both PostgreSQL JSONB and the SQLite
    # test database.  Explicit markers are required in either control field;
    # there is intentionally no "missing marker means legacy" fallback here.
    return or_(
        GenerationModel.chunked_state_json["control"]["pipeline"].as_string()
        == CANONICAL_PIPELINE,
        GenerationModel.chunked_state_json["control_meta"]["pipeline"].as_string()
        == CANONICAL_PIPELINE,
    )


async def get_owned_canonical_generation(
    session: AsyncSession,
    *,
    generation_id: str,
    user_id: str,
) -> GenerationModel | None:
    result = await session.execute(
        select(GenerationModel).where(
            GenerationModel.id == generation_id,
            GenerationModel.user_id == user_id,
            canonical_marker_clause(),
        )
    )
    return result.scalar_one_or_none()


async def list_owned_canonical_generations(
    session: AsyncSession,
    *,
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> list[GenerationModel]:
    result = await session.execute(
        select(GenerationModel)
        .where(GenerationModel.user_id == user_id, canonical_marker_clause())
        .order_by(GenerationModel.created_at.desc(), GenerationModel.id.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 100))
    )
    return list(result.scalars().all())


class CanonicalGenerationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_id: str
    pipeline: str = CANONICAL_PIPELINE
    subject: str
    context: str = ""
    mode: str
    status: str
    stage: str
    document_present: bool
    quality_passed: bool | None = None
    error: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    pack_id: str | None = None
    pack_resource_id: str | None = None
    pack_resource_label: str | None = None
    builder_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    last_heartbeat: datetime | None = None


def summary_from_generation(
    generation: GenerationModel,
    *,
    builder_id: str | None = None,
) -> CanonicalGenerationSummary:
    return CanonicalGenerationSummary(
        generation_id=generation.id,
        subject=generation.subject,
        context=generation.context or "",
        mode=generation.mode or "balanced",
        status=generation.status or "pending",
        stage=canonical_stage(generation),
        document_present=canonical_document(generation) is not None,
        quality_passed=generation.quality_passed,
        error=generation.error,
        error_type=generation.error_type,
        error_code=generation.error_code,
        pack_id=generation.pack_id,
        pack_resource_id=generation.pack_resource_id,
        pack_resource_label=generation.pack_resource_label,
        builder_id=builder_id
        or (_state(generation).get("builder_id") if isinstance(_state(generation).get("builder_id"), str) else None),
        created_at=generation.created_at,
        completed_at=generation.completed_at,
        last_heartbeat=generation.last_heartbeat,
    )


async def builder_id_for_generation(
    session: AsyncSession,
    *,
    generation_id: str,
    user_id: str,
) -> str | None:
    return await session.scalar(
        select(EditableLessonModel.id).where(
            EditableLessonModel.user_id == user_id,
            EditableLessonModel.source_generation_id == generation_id,
            EditableLessonModel.source_type == CANONICAL_PIPELINE,
        )
    )


def build_pipeline_document_for_lesson_document(
    *,
    generation: GenerationModel,
    document: dict[str, Any] | None = None,
) -> PipelineDocument:
    """Adapt canonical metadata for the shared PDF assembly service.

    The print renderer reads the canonical LessonDocument itself.  The
    PipelineDocument here supplies only the stable metadata/TOC projection and
    intentionally does not reinterpret or mutate block content.
    """

    canonical = document or canonical_document(generation)
    if canonical is None:
        raise ValueError("Generation does not contain a canonical LessonDocument")
    sections = canonical.get("sections", [])
    manifest: list[PipelineSectionManifestItem] = []
    template_id = "open-canvas"
    if isinstance(sections, list):
        for index, raw in enumerate(sections, start=1):
            if not isinstance(raw, dict):
                continue
            if not manifest and isinstance(raw.get("template_id"), str) and raw["template_id"]:
                template_id = raw["template_id"]
            section_id = raw.get("id")
            title = raw.get("title")
            position = raw.get("position")
            manifest.append(
                PipelineSectionManifestItem(
                    section_id=section_id if isinstance(section_id, str) and section_id else f"section-{index}",
                    title=title if isinstance(title, str) and title else f"Section {index}",
                    position=position if isinstance(position, int) else index,
                )
            )
    return PipelineDocument(
        generation_id=generation.id,
        subject=str(canonical.get("title") or generation.subject or "Lesson"),
        context=str(canonical.get("subject") or generation.context or ""),
        mode="component_lectio",
        template_id=template_id,
        preset_id=str(canonical.get("preset_id") or generation.resolved_preset_id or "blue-classroom"),
        status="completed" if str(generation.status).lower() == "completed" else "pending",
        section_manifest=manifest,
        sections=[],
        quality_passed=generation.quality_passed,
        error=generation.error,
        created_at=generation.created_at,
        updated_at=generation.completed_at or generation.created_at,
        completed_at=generation.completed_at,
    )


__all__ = [
    "CANONICAL_PIPELINE",
    "CanonicalGenerationSummary",
    "build_pipeline_document_for_lesson_document",
    "builder_id_for_generation",
    "canonical_document",
    "canonical_marker_clause",
    "canonical_stage",
    "get_owned_canonical_generation",
    "is_canonical_generation",
    "list_owned_canonical_generations",
    "pipeline_marker",
    "summary_from_generation",
]
