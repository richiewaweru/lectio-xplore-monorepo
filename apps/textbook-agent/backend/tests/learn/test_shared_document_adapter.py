from __future__ import annotations

from datetime import UTC, datetime

import pytest

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.models import (
    FigureAccessibility,
    FigureDisplay,
    FigureNode,
    HeadingDisplay,
    HeadingNode,
    ParagraphDisplay,
    ParagraphNode,
    SharedSection,
    TaskAnchor,
    build_shared_lesson_document,
)
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    SharedDocumentLearnMappingError,
    realize_shared_document_for_learn,
)


def _task(*, task_id: str = "task-1", response_type: str = "single_choice") -> SharedTaskSpec:
    if response_type == "single_choice":
        action = "select-one"
        response = {
            "type": response_type,
            "options": [
                {"id": "a", "text": "First"},
                {"id": "b", "text": "Second"},
            ],
        }
        evaluation = {"type": "exact_match", "correct_option_id": "b"}
    else:
        action = "enter-text"
        response = {"type": "text", "min_length": 1}
        evaluation = {"type": "rubric", "criteria": ["Explains the evidence"]}
    return SharedTaskSpec(
        id=task_id,
        teaching_plan_id="plan-1",
        teaching_plan_revision=2,
        teaching_plan_hash="b" * 64,
        teaching_block_id=task_id.replace("task", "block"),
        mode="assessment",
        action=action,
        purpose="Check understanding",
        prompt="Which option is supported?",
        difficulty="guided",
        expected_evidence="Select the supported option",
        response=response,
        evaluation=evaluation,
    )


def _stored(*, second_task: SharedTaskSpec | None = None) -> StoredSharedLessonDocument:
    task = _task()
    first_nodes = [
        ParagraphNode(
            id="paragraph-1",
            teaching_block_id="block-1",
            display=ParagraphDisplay(text="Shared authored prose."),
        ),
        TaskAnchor(
            id="anchor-1",
            task_spec_id=task.id,
            teaching_block_id=task.teaching_block_id,
        ),
        FigureNode(
            id="figure-1",
            teaching_block_id="block-1",
            display=FigureDisplay(asset_id="asset-1", caption="A figure"),
            accessibility=FigureAccessibility(alt_text="A labeled diagram"),
        ),
    ]
    sections = [
        SharedSection(id="section-1", title="First section", position=0, nodes=tuple(first_nodes))
    ]
    tasks = [task]
    if second_task is not None:
        sections.append(
            SharedSection(
                id="section-2",
                title="Second section",
                position=1,
                nodes=(
                    HeadingNode(
                        id="heading-2",
                        teaching_block_id=second_task.teaching_block_id,
                        display=HeadingDisplay(text="Second task"),
                    ),
                    TaskAnchor(
                        id="anchor-2",
                        task_spec_id=second_task.id,
                        teaching_block_id=second_task.teaching_block_id,
                    ),
                ),
            )
        )
        tasks.append(second_task)
    document = build_shared_lesson_document(
        {
            "id": "shared-1",
            "revision": 4,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 2,
            "teaching_plan_hash": "b" * 64,
            "title": "A shared lesson",
            "sections": sections,
            "tasks": [task.model_dump(mode="json") for task in tasks],
            "created_at": datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        }
    )
    return StoredSharedLessonDocument(
        document=document,
        path_lesson_id="path-lesson-1",
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )


def _identity(stored: StoredSharedLessonDocument) -> SharedDocumentIdentity:
    document = stored.document
    return SharedDocumentIdentity(
        id=document.id,
        revision=document.revision,
        content_hash=document.content_hash,
    )


def test_adapter_copies_ordered_shared_nodes_and_maps_anchor_to_learn_interaction() -> None:
    stored = _stored()

    result = realize_shared_document_for_learn(
        stored,
        expected_identity=_identity(stored),
        subject="Science",
        source_generation_id="prep-1",
    )

    assert result.source_identity == _identity(stored)
    assert [node.id for node in result.document.nodes] == [
        "paragraph-1",
        "anchor-1",
        "figure-1",
    ]
    paragraph, interaction, figure = result.document.nodes
    assert paragraph.text == "Shared authored prose."
    assert interaction.kind == "interaction"
    assert interaction.interaction_type == "choice"
    assert interaction.teaching_block_id == "block-1"
    assert interaction.prompt == "Which option is supported?"
    assert interaction.config == {
        "options": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}],
        "correct_option_id": "b",
    }
    assert interaction.assessment_mode == "graded"
    assert interaction.feedback == {"correct": "Correct.", "incorrect": "Not yet — try again."}
    assert interaction.attempt_policy["show_feedback_after_submit"] is True
    assert interaction.contract["shared_task"]["expected_evidence"] == (
        "Select the supported option"
    )
    assert "feedback" not in interaction.contract["shared_task"]
    assert figure.asset_id == "asset-1"
    assert figure.alt == "A labeled diagram"
    assert result.document.sections[0].node_ids == ["paragraph-1", "anchor-1", "figure-1"]


@pytest.mark.parametrize(
    "identity",
    [
        SharedDocumentIdentity(id="wrong", revision=4, content_hash="0" * 64),
        SharedDocumentIdentity(id="shared-1", revision=5, content_hash="0" * 64),
    ],
)
def test_adapter_rejects_wrong_document_identity(identity: SharedDocumentIdentity) -> None:
    stored = _stored()

    with pytest.raises(SharedDocumentLearnMappingError, match="differs from Learn admission"):
        realize_shared_document_for_learn(
            stored,
            expected_identity=identity,
            subject="Science",
        )


def test_adapter_rejects_stale_recomputed_content_hash() -> None:
    stored = _stored()
    tampered_document = stored.document.model_copy(update={"content_hash": "0" * 64})
    tampered = StoredSharedLessonDocument(
        document=tampered_document,
        path_lesson_id=stored.path_lesson_id,
        status="ready",
        storage_hash=content_hash(tampered_document.model_dump(mode="json")),
    )

    with pytest.raises(SharedDocumentLearnMappingError, match="content hash is stale"):
        realize_shared_document_for_learn(
            tampered,
            expected_identity=_identity(stored),
            subject="Science",
        )


def test_unsupported_task_in_one_section_does_not_mutate_or_rewrite_sibling() -> None:
    unsupported_task = _task(task_id="task-2", response_type="text")
    stored = _stored(second_task=unsupported_task)
    before = stored.document.model_dump(mode="json")

    with pytest.raises(SharedDocumentLearnMappingError, match="evaluation is not supported"):
        realize_shared_document_for_learn(
            stored,
            expected_identity=_identity(stored),
            subject="Science",
        )

    assert stored.document.model_dump(mode="json") == before
    assert stored.document.sections[0].nodes[0].display.text == "Shared authored prose."
    assert stored.document.sections[0].nodes[1].task_spec_id == "task-1"
