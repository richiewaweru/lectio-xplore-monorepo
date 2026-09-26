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
from print.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    SharedDocumentPrintMappingError,
    realize_shared_document_for_print,
)


def _task() -> SharedTaskSpec:
    return SharedTaskSpec(
        id="task-secret-123",
        teaching_plan_id="plan-1",
        teaching_plan_revision=2,
        teaching_plan_hash="b" * 64,
        teaching_block_id="block-1",
        mode="assessment",
        action="select-one",
        purpose="Check understanding",
        prompt="Which option is supported?",
        difficulty="guided",
        expected_evidence="Select the supported option",
        response={
            "type": "single_choice",
            "options": [{"id": "internal-a", "text": "First"}, {"id": "internal-b", "text": "Second"}],
        },
        evaluation={"type": "exact_match", "correct_option_id": "internal-b"},
    )


def _stored(*, include_figure: bool = False) -> StoredSharedLessonDocument:
    task = _task()
    nodes = [
        ParagraphNode(
            id="paragraph-1",
            teaching_block_id="block-1",
            display=ParagraphDisplay(text="Shared authored prose."),
        ),
        HeadingNode(
            id="heading-1",
            teaching_block_id="block-1",
            display=HeadingDisplay(text="Shared subsection", level=3),
        ),
        TaskAnchor(id="anchor-secret-456", task_spec_id=task.id, teaching_block_id="block-1"),
    ]
    if include_figure:
        nodes.append(
            FigureNode(
                id="figure-1",
                teaching_block_id="block-1",
                display=FigureDisplay(caption="A figure"),
                accessibility=FigureAccessibility(alt_text="A labeled diagram"),
            )
        )
    document = build_shared_lesson_document(
        {
            "id": "shared-1",
            "revision": 4,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 2,
            "teaching_plan_hash": "b" * 64,
            "title": "A shared lesson",
            "sections": [
                SharedSection(id="section-1", title="First section", position=0, nodes=tuple(nodes))
            ],
            "tasks": [task.model_dump(mode="json")],
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
    doc = stored.document
    return SharedDocumentIdentity(doc.id, doc.revision, doc.content_hash)


def test_print_adapter_verifies_source_and_maps_heading_hierarchy_and_task_labels() -> None:
    stored = _stored()

    result = realize_shared_document_for_print(stored, expected_identity=_identity(stored))

    section = result.document["sections"][0]
    assert section["title"] == "First section"
    assert [block["object"] for block in section["blocks"]] == ["prose", "heading", "choices"]
    assert section["blocks"][1]["content"] == {"text": "Shared subsection", "level": 3}
    choice = section["blocks"][2]
    assert choice["content"]["options"] == [
        {"letter": "A", "text": "First"},
        {"letter": "B", "text": "Second"},
    ]
    assert result.document["answer_key"]["content"]["groups"][0]["entries"] == [
        {"question_id": "Choice-1", "answer": "B"}
    ]
    metadata = result.document["metadata"]["shared_tasks"][0]
    assert metadata == {
        "label": "Q1",
        "anchor_id": "anchor-secret-456",
        "task_spec_id": "task-secret-123",
    }
    assert "task-secret-123" not in str(result.document["answer_key"])


def test_print_adapter_rejects_stale_recomputed_hash() -> None:
    stored = _stored()
    changed = stored.document.model_copy(update={"content_hash": "0" * 64})
    tampered = StoredSharedLessonDocument(
        document=changed,
        path_lesson_id=stored.path_lesson_id,
        status="ready",
        storage_hash=content_hash(changed.model_dump(mode="json")),
    )

    with pytest.raises(SharedDocumentPrintMappingError, match="content hash is stale"):
        realize_shared_document_for_print(tampered, expected_identity=_identity(stored))


def test_print_adapter_fails_when_required_figure_media_is_missing() -> None:
    stored = _stored(include_figure=True)

    with pytest.raises(SharedDocumentPrintMappingError, match="no document-bound Print media"):
        realize_shared_document_for_print(stored, expected_identity=_identity(stored))
