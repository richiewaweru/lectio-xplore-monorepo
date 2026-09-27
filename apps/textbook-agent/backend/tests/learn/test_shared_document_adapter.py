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
    _learn_config,
    realize_shared_document_for_learn,
)
from learn.runtime.evaluation import evaluate_interaction


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


def _classification_task() -> SharedTaskSpec:
    return SharedTaskSpec(
        id="task-3",
        teaching_plan_id="plan-1",
        teaching_plan_revision=2,
        teaching_plan_hash="b" * 64,
        teaching_block_id="block-3",
        mode="assessment",
        action="classify-items",
        purpose="Classify the examples",
        prompt="Place each example in its group.",
        difficulty="guided",
        expected_evidence="A supported classification",
        response={
            "type": "classification",
            "items": ["a"],
            "categories": ["group"],
            "correct_placements": {"a": "group"},
        },
        evaluation={"type": "mapping", "correct_placements": {"a": "group"}},
    )


def _stored_with_three_anchors(rubric_task: SharedTaskSpec) -> StoredSharedLessonDocument:
    classification = _classification_task()
    stored = _stored(second_task=rubric_task)
    document = stored.document
    sections = list(document.sections)
    sections.append(
        SharedSection(
            id="section-3",
            title="Classify",
            position=2,
            nodes=(
                TaskAnchor(
                    id="anchor-3",
                    task_spec_id=classification.id,
                    teaching_block_id=classification.teaching_block_id,
                ),
            ),
        )
    )
    updated = build_shared_lesson_document(
        {
            **document.model_dump(mode="json"),
            "sections": sections,
            "tasks": [
                *(task.model_dump(mode="json") for task in document.tasks),
                classification.model_dump(mode="json"),
            ],
        }
    )
    return StoredSharedLessonDocument(
        document=updated,
        path_lesson_id=stored.path_lesson_id,
        status="ready",
        storage_hash=content_hash(updated.model_dump(mode="json")),
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


def test_rubric_text_task_maps_to_teacher_review_in_three_anchor_document() -> None:
    unsupported_task = _task(task_id="task-2", response_type="text")
    criteria = ["Uses the relevant evidence", "Explains the reasoning"]
    rubric_task = unsupported_task.model_copy(
        update={"evaluation": {"type": "rubric", "criteria": criteria}}
    )
    stored = _stored_with_three_anchors(rubric_task)
    before = stored.document.model_dump(mode="json")

    result = realize_shared_document_for_learn(
        stored,
        expected_identity=_identity(stored),
        subject="Science",
    )

    assert len(result.document.sections) == 3
    assert [node.kind for node in result.document.nodes].count("interaction") == 3
    rubric_interaction = next(node for node in result.document.nodes if node.id == "anchor-2")
    assert rubric_interaction.interaction_type == "short-response"
    assert rubric_interaction.config == {
        "evaluation": "teacher-review",
        "review_guidance": (
            "Review the learner response against these rubric criteria:\n"
            "- Uses the relevant evidence\n- Explains the reasoning"
        ),
        "rubric_criteria": criteria,
    }
    evaluation = evaluate_interaction(
        {
            "kind": rubric_interaction.interaction_type,
            "config": rubric_interaction.config,
            "feedback": rubric_interaction.feedback,
        },
        {"text": "The learner's response."},
    )
    assert evaluation.outcome == "pending-review"
    assert evaluation.details["mode"] == "teacher-review"
    assert all(criterion in evaluation.details["review_guidance"] for criterion in criteria)
    assert stored.document.model_dump(mode="json") == before
    ordinary = next(node for node in result.document.nodes if node.id == "paragraph-1")
    assert ordinary.text == "Shared authored prose."


def test_rubric_string_is_preserved_verbatim_as_teacher_review_guidance() -> None:
    rubric = "Assess the explanation against the approved evidence and reasoning rubric."
    rubric_task = _task(task_id="task-2", response_type="text").model_copy(
        update={"evaluation": {"type": "rubric", "criteria": rubric}}
    )
    stored = _stored(second_task=rubric_task)

    result = realize_shared_document_for_learn(
        stored,
        expected_identity=_identity(stored),
        subject="Science",
    )
    interaction = next(node for node in result.document.nodes if node.id == "anchor-2")

    assert interaction.config["evaluation"] == "teacher-review"
    assert interaction.config["review_guidance"] == rubric
    assert interaction.config["rubric_criteria"] == rubric
    evaluation = evaluate_interaction(
        {
            "kind": interaction.interaction_type,
            "config": interaction.config,
            "feedback": interaction.feedback,
        },
        {"text": "The learner's response."},
    )
    assert evaluation.outcome == "pending-review"
    assert evaluation.details["review_guidance"] == rubric


@pytest.mark.parametrize("criteria", [[], ["   "], ["valid", 3]])
def test_rubric_text_task_rejects_empty_or_invalid_criteria(criteria) -> None:
    rubric_task = _task(task_id="task-2", response_type="text").model_copy(
        update={"evaluation": {"type": "rubric", "criteria": criteria}}
    )
    with pytest.raises(SharedDocumentLearnMappingError, match="rubric evaluation requires"):
        _learn_config(rubric_task, "short-response")
