"""LearnDocument v2 contract and assembly."""

from __future__ import annotations

from learn.contracts.lesson_document import (
    LearnDocumentValidationError,
    assert_valid_learn_document,
    validate_learn_document,
)
from learn.generation.assemble import assemble_learn_document


def test_passive_mixed_nodes_validate() -> None:
    document = assemble_learn_document(
        [
            {
                "id": "h1",
                "kind": "heading",
                "text": "Evaporation",
                "level": 1,
                "teaching_block_id": "b1",
            },
            {
                "id": "p1",
                "kind": "paragraph",
                "text": "Liquid water becomes vapour.",
                "teaching_block_id": "b1",
            },
            {
                "id": "l1",
                "kind": "list",
                "ordered": True,
                "items": ["Heat the surface.", "Molecules escape."],
                "teaching_block_id": "b2",
            },
            {
                "id": "c1",
                "kind": "callout",
                "tone": "tip",
                "body": "Watch puddles on warm days.",
                "teaching_block_id": "b2",
            },
        ],
        {
            "id": "lesson-passive",
            "title": "Evaporation",
            "subject": "science",
            "source": "generated",
            "source_generation_id": "gen-1",
            "teaching_plan_id": "tp-1",
            "teaching_plan_revision": 1,
        },
    )
    assert document["version"] == 2
    assert validate_learn_document(document) == []
    parsed = assert_valid_learn_document(document)
    assert [n.kind for n in parsed.nodes] == ["heading", "paragraph", "list", "callout"]
    assert [getattr(n, "teaching_block_id", None) for n in parsed.nodes] == [
        "b1",
        "b1",
        "b2",
        "b2",
    ]


def test_interaction_node_validates() -> None:
    document = assemble_learn_document(
        [
            {
                "id": "p1",
                "kind": "paragraph",
                "text": "Choose the best description.",
                "teaching_block_id": "b1",
            },
            {
                "id": "ix1",
                "kind": "interaction",
                "interaction_type": "choice",
                "teaching_block_id": "b1",
                "prompt": "What is evaporation?",
                "config": {
                    "options": [
                        {"id": "a", "text": "Liquid to solid"},
                        {"id": "b", "text": "Liquid to vapour"},
                    ],
                    "correct_option_id": "b",
                },
                "feedback": {"correct": "Yes.", "incorrect": "Try again."},
            },
        ],
        {"title": "Check", "subject": "science", "source": "manual"},
    )
    assert validate_learn_document(document) == []
    kinds = [n["kind"] for n in document["nodes"]]
    assert kinds == ["paragraph", "interaction"]
    assert document["nodes"][1]["interaction_type"] == "choice"
    assert "component_id" not in document["nodes"][1]
    assert "template_id" not in document["nodes"][1]


def test_rejects_component_id_on_document_primitives() -> None:
    errors = validate_learn_document(
        {
            "version": 2,
            "id": "bad",
            "title": "Bad",
            "subject": "science",
            "source": "generated",
            "source_generation_id": None,
            "nodes": [
                {
                    "id": "p1",
                    "kind": "paragraph",
                    "text": "x",
                    "component_id": "explanation-block",
                }
            ],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "teaching_plan_id": None,
            "teaching_plan_revision": None,
        }
    )
    assert errors
    assert any("forbidden" in err for err in errors)
    try:
        assert_valid_learn_document(
            {
                "version": 2,
                "id": "bad2",
                "title": "Bad",
                "subject": "science",
                "source": "generated",
                "nodes": [
                    {
                        "id": "p1",
                        "kind": "paragraph",
                        "text": "x",
                        "template_id": "open-canvas",
                    }
                ],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )
        raise AssertionError("expected LearnDocumentValidationError")
    except LearnDocumentValidationError as exc:
        assert any("forbidden" in err for err in exc.errors)
