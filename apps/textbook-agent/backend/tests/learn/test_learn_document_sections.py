from __future__ import annotations

from learn.contracts.lesson_document import LearnSection, assert_valid_learn_document
from learn.generation.assemble import assemble_learn_document


def test_learn_document_persists_section_metadata() -> None:
    nodes = [
        {"id": "n1", "kind": "paragraph", "text": "Hello", "teaching_block_id": "b1"},
        {"id": "n2", "kind": "paragraph", "text": "Check", "teaching_block_id": "b2"},
    ]
    document = assemble_learn_document(
        nodes,
        {
            "id": "lesson-1",
            "title": "Sections",
            "subject": "Science",
            "source": "generated",
            "sections": [
                {
                    "id": "intro",
                    "title": "Introduce the idea",
                    "position": 0,
                    "transition": None,
                    "node_ids": ["n1"],
                },
                {
                    "id": "check",
                    "title": "Check",
                    "position": 1,
                    "transition": "Now try it",
                    "node_ids": ["n2"],
                },
            ],
        },
    )
    parsed = assert_valid_learn_document(document)
    assert len(parsed.sections) == 2
    assert parsed.sections[0].id == "intro"
    assert parsed.sections[1].node_ids == ["n2"]
    LearnSection.model_validate(document["sections"][0])
