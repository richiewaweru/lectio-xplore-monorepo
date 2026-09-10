"""Builder accepts LearnDocument version 2 on save."""

from __future__ import annotations

from learn.authoring.builder.service import (
    ACTIVE_BUILDER_SOURCE_TYPES,
    DOCUMENT_SOURCE_TYPES,
    BuilderDocumentValidationError,
    assert_valid_builder_document,
    validate_builder_document,
)


def _learn_document_v2(**overrides: object) -> dict:
    document: dict = {
        "version": 2,
        "id": "lesson-v2",
        "title": "Evaporation",
        "subject": "science",
        "source": "manual",
        "source_generation_id": None,
        "nodes": [
            {
                "id": "h1",
                "kind": "heading",
                "text": "Evaporation",
                "level": 1,
            },
            {
                "id": "p1",
                "kind": "paragraph",
                "text": "Liquid water becomes vapour.",
            },
        ],
        "created_at": "2026-09-10T00:00:00Z",
        "updated_at": "2026-09-10T00:00:00Z",
    }
    document.update(overrides)
    return document


def test_validate_builder_document_accepts_v2() -> None:
    errors = validate_builder_document(_learn_document_v2())
    assert errors == []
    parsed = assert_valid_builder_document(_learn_document_v2())
    assert parsed["version"] == 2
    assert len(parsed["nodes"]) == 2


def test_validate_builder_document_rejects_component_fields_on_v2() -> None:
    bad = _learn_document_v2(
        nodes=[
            {
                "id": "p1",
                "kind": "paragraph",
                "text": "Hello",
                "component_id": "explanation-block",
            }
        ]
    )
    errors = validate_builder_document(bad)
    assert errors
    assert any("forbidden" in e or "component_id" in e for e in errors)


def test_validate_builder_document_still_accepts_v1_shape() -> None:
    v1 = {
        "version": 1,
        "id": "lesson-v1",
        "title": "Fractions",
        "subject": "mathematics",
        "preset_id": "blue-classroom",
        "source": "manual",
        "source_generation_id": None,
        "sections": [
            {
                "id": "section-1",
                "template_id": "open-canvas",
                "title": "Fractions",
                "position": 0,
                "block_ids": ["block-1"],
            }
        ],
        "blocks": {
            "block-1": {
                "id": "block-1",
                "component_id": "explanation-block",
                "position": 0,
                "content": {"body": "A fraction is part of a whole."},
            }
        },
        "media": {},
        "created_at": "2026-09-10T00:00:00Z",
        "updated_at": "2026-09-10T00:00:00Z",
    }
    assert validate_builder_document(v1) == []


def test_document_source_types_do_not_require_component_lectio() -> None:
    assert "document" in DOCUMENT_SOURCE_TYPES
    assert "learn_document" in DOCUMENT_SOURCE_TYPES
    assert "component_lectio" not in DOCUMENT_SOURCE_TYPES
    assert DOCUMENT_SOURCE_TYPES <= ACTIVE_BUILDER_SOURCE_TYPES


def test_assert_valid_builder_document_raises_on_bad_version() -> None:
    try:
        assert_valid_builder_document({"version": 9, "id": "x"})
        raise AssertionError("expected BuilderDocumentValidationError")
    except BuilderDocumentValidationError as exc:
        assert any("Unsupported document version" in e for e in exc.errors)


def test_publish_validation_accepts_learn_document_v2() -> None:
    from learn.publishing.publish_validation import (
        collect_publish_validation_errors,
        validate_publishable_lesson_document,
    )

    document = _learn_document_v2()
    assert collect_publish_validation_errors(document) == []
    validate_publishable_lesson_document(document)
