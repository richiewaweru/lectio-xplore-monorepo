"""Unit tests for the shared document vocabulary (Phase B)."""

from __future__ import annotations

import pytest

from document.models import DOCUMENT_PRIMITIVE_KINDS, CalloutNode, HeadingNode, ParagraphNode
from document.validation import DocumentValidationError, validate_document_nodes


def test_all_six_primitives_round_trip() -> None:
    nodes = validate_document_nodes(
        [
            {"id": "h1", "kind": "heading", "text": "Title", "level": 1},
            {"id": "p1", "kind": "paragraph", "text": "Body prose."},
            {"id": "l1", "kind": "list", "ordered": True, "items": ["a", "b"]},
            {"id": "f1", "kind": "figure", "caption": "A diagram", "alt": "diagram"},
            {
                "id": "t1",
                "kind": "table",
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
            },
            {"id": "c1", "kind": "callout", "tone": "warning", "body": "Watch out."},
        ]
    )
    assert len(nodes) == 6
    assert {n.kind for n in nodes} == DOCUMENT_PRIMITIVE_KINDS
    assert isinstance(nodes[0], HeadingNode)
    assert isinstance(nodes[1], ParagraphNode)
    assert isinstance(nodes[5], CalloutNode)


def test_rejects_component_and_pagination_fields() -> None:
    with pytest.raises(DocumentValidationError) as exc:
        validate_document_nodes(
            [{"id": "p1", "kind": "paragraph", "text": "x", "component_id": "ExplanationBlock"}]
        )
    assert "forbidden" in str(exc.value)


def test_rejects_unknown_kind() -> None:
    with pytest.raises(DocumentValidationError) as exc:
        validate_document_nodes([{"id": "x", "kind": "explanation-block", "text": "no"}])
    assert "not a document primitive" in str(exc.value)


def test_new_intent_does_not_require_new_node_class() -> None:
    """Any teaching intent can be realized with existing primitives."""
    nodes = validate_document_nodes(
        [
            {"id": "n1", "kind": "paragraph", "text": "Define X.", "teaching_block_id": "b1"},
            {"id": "n2", "kind": "callout", "body": "Common pitfall.", "teaching_block_id": "b2"},
        ]
    )
    assert [n.teaching_block_id for n in nodes] == ["b1", "b2"]
