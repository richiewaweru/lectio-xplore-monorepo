from __future__ import annotations

from learn.contracts.lesson_document import LearnSection, assert_valid_learn_document
from learn.generation.assemble import assemble_learn_document
from learn.generation.native_production import _realized_sections
from print.generation.whole_lesson.teaching_plan import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)


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


def test_realized_sections_group_nodes_without_reopening_plan() -> None:
    plan = TeachingPlan(
        arc="Arc",
        teaching_plan_id="tp-1",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                specific_purpose="Explain light",
                blocks=[
                    TeachingPlanBlock(
                        id="b1",
                        position=0,
                        intent="explain",
                        brief="Light",
                        evidence="The cause is named",
                    )
                ],
            ),
            TeachingPlanSection(
                slot_id="s2",
                specific_purpose="Check",
                transition="Now apply it",
                blocks=[
                    TeachingPlanBlock(
                        id="b2",
                        position=1,
                        intent="check-understanding",
                        brief="Choose",
                        evidence="Learner chooses",
                    )
                ],
            ),
        ],
    )
    nodes = [
        {"id": "n-a", "teaching_block_id": "b1"},
        {"id": "n-b", "teaching_block_id": "b2"},
    ]
    sections = _realized_sections(plan, nodes)
    assert [item["id"] for item in sections] == ["s1", "s2"]
    assert sections[0]["node_ids"] == ["n-a"]
    assert sections[1]["node_ids"] == ["n-b"]
    assert sections[1]["transition"] == "Now apply it"
