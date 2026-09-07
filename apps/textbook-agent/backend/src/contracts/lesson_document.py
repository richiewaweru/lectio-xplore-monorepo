"""Canonical Lectio LessonDocument validation (derived from Lectio 0.6.0 Builder contract)."""

from __future__ import annotations

from typing import Any

REQUIRED_DOCUMENT_FIELDS = (
    "version",
    "id",
    "title",
    "subject",
    "preset_id",
    "source",
    "source_generation_id",
    "sections",
    "blocks",
    "media",
    "created_at",
    "updated_at",
)

REQUIRED_SECTION_FIELDS = (
    "id",
    "template_id",
    "block_ids",
    "title",
    "position",
)

REQUIRED_BLOCK_FIELDS = (
    "id",
    "component_id",
    "content",
    "position",
)

GENERATION_ONLY_FIELDS = frozenset(
    {
        "schema",
        "plan_hash",
        "plan_revision",
        "human_revision",
        "partial",
        "pipeline",
        "status",
    }
)


class LessonDocumentValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_lesson_document(document: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["LessonDocument must be an object"]

    leaked = sorted(key for key in GENERATION_ONLY_FIELDS if key in document)
    if leaked:
        errors.append(f"generation-runtime fields must not appear on LessonDocument: {leaked}")

    for field in REQUIRED_DOCUMENT_FIELDS:
        if field not in document:
            errors.append(f"Missing required field: {field}")

    if document.get("version") != 1:
        errors.append(f"Unsupported document version: {document.get('version')!r}. Expected 1.")

    if not isinstance(document.get("id"), str) or not str(document.get("id")).strip():
        errors.append("id must be a non-empty string")
    if not isinstance(document.get("title"), str):
        errors.append("title must be a string")
    if not isinstance(document.get("subject"), str):
        errors.append("subject must be a string")
    if not isinstance(document.get("preset_id"), str):
        errors.append("preset_id must be a string")
    if document.get("source") not in {"generated", "manual", "imported"} and not isinstance(
        document.get("source"), str
    ):
        errors.append("source must be a string")

    sections = document.get("sections")
    blocks = document.get("blocks")
    media = document.get("media")
    if not isinstance(sections, list):
        errors.append("sections must be an array")
        return errors
    if not isinstance(blocks, dict) or isinstance(blocks, list):
        errors.append("blocks must be an object")
        return errors
    if not isinstance(media, dict) or isinstance(media, list):
        errors.append("media must be an object")

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"sections[{index}] must be an object")
            continue
        for field in REQUIRED_SECTION_FIELDS:
            if field not in section:
                errors.append(f"sections[{index}] missing required field: {field}")
        if not isinstance(section.get("block_ids"), list):
            errors.append(f"sections[{index}].block_ids must be an array")
            continue
        if not isinstance(section.get("template_id"), str) or not section.get("template_id"):
            errors.append(f"sections[{index}].template_id must be a non-empty string")
        if not isinstance(section.get("position"), int):
            errors.append(f"sections[{index}].position must be an integer")
        for block_id in section.get("block_ids") or []:
            if block_id not in blocks:
                errors.append(f"sections[{index}] references missing block id {block_id!r}")

    for block_id, block in blocks.items():
        if not isinstance(block, dict):
            errors.append(f"blocks[{block_id!r}] must be an object")
            continue
        for field in REQUIRED_BLOCK_FIELDS:
            if field not in block:
                errors.append(f"blocks[{block_id!r}] missing required field: {field}")
        if block.get("id") != block_id:
            errors.append(f"blocks[{block_id!r}].id must equal its key")

    return errors


def assert_valid_lesson_document(document: Any) -> dict[str, Any]:
    errors = validate_lesson_document(document)
    if errors:
        raise LessonDocumentValidationError(errors)
    return document
