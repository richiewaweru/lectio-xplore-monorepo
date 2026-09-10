"""Unit tests for Print catalogue ↔ document primitive mapping (Phase C/E)."""

from __future__ import annotations

from document.models import DOCUMENT_PRIMITIVE_KINDS
from print.generation.document_form_map import (
    PRINT_OBJECT_TO_PRIMITIVE,
    PRINT_ONLY_OBJECTS,
    PRIMITIVE_TO_PRINT_OBJECT,
    is_ordinary_document_object,
    to_document_primitive,
    to_print_object,
)


def test_ordinary_print_objects_map_to_six_primitives() -> None:
    assert set(PRINT_OBJECT_TO_PRIMITIVE.values()) == DOCUMENT_PRIMITIVE_KINDS
    assert set(PRIMITIVE_TO_PRINT_OBJECT.keys()) == DOCUMENT_PRIMITIVE_KINDS
    assert to_document_primitive("prose") == "paragraph"
    assert to_document_primitive("aside") == "callout"
    assert to_print_object("paragraph") == "prose"
    assert to_print_object("callout") == "aside"
    assert is_ordinary_document_object("table")
    assert not is_ordinary_document_object("questions")


def test_print_only_objects_are_not_primitives() -> None:
    for object_id in PRINT_ONLY_OBJECTS:
        assert to_document_primitive(object_id) is None
        assert not is_ordinary_document_object(object_id)
