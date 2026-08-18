"""Typed form content model validation for all 8 generated forms."""

from __future__ import annotations

import pytest

from generation.page_objects import (
    FORM_OUTPUTS,
    WRITER_PROVIDER_OUTPUTS,
    GENERATED_FORM_IDS,
    ContentValidationError,
    UnsupportedObject,
    validate_content,
)


VALID_FIXTURES: dict[str, dict] = {
    "prose": {"paragraphs": ["Light supplies energy for food making."]},
    "list": {
        "style": "steps",
        "lead_in": "Sequence:",
        "items": [{"text": "Light reaches the leaf."}, {"text": "Food is made."}],
    },
    "table": {
        "columns": [{"id": "part", "label": "Part"}, {"id": "light", "label": "Light"}],
        "rows": [{"cells": {"part": "Lit", "light": "Yes"}}],
        "caption": "Comparison",
        "presentation": "comparison",
    },
    "figure": {
        "asset": {"kind": "image", "status": "pending", "request_id": "fig-1"},
        "alt_text": "Diagram of a lit and covered leaf",
        "caption": "Leaf comparison",
        "width": "span",
    },
    "aside": {"label": "Note", "body": "Soil is not food."},
    "worked-example": {
        "problem": "Why does the covered part lack evidence?",
        "steps": [{"text": "Identify the changed condition."}],
        "answer": "No light reached that part.",
        "title": "Reasoning",
    },
    "questions": {
        "instructions": "Answer briefly.",
        "items": [{"id": "q1", "prompt": "Why cover the leaf?", "marks": 2, "answer_lines": 3}],
    },
    "choices": {
        "stem": "What does soil supply?",
        "options": [
            {"letter": "A", "text": "Food"},
            {"letter": "B", "text": "Water and minerals"},
        ],
        "marks": 1,
    },
}


INVALID_FIXTURES: dict[str, dict] = {
    "prose": {"paragraphs": []},
    "list": {"style": "unordered", "items": []},
    "table": {"columns": [], "rows": []},
    "figure": {"asset": {"status": "pending"}, "caption": "missing alt"},
    "aside": {"label": "Note"},
    "worked-example": {"problem": "x", "steps": [], "answer": "y"},
    "questions": {"items": [{"id": "q1", "prompt": "Why?", "correct_key": "A"}]},
    "choices": {"stem": "Which?", "options": [{"letter": "A", "text": "Only one"}]},
}


def test_generated_form_ids_cover_eight_forms() -> None:
    assert set(GENERATED_FORM_IDS) == set(FORM_OUTPUTS)
    assert len(GENERATED_FORM_IDS) == 8


@pytest.mark.parametrize("object_id", list(GENERATED_FORM_IDS))
def test_valid_content_for_each_form(object_id: str) -> None:
    dumped = validate_content(object_id, VALID_FIXTURES[object_id])
    assert isinstance(dumped, dict)
    # Round-trip through the model again.
    validate_content(object_id, dumped)


def test_table_provider_cells_use_strict_entries_but_normalize_to_map() -> None:
    from generation.page_objects.models import TableContent

    content = TableContent.model_validate(
        {
            "columns": [{"id": "part", "label": "Part"}],
            "rows": [{"cells": [{"column_id": "part", "value": "Leaf"}]}],
        }
    )

    assert content.rows[0].cells == {"part": "Leaf"}
    schema = TableContent.model_json_schema()
    assert schema["$defs"]["TableRow"]["properties"]["cells"]["type"] == "array"


@pytest.mark.parametrize("object_id", list(GENERATED_FORM_IDS))
def test_invalid_content_rejected(object_id: str) -> None:
    with pytest.raises(ContentValidationError) as exc:
        validate_content(object_id, INVALID_FIXTURES[object_id])
    assert exc.value.object_id == object_id
    assert exc.value.errors
    assert all("path" in err and "message" in err for err in exc.value.errors)


def test_unknown_form_raises_unsupported() -> None:
    with pytest.raises(UnsupportedObject):
        validate_content("heading", {"level": 1, "text": "Hi"})


def test_extra_fields_forbidden_on_questions() -> None:
    with pytest.raises(ContentValidationError) as exc:
        validate_content(
            "questions",
            {
                "items": [
                    {
                        "id": "q1",
                        "prompt": "Why?",
                        "options": [{"letter": "A", "text": "x"}],
                    }
                ]
            },
        )
    paths = " ".join(err["path"] for err in exc.value.errors)
    assert "options" in paths or "extra" in str(exc.value).lower()
