"""Map Print catalogue objects ↔ shared document primitives (Phase C)."""

from __future__ import annotations

from typing import Literal

DocumentPrimitiveKind = Literal[
    "paragraph", "heading", "list", "figure", "table", "callout"
]

# Ordinary Print forms that are really document-primitive decisions.
PRINT_OBJECT_TO_PRIMITIVE: dict[str, DocumentPrimitiveKind] = {
    "prose": "paragraph",
    "heading": "heading",
    "list": "list",
    "figure": "figure",
    "table": "table",
    "aside": "callout",
}

PRIMITIVE_TO_PRINT_OBJECT: dict[DocumentPrimitiveKind, str] = {
    "paragraph": "prose",
    "heading": "prose",
    "list": "list",
    "figure": "figure",
    "table": "table",
    "callout": "aside",
}

# Paper-only / task treatments — not shared document primitives.
PRINT_ONLY_OBJECTS = frozenset(
    {"worked-example", "questions", "choices", "answer-key"}
)

# Print-only layout/response surfaces that must never appear on Learn plans.
PRINT_ONLY_LAYOUT_OBJECTS: frozenset[str] = frozenset(
    {"ruled_lines", "page_break", "answer-key", "working-space"}
)


def is_ordinary_document_object(object_id: str) -> bool:
    return object_id in PRINT_OBJECT_TO_PRIMITIVE


def to_document_primitive(object_id: str) -> DocumentPrimitiveKind | None:
    return PRINT_OBJECT_TO_PRIMITIVE.get(object_id)


def to_print_object(kind: DocumentPrimitiveKind) -> str:
    return PRIMITIVE_TO_PRINT_OBJECT[kind]
